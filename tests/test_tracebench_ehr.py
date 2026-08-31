"""TraceBench-EHR正式評価の単体テスト。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from interactive_ehr.evaluation.tracebench_ehr import (
    DataArtifact,
    ExpectationMode,
    MutationKind,
    ResultSnapshot,
    SemanticExpectation,
    TraceBenchError,
    TraceCandidate,
    TraceContract,
    ValidationCondition,
    WidgetArtifact,
    WidgetMapping,
    execute_query_snapshot,
    load_tracebench_config,
    normalize_query,
    normalized_query_checksum,
    oracle_candidate_valid,
    referenced_tables,
    validate_candidate,
)


def test_load_frozen_config() -> None:
    """固定設定が8変異と4条件を含むことを確認する。"""

    config = load_tracebench_config(Path("data/evaluation/tracebench_ehr.v1.json"))
    assert set(config.mutation_kinds) == set(MutationKind)
    assert set(config.validation_conditions) == set(ValidationCondition)
    assert config.bootstrap_iterations == 10_000


def test_normalize_query_rejects_write_statement() -> None:
    """書き込みSQLが正規化前に拒否されることを確認する。"""

    with pytest.raises(TraceBenchError):
        normalize_query("UPDATE labs SET value = 1")


def test_execute_empty_result_maps_to_dataframe(tmp_path: Path) -> None:
    """空結果を値のないMetricではなくDataframeへ割り当てる。"""

    database_path = tmp_path / "sample.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE labs(subject_id INTEGER, value REAL)")
    connection.commit()
    snapshot = execute_query_snapshot(
        connection,
        "SELECT value FROM labs WHERE subject_id = 1",
        timeout_seconds=1.0,
        max_result_rows=100,
    )
    connection.close()
    assert snapshot.row_count == 0
    assert snapshot.widget_mapping is WidgetMapping.DATAFRAME


def test_semantic_mutation_passes_local_and_fails_cross_layer() -> None:
    """対象患者の不整合を局所検査が通し、層間契約が特定する。"""

    candidate, contract = _semantic_candidate()
    local = validate_candidate(candidate, contract, ValidationCondition.LOCAL_CHECKS)
    artifact = validate_candidate(
        candidate,
        contract,
        ValidationCondition.ARTIFACT_CONTRACTS,
    )
    graph = validate_candidate(candidate, contract, ValidationCondition.GRAPH_CONTRACT)
    sidecar = validate_candidate(
        candidate,
        contract,
        ValidationCondition.SIDECAR_CONTRACT,
    )
    assert local.accepted
    assert artifact.accepted
    assert not graph.accepted
    assert not sidecar.accepted
    assert MutationKind.PATIENT in {issue.mutation_kind for issue in graph.issues}
    assert graph.accepted == sidecar.accepted


def test_artifact_contract_detects_stale_result() -> None:
    """SQLと別の実行結果を成果物契約が拒否する。"""

    candidate, contract = _valid_candidate()
    target = candidate.data_nodes[candidate.target_node_id]
    stale_result = target.result.model_copy(update={"query_checksum": "stale"})
    stale_node = target.model_copy(update={"result": stale_result})
    stale_candidate = candidate.model_copy(
        update={
            "expected_valid": False,
            "data_nodes": {candidate.target_node_id: stale_node},
        }
    )
    local = validate_candidate(
        stale_candidate,
        contract,
        ValidationCondition.LOCAL_CHECKS,
    )
    artifact = validate_candidate(
        stale_candidate,
        contract,
        ValidationCondition.ARTIFACT_CONTRACTS,
    )
    assert local.accepted
    assert not artifact.accepted
    assert MutationKind.STALE_RESULT in {
        issue.mutation_kind for issue in artifact.issues
    }


def test_graph_detects_wrong_widget_connection() -> None:
    """存在する別DataNodeへの誤接続をグラフ契約が拒否する。"""

    candidate, contract = _valid_candidate()
    target = candidate.data_nodes[candidate.target_node_id]
    source = target.model_copy(update={"node_id": "source-node"})
    wrong_widget = candidate.widget.model_copy(update={"data_node_id": source.node_id})
    wrong_candidate = candidate.model_copy(
        update={
            "expected_valid": False,
            "data_nodes": {
                candidate.target_node_id: target,
                source.node_id: source,
            },
            "widget": wrong_widget,
        }
    )
    expanded_contract = contract.model_copy(
        update={"allowed_node_ids": sorted((candidate.target_node_id, source.node_id))}
    )
    assert validate_candidate(
        wrong_candidate,
        expanded_contract,
        ValidationCondition.LOCAL_CHECKS,
    ).accepted
    graph = validate_candidate(
        wrong_candidate,
        expanded_contract,
        ValidationCondition.GRAPH_CONTRACT,
    )
    assert not graph.accepted
    assert MutationKind.DATA_WIDGET_CONNECTION in {
        issue.mutation_kind for issue in graph.issues
    }


@pytest.mark.parametrize(
    ("baseline_mapping", "mutated_mapping", "row_count"),
    (
        (WidgetMapping.METRIC, WidgetMapping.DATAFRAME, 1),
        (WidgetMapping.DATAFRAME, WidgetMapping.TABLE, 2),
    ),
)
def test_widget_mapping_mutation_passes_local_and_is_localized(
    baseline_mapping: WidgetMapping,
    mutated_mapping: WidgetMapping,
    row_count: int,
) -> None:
    """描画可能な表示方式の不整合を成果物契約と層間契約が特定する。"""

    candidate, contract = _valid_candidate()
    target = candidate.data_nodes[candidate.target_node_id]
    result = target.result.model_copy(
        update={"row_count": row_count, "widget_mapping": baseline_mapping}
    )
    target = target.model_copy(update={"result": result})
    widget = candidate.widget.model_copy(update={"mapping": mutated_mapping})
    candidate = candidate.model_copy(
        update={
            "mutation_kind": MutationKind.WIDGET_MAPPING,
            "expected_valid": False,
            "data_nodes": {target.node_id: target},
            "widget": widget,
        }
    )
    contract = contract.model_copy(update={"widget_mapping": baseline_mapping})

    local = validate_candidate(candidate, contract, ValidationCondition.LOCAL_CHECKS)
    artifact = validate_candidate(
        candidate,
        contract,
        ValidationCondition.ARTIFACT_CONTRACTS,
    )
    graph = validate_candidate(candidate, contract, ValidationCondition.GRAPH_CONTRACT)

    assert local.accepted
    assert not artifact.accepted
    assert not graph.accepted
    assert MutationKind.WIDGET_MAPPING in {
        issue.mutation_kind for issue in artifact.issues
    }
    assert MutationKind.WIDGET_MAPPING in {
        issue.mutation_kind for issue in graph.issues
    }


def test_oracle_uses_separate_exact_target_path() -> None:
    """独立オラクルが妥当候補だけを正解とする。"""

    valid, contract = _valid_candidate()
    invalid, invalid_contract = _semantic_candidate()
    assert oracle_candidate_valid(valid, contract)
    assert not oracle_candidate_valid(invalid, invalid_contract)


def test_referenced_tables_are_normalized() -> None:
    """SQLの参照テーブルを重複なく抽出する。"""

    assert referenced_tables(
        "SELECT labs.value FROM labs JOIN patients ON labs.subject_id = patients.subject_id"
    ) == ["labs", "patients"]


def _valid_candidate() -> tuple[TraceCandidate, TraceContract]:
    """検査用の妥当候補と契約を返す。"""

    query = "SELECT value FROM labs WHERE subject_id = 2"
    query_checksum = normalized_query_checksum(query)
    column_checksum = "column-value"
    result = ResultSnapshot(
        query_checksum=query_checksum,
        result_digest="target-result",
        column_checksums=[column_checksum],
        row_count=1,
        row_count_capped=False,
        widget_mapping=WidgetMapping.METRIC,
    )
    data_node = DataArtifact(
        node_id="target-node",
        query=query,
        provenance_tables=["labs"],
        result=result,
    )
    widget = WidgetArtifact(
        widget_id="widget",
        data_node_id=data_node.node_id,
        field_checksums=[column_checksum],
        mapping=WidgetMapping.METRIC,
    )
    candidate = TraceCandidate(
        candidate_id="valid",
        pair_id="pair",
        template_checksum="template",
        mutation_kind=MutationKind.PATIENT,
        expected_valid=True,
        question_checksum="question",
        target_node_id=data_node.node_id,
        data_nodes={data_node.node_id: data_node},
        widget=widget,
    )
    contract = TraceContract(
        pair_id="pair",
        question_checksum="question",
        target_node_id=data_node.node_id,
        allowed_node_ids=[data_node.node_id],
        normalized_query_checksum=query_checksum,
        provenance_tables=["labs"],
        result_query_checksum=query_checksum,
        result_digest="target-result",
        result_column_checksums=[column_checksum],
        widget_id="widget",
        widget_data_node_id=data_node.node_id,
        widget_field_checksums=[column_checksum],
        widget_mapping=WidgetMapping.METRIC,
        semantic_expectations=[
            SemanticExpectation(
                mutation_kind=MutationKind.PATIENT,
                key="patient_id",
                mode=ExpectationMode.LITERAL,
                value=2,
            )
        ],
    )
    return candidate, contract


def _semantic_candidate() -> tuple[TraceCandidate, TraceContract]:
    """患者だけが目標更新と異なる自己整合的な候補を返す。"""

    valid, contract = _valid_candidate()
    query = "SELECT value FROM labs WHERE subject_id = 1"
    result = valid.data_nodes[valid.target_node_id].result.model_copy(
        update={
            "query_checksum": normalized_query_checksum(query),
            "result_digest": "mutated-result",
        }
    )
    data_node = valid.data_nodes[valid.target_node_id].model_copy(
        update={"query": query, "result": result}
    )
    candidate = valid.model_copy(
        update={
            "candidate_id": "invalid",
            "expected_valid": False,
            "data_nodes": {data_node.node_id: data_node},
        }
    )
    return candidate, contract
