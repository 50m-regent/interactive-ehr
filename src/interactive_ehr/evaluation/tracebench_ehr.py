"""EHRSQL-2024に基づくTraceBench-EHR正式評価。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from interactive_ehr.evaluation.ehrsql_feasibility import (
    sha256_file,
    sha256_text,
    validate_read_only_query,
)

_ITEM_KEY_PARTS = (
    "name",
    "route",
    "careunit",
    "spec",
    "abbreviation",
    "gender",
)
_WRITE_ACTION_NAMES = (
    "SQLITE_ALTER_TABLE",
    "SQLITE_ANALYZE",
    "SQLITE_ATTACH",
    "SQLITE_CREATE_INDEX",
    "SQLITE_CREATE_TABLE",
    "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER",
    "SQLITE_CREATE_TEMP_VIEW",
    "SQLITE_CREATE_TRIGGER",
    "SQLITE_CREATE_VIEW",
    "SQLITE_CREATE_VTABLE",
    "SQLITE_DELETE",
    "SQLITE_DETACH",
    "SQLITE_DROP_INDEX",
    "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX",
    "SQLITE_DROP_TEMP_TABLE",
    "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER",
    "SQLITE_DROP_VIEW",
    "SQLITE_DROP_VTABLE",
    "SQLITE_INSERT",
    "SQLITE_PRAGMA",
    "SQLITE_REINDEX",
    "SQLITE_SAVEPOINT",
    "SQLITE_TRANSACTION",
    "SQLITE_UPDATE",
)
_WRITE_ACTIONS = frozenset(
    getattr(sqlite3, name) for name in _WRITE_ACTION_NAMES if hasattr(sqlite3, name)
)


class TraceBenchError(ValueError):
    """TraceBench-EHRの入力または実行条件が不正であることを示す。"""


class TraceSplit(str, Enum):
    """EHRSQL-2024の評価分割。"""

    VALIDATION = "validation"
    TEST = "test"


class MutationKind(str, Enum):
    """事前に固定した層間不整合。"""

    PATIENT = "patient"
    CLINICAL_ITEM = "clinical_item"
    TIME_CONSTRAINT = "time_constraint"
    AGGREGATION_OPERATION = "aggregation_operation"
    INFORMATION_SOURCE = "information_source"
    WIDGET_MAPPING = "widget_mapping"
    DATA_WIDGET_CONNECTION = "data_widget_connection"
    STALE_RESULT = "stale_result"


class ValidationCondition(str, Enum):
    """更新候補へ適用する検査条件。"""

    LOCAL_CHECKS = "local_checks"
    ARTIFACT_CONTRACTS = "artifact_contracts"
    GRAPH_CONTRACT = "graph_contract"
    SIDECAR_CONTRACT = "sidecar_contract"


class WidgetMapping(str, Enum):
    """SQL結果へ割り当てる表示部品。"""

    METRIC = "metric"
    DATAFRAME = "dataframe"
    TABLE = "table"


class ExpectationMode(str, Enum):
    """SQL中の期待値を検査する方法。"""

    LITERAL = "literal"
    FRAGMENT = "fragment"


class TraceBenchConfig(BaseModel):
    """正式評価前に固定する設定。"""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    dataset_commit: str
    dataset_repository: str
    dataset_version: str
    database_checksum: str
    input_checksums: dict[str, dict[str, str]]
    splits: dict[str, str]
    sample_seed: int
    bootstrap_iterations: int = Field(gt=0)
    query_timeout_seconds: float = Field(gt=0.0)
    max_result_rows: int = Field(gt=0)
    minimum_baseline_success_rate: float = Field(ge=0.0, le=1.0)
    minimum_templates_per_mutation: int = Field(gt=0)
    minimum_candidates_per_mutation: int = Field(gt=0)
    mutation_kinds: list[MutationKind]
    validation_conditions: list[ValidationCondition]
    interpretation_limit: str
    privacy_policy: str

    @model_validator(mode="after")
    def validate_registered_values(self) -> Self:
        """列挙値の欠落や重複を拒否する。"""

        if set(self.mutation_kinds) != set(MutationKind):
            raise ValueError("mutation_kinds must contain every registered mutation")
        if set(self.validation_conditions) != set(ValidationCondition):
            raise ValueError(
                "validation_conditions must contain every registered condition"
            )
        if len(self.mutation_kinds) != len(set(self.mutation_kinds)):
            raise ValueError("mutation_kinds contains duplicates")
        if len(self.validation_conditions) != len(set(self.validation_conditions)):
            raise ValueError("validation_conditions contains duplicates")
        return self


class TraceCase(BaseModel):
    """EHRSQLの個票を実行中だけ保持する。"""

    model_config = ConfigDict(frozen=True)

    case_id: str
    split: TraceSplit
    question: str
    query: str
    template: str
    val_dict: dict[str, Any]


class SemanticExpectation(BaseModel):
    """質問からSQLへ伝わる意味要素の期待値。"""

    model_config = ConfigDict(frozen=True)

    mutation_kind: MutationKind
    key: str
    mode: ExpectationMode
    value: str | int | float


class ResultSnapshot(BaseModel):
    """結果値を含まないSQL実行結果。"""

    model_config = ConfigDict(frozen=True)

    query_checksum: str
    result_digest: str
    column_checksums: list[str]
    row_count: int = Field(ge=0)
    row_count_capped: bool
    widget_mapping: WidgetMapping
    execution_seconds: float = Field(ge=0.0)


class DataArtifact(BaseModel):
    """SQL、来歴、実行結果を持つDataNode相当の成果物。"""

    model_config = ConfigDict(frozen=True)

    node_id: str
    query: str
    provenance_tables: list[str]
    result: ResultSnapshot


class WidgetArtifact(BaseModel):
    """DataArtifactとの接続と列対応を持つWidget成果物。"""

    model_config = ConfigDict(frozen=True)

    widget_id: str
    data_node_id: str
    field_checksums: list[str]
    mapping: WidgetMapping


class TraceCandidate(BaseModel):
    """一つの正しい更新または不整合を含む更新候補。"""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    pair_id: str
    template_checksum: str
    mutation_kind: MutationKind
    expected_valid: bool
    question_checksum: str
    target_node_id: str
    data_nodes: dict[str, DataArtifact]
    widget: WidgetArtifact


class TraceContract(BaseModel):
    """更新後に質問からWidgetまで保持すべき層間契約。"""

    model_config = ConfigDict(frozen=True)

    pair_id: str
    question_checksum: str
    target_node_id: str
    allowed_node_ids: list[str]
    normalized_query_checksum: str
    provenance_tables: list[str]
    result_query_checksum: str
    result_digest: str
    result_column_checksums: list[str]
    widget_id: str
    widget_data_node_id: str
    widget_field_checksums: list[str]
    widget_mapping: WidgetMapping
    semantic_expectations: list[SemanticExpectation]


class TracePair(BaseModel):
    """同じ更新前後から作る妥当候補と単一不整合候補。"""

    model_config = ConfigDict(frozen=True)

    pair_id: str
    mutation_kind: MutationKind
    template_checksum: str
    source_case_id: str
    target_case_id: str
    valid_candidate: TraceCandidate
    invalid_candidate: TraceCandidate
    contract: TraceContract


class ValidationIssue(BaseModel):
    """検査で見つかった問題と局在。"""

    model_config = ConfigDict(frozen=True)

    code: str
    layer: str
    mutation_kind: MutationKind | None = None


class ValidationReport(BaseModel):
    """一つの条件が返す受理判定と問題一覧。"""

    model_config = ConfigDict(frozen=True)

    condition: ValidationCondition
    accepted: bool
    issues: list[ValidationIssue]


class CandidateRunRecord(BaseModel):
    """内容を含まない候補単位の評価結果。"""

    model_config = ConfigDict(frozen=True)

    pair_id: str
    candidate_id: str
    template_checksum: str
    mutation_kind: MutationKind
    condition: ValidationCondition
    expected_valid: bool
    oracle_valid: bool
    accepted: bool
    unsafe_acceptance: bool
    safe_rejection: bool
    over_rejection: bool
    localization_correct: bool | None
    repair_attempted: bool
    repair_success: bool | None
    issue_codes: list[str]
    validation_seconds: float = Field(ge=0.0)


class PairManifestRecord(BaseModel):
    """質問、SQL、値を含まない更新ペアの記録。"""

    model_config = ConfigDict(frozen=True)

    pair_id: str
    mutation_kind: MutationKind
    template_checksum: str
    source_case_id: str
    target_case_id: str
    valid_candidate_checksum: str
    invalid_candidate_checksum: str
    contract_checksum: str


class TraceBuildSummary(BaseModel):
    """基準ケースの実行と候補生成の件数。"""

    model_config = ConfigDict(frozen=True)

    split: TraceSplit
    total_case_count: int
    answerable_case_count: int
    answerable_template_count: int
    baseline_success_count: int
    baseline_success_rate: float
    baseline_failure_count: int
    row_count_capped_count: int
    empty_result_count: int
    pair_count: int
    pair_counts_by_mutation: dict[str, int]
    template_counts_by_mutation: dict[str, int]
    construction_failure_counts: dict[str, int]


class TraceBenchmarkRun(BaseModel):
    """正式評価の機微情報を除いた実行結果。"""

    model_config = ConfigDict(frozen=True)

    build_summary: TraceBuildSummary
    pair_manifest: list[PairManifestRecord]
    candidate_records: list[CandidateRunRecord]


class _PairDescriptor(BaseModel):
    """候補を作る前の更新ペアと置換対象。"""

    model_config = ConfigDict(frozen=True)

    source_case_id: str
    target_case_id: str
    mutation_kind: MutationKind
    expectation_key: str | None = None


def load_tracebench_config(path: Path) -> TraceBenchConfig:
    """固定したTraceBench-EHR設定を読む。"""

    return TraceBenchConfig.model_validate_json(path.read_text(encoding="utf-8"))


def verify_tracebench_inputs(
    config: TraceBenchConfig,
    *,
    split: TraceSplit,
    annotated_path: Path,
    dataset_data_path: Path,
    database_path: Path,
) -> None:
    """分割ごとの入力チェックサムを固定値と照合する。"""

    expected = config.input_checksums.get(split.value)
    if expected is None:
        raise TraceBenchError(f"missing input checksums for {split.value}")
    observed = {
        "annotated.json": sha256_file(annotated_path),
        "data.json": sha256_file(dataset_data_path),
    }
    if observed != expected:
        raise TraceBenchError(f"input checksum mismatch for {split.value}: {observed}")
    database_checksum = sha256_file(database_path)
    if database_checksum != config.database_checksum:
        raise TraceBenchError("database checksum mismatch")


def load_trace_cases(path: Path, *, split: TraceSplit) -> list[TraceCase]:
    """EHRSQL annotated.jsonから回答可能ケースを含む全個票を読む。"""

    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_cases, list):
        raise TraceBenchError("annotated data must be an array")
    cases: list[TraceCase] = []
    seen_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise TraceBenchError("each annotated case must be an object")
        case_id = str(raw_case.get("id", ""))
        if not case_id or case_id in seen_ids:
            raise TraceBenchError(f"empty or duplicate case ID: {case_id}")
        seen_ids.add(case_id)
        val_dict = raw_case.get("val_dict")
        cases.append(
            TraceCase(
                case_id=case_id,
                split=split,
                question=str(raw_case.get("question", "")),
                query=str(raw_case.get("query", "")),
                template=str(raw_case.get("template", "")),
                val_dict=val_dict if isinstance(val_dict, dict) else {},
            )
        )
    return cases


def is_answerable(case: TraceCase) -> bool:
    """ケースが正解SQLを持つか返す。"""

    return case.query.strip().lower() != "null"


def normalize_query(query: str) -> str:
    """単一の読み取り専用SQLite SQLを正規化する。"""

    try:
        validate_read_only_query(query)
    except ValueError as error:
        raise TraceBenchError("query is not a single read-only statement") from error
    try:
        expression = parse_one(query, read="sqlite")
    except ParseError as error:
        raise TraceBenchError("SQL parse failed") from error
    if expression.find(exp.Select) is None:
        raise TraceBenchError("query does not contain SELECT")
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Command,
    )
    if any(expression.find(node_type) is not None for node_type in forbidden):
        raise TraceBenchError("query contains a write or command expression")
    return expression.sql(dialect="sqlite", pretty=False)


def normalized_query_checksum(query: str) -> str:
    """正規化したSQLのチェックサムを返す。"""

    return sha256_text(normalize_query(query))


def referenced_tables(query: str) -> list[str]:
    """SQLが参照するテーブル名を正規化して返す。"""

    expression = parse_one(normalize_query(query), read="sqlite")
    return sorted({table.name.casefold() for table in expression.find_all(exp.Table)})


def semantic_expectations(case: TraceCase) -> list[SemanticExpectation]:
    """質問注釈からSQLに現れる意味要素だけを抽出する。"""

    candidates: list[SemanticExpectation] = []
    value_placeholders = case.val_dict.get("val_placeholder", {})
    if isinstance(value_placeholders, Mapping):
        for key, value in sorted(value_placeholders.items()):
            mutation_kind = _value_mutation_kind(str(key))
            if mutation_kind is None or not isinstance(value, (str, int, float)):
                continue
            expectation = SemanticExpectation(
                mutation_kind=mutation_kind,
                key=str(key),
                mode=ExpectationMode.LITERAL,
                value=value,
            )
            if _expectation_present(case.query, expectation):
                candidates.append(expectation)
    for group_name, mutation_kind in (
        ("time_placeholder", MutationKind.TIME_CONSTRAINT),
        ("op_placeholder", MutationKind.AGGREGATION_OPERATION),
    ):
        group = case.val_dict.get(group_name, {})
        if not isinstance(group, Mapping):
            continue
        for key, value in sorted(group.items()):
            if not isinstance(value, dict):
                continue
            value_dict = cast(dict[str, Any], value)
            if not isinstance(value_dict.get("sql"), str):
                continue
            expectation = SemanticExpectation(
                mutation_kind=mutation_kind,
                key=str(key),
                mode=ExpectationMode.FRAGMENT,
                value=str(value_dict["sql"]),
            )
            if _expectation_present(case.query, expectation):
                candidates.append(expectation)
    return candidates


def execute_query_snapshot(
    connection: sqlite3.Connection,
    query: str,
    *,
    timeout_seconds: float,
    max_result_rows: int,
) -> ResultSnapshot:
    """SQLを実行し、結果値を保存せず安定したダイジェストへ変換する。"""

    if timeout_seconds <= 0.0 or max_result_rows <= 0:
        raise TraceBenchError("query limits must be positive")
    normalized_checksum = normalized_query_checksum(query)
    deadline = time.monotonic() + timeout_seconds
    started_at = time.monotonic()

    def progress_handler() -> int:
        """実行期限を超えたSQLite処理を停止する。"""

        return int(time.monotonic() > deadline)

    connection.set_progress_handler(progress_handler, 1_000)
    try:
        cursor = connection.execute(query)
        column_names = [str(item[0]) for item in cursor.description or []]
        rows = cursor.fetchmany(max_result_rows + 1)
    except sqlite3.Error as error:
        raise TraceBenchError("SQL execution failed") from error
    finally:
        connection.set_progress_handler(None, 0)
    if not column_names:
        raise TraceBenchError("query returned no columns")
    capped = len(rows) > max_result_rows
    observed_rows = rows[:max_result_rows]
    column_checksums = [sha256_text(name) for name in column_names]
    mapping = (
        WidgetMapping.METRIC
        if len(column_names) == 1 and len(observed_rows) == 1
        else WidgetMapping.DATAFRAME
    )
    return ResultSnapshot(
        query_checksum=normalized_checksum,
        result_digest=_result_digest(column_checksums, observed_rows),
        column_checksums=column_checksums,
        row_count=len(observed_rows),
        row_count_capped=capped,
        widget_mapping=mapping,
        execution_seconds=time.monotonic() - started_at,
    )


def build_tracebench_run(
    cases: Sequence[TraceCase],
    *,
    split: TraceSplit,
    database_path: Path,
    config: TraceBenchConfig,
) -> TraceBenchmarkRun:
    """基準SQLを実行し、更新ペアを生成して全条件を一度ずつ評価する。"""

    answerable_cases = [case for case in cases if is_answerable(case)]
    connection = _open_read_only_connection(database_path)
    baseline_artifacts: dict[str, DataArtifact] = {}
    baseline_failures = 0
    try:
        for case in answerable_cases:
            try:
                baseline_artifacts[case.case_id] = _baseline_artifact(
                    case,
                    connection=connection,
                    timeout_seconds=config.query_timeout_seconds,
                    max_result_rows=config.max_result_rows,
                )
            except TraceBenchError:
                baseline_failures += 1
        pairs, construction_failures = _build_pairs(
            answerable_cases,
            baseline_artifacts=baseline_artifacts,
            connection=connection,
            config=config,
        )
    finally:
        connection.close()

    records = [
        record
        for pair in pairs
        for candidate in (pair.valid_candidate, pair.invalid_candidate)
        for record in _evaluate_candidate(pair, candidate, config.validation_conditions)
    ]
    pair_manifest = [
        PairManifestRecord(
            pair_id=pair.pair_id,
            mutation_kind=pair.mutation_kind,
            template_checksum=pair.template_checksum,
            source_case_id=pair.source_case_id,
            target_case_id=pair.target_case_id,
            valid_candidate_checksum=_model_checksum(pair.valid_candidate),
            invalid_candidate_checksum=_model_checksum(pair.invalid_candidate),
            contract_checksum=_model_checksum(pair.contract),
        )
        for pair in pairs
    ]
    pair_counts = {
        mutation.value: sum(pair.mutation_kind is mutation for pair in pairs)
        for mutation in MutationKind
    }
    template_counts = {
        mutation.value: len(
            {pair.template_checksum for pair in pairs if pair.mutation_kind is mutation}
        )
        for mutation in MutationKind
    }
    baseline_success_count = len(baseline_artifacts)
    baseline_success_rate = _safe_rate(baseline_success_count, len(answerable_cases))
    return TraceBenchmarkRun(
        build_summary=TraceBuildSummary(
            split=split,
            total_case_count=len(cases),
            answerable_case_count=len(answerable_cases),
            answerable_template_count=len({case.template for case in answerable_cases}),
            baseline_success_count=baseline_success_count,
            baseline_success_rate=baseline_success_rate,
            baseline_failure_count=baseline_failures,
            row_count_capped_count=sum(
                artifact.result.row_count_capped
                for artifact in baseline_artifacts.values()
            ),
            empty_result_count=sum(
                artifact.result.row_count == 0
                for artifact in baseline_artifacts.values()
            ),
            pair_count=len(pairs),
            pair_counts_by_mutation=pair_counts,
            template_counts_by_mutation=template_counts,
            construction_failure_counts=construction_failures,
        ),
        pair_manifest=pair_manifest,
        candidate_records=records,
    )


def validate_pilot_gate(
    run: TraceBenchmarkRun,
    config: TraceBenchConfig,
) -> list[str]:
    """validationパイロットが正式評価の停止条件を満たすか返す。"""

    failures: list[str] = []
    summary = run.build_summary
    if summary.baseline_success_rate < config.minimum_baseline_success_rate:
        failures.append(
            f"baseline success rate below {config.minimum_baseline_success_rate:.3f}"
        )
    for mutation in MutationKind:
        candidate_count = summary.pair_counts_by_mutation.get(mutation.value, 0)
        template_count = summary.template_counts_by_mutation.get(mutation.value, 0)
        if candidate_count < config.minimum_candidates_per_mutation:
            failures.append(
                f"{mutation.value} has {candidate_count} candidates; "
                f"requires {config.minimum_candidates_per_mutation}"
            )
        if template_count < config.minimum_templates_per_mutation:
            failures.append(
                f"{mutation.value} has {template_count} templates; "
                f"requires {config.minimum_templates_per_mutation}"
            )
    return failures


def validate_candidate(
    candidate: TraceCandidate,
    contract: TraceContract,
    condition: ValidationCondition,
) -> ValidationReport:
    """一つの候補を指定条件で検査する。"""

    if condition is ValidationCondition.LOCAL_CHECKS:
        issues = _local_issues(candidate)
    elif condition is ValidationCondition.ARTIFACT_CONTRACTS:
        issues = _local_issues(candidate) + _artifact_issues(candidate)
    elif condition is ValidationCondition.GRAPH_CONTRACT:
        issues = (
            _local_issues(candidate)
            + _artifact_issues(candidate)
            + _graph_issues(candidate, contract)
        )
    else:
        issues = (
            _local_issues(candidate)
            + _artifact_issues(candidate)
            + _sidecar_issues(candidate, contract)
        )
    unique_issues = _unique_issues(issues)
    return ValidationReport(
        condition=condition,
        accepted=not unique_issues,
        issues=unique_issues,
    )


def oracle_candidate_valid(
    candidate: TraceCandidate,
    contract: TraceContract,
) -> bool:
    """実行時検査と別の経路で候補が目標更新と一致するか判定する。"""

    target_node = candidate.data_nodes.get(contract.target_node_id)
    if target_node is None:
        return False
    return all(
        (
            candidate.question_checksum == contract.question_checksum,
            normalized_query_checksum(target_node.query)
            == contract.normalized_query_checksum,
            target_node.provenance_tables == contract.provenance_tables,
            target_node.result.query_checksum == contract.result_query_checksum,
            target_node.result.result_digest == contract.result_digest,
            target_node.result.column_checksums == contract.result_column_checksums,
            candidate.widget.widget_id == contract.widget_id,
            candidate.widget.data_node_id == contract.widget_data_node_id,
            candidate.widget.field_checksums == contract.widget_field_checksums,
            candidate.widget.mapping is contract.widget_mapping,
        )
    )


def _build_pairs(
    cases: Sequence[TraceCase],
    *,
    baseline_artifacts: Mapping[str, DataArtifact],
    connection: sqlite3.Connection,
    config: TraceBenchConfig,
) -> tuple[list[TracePair], dict[str, int]]:
    """各テンプレートから変異種類ごとに一つの決定的な更新ペアを作る。"""

    cases_by_template: dict[str, list[TraceCase]] = defaultdict(list)
    for case in cases:
        if case.case_id in baseline_artifacts:
            cases_by_template[case.template].append(case)
    pairs: list[TracePair] = []
    construction_failures = {mutation.value: 0 for mutation in MutationKind}
    for template, template_cases in sorted(cases_by_template.items()):
        if len(template_cases) < 2:
            continue
        for mutation in MutationKind:
            descriptors = _ordered_descriptors(
                template,
                template_cases,
                mutation=mutation,
                baseline_artifacts=baseline_artifacts,
                seed=config.sample_seed,
            )
            for descriptor in descriptors:
                source = _case_by_id(template_cases, descriptor.source_case_id)
                target = _case_by_id(template_cases, descriptor.target_case_id)
                try:
                    pair = _build_pair(
                        descriptor,
                        source=source,
                        target=target,
                        source_artifact=baseline_artifacts[source.case_id],
                        target_artifact=baseline_artifacts[target.case_id],
                        connection=connection,
                        config=config,
                    )
                except TraceBenchError:
                    construction_failures[mutation.value] += 1
                    continue
                pairs.append(pair)
                break
    return pairs, construction_failures


def _ordered_descriptors(
    template: str,
    cases: Sequence[TraceCase],
    *,
    mutation: MutationKind,
    baseline_artifacts: Mapping[str, DataArtifact],
    seed: int,
) -> list[_PairDescriptor]:
    """適用可能な更新前後ペアをseed付きハッシュ順で返す。"""

    descriptors: list[_PairDescriptor] = []
    for source in cases:
        for target in cases:
            if source.case_id == target.case_id:
                continue
            source_artifact = baseline_artifacts[source.case_id]
            target_artifact = baseline_artifacts[target.case_id]
            if mutation in _semantic_mutations():
                for key in _eligible_expectation_keys(source, target, mutation):
                    descriptors.append(
                        _PairDescriptor(
                            source_case_id=source.case_id,
                            target_case_id=target.case_id,
                            mutation_kind=mutation,
                            expectation_key=key,
                        )
                    )
            elif mutation is MutationKind.WIDGET_MAPPING:
                descriptors.append(
                    _PairDescriptor(
                        source_case_id=source.case_id,
                        target_case_id=target.case_id,
                        mutation_kind=mutation,
                    )
                )
            elif mutation is MutationKind.DATA_WIDGET_CONNECTION:
                if (
                    target_artifact.result.column_checksums
                    == source_artifact.result.column_checksums
                    and target_artifact.result.widget_mapping
                    is source_artifact.result.widget_mapping
                ):
                    descriptors.append(
                        _PairDescriptor(
                            source_case_id=source.case_id,
                            target_case_id=target.case_id,
                            mutation_kind=mutation,
                        )
                    )
            elif mutation is MutationKind.STALE_RESULT:
                if (
                    target_artifact.result.column_checksums
                    == source_artifact.result.column_checksums
                    and target_artifact.result.widget_mapping
                    is source_artifact.result.widget_mapping
                    and target_artifact.result.result_digest
                    != source_artifact.result.result_digest
                ):
                    descriptors.append(
                        _PairDescriptor(
                            source_case_id=source.case_id,
                            target_case_id=target.case_id,
                            mutation_kind=mutation,
                        )
                    )
            else:
                descriptors.append(
                    _PairDescriptor(
                        source_case_id=source.case_id,
                        target_case_id=target.case_id,
                        mutation_kind=mutation,
                    )
                )
    return sorted(
        descriptors,
        key=lambda item: sha256_text(
            f"{seed}:{template}:{mutation.value}:"
            f"{item.source_case_id}:{item.target_case_id}:"
            f"{item.expectation_key or ''}"
        ),
    )


def _build_pair(
    descriptor: _PairDescriptor,
    *,
    source: TraceCase,
    target: TraceCase,
    source_artifact: DataArtifact,
    target_artifact: DataArtifact,
    connection: sqlite3.Connection,
    config: TraceBenchConfig,
) -> TracePair:
    """一つの妥当候補と単一不整合候補を作る。"""

    pair_id = sha256_text(
        f"{target.split.value}:{target.template}:{descriptor.mutation_kind.value}:"
        f"{source.case_id}:{target.case_id}"
    )[:24]
    source_node = source_artifact.model_copy(
        update={"node_id": f"source-{source.case_id}"}
    )
    target_node = target_artifact.model_copy(
        update={"node_id": f"target-{target.case_id}"}
    )
    target_widget = WidgetArtifact(
        widget_id=f"widget-{target.case_id}",
        data_node_id=target_node.node_id,
        field_checksums=target_node.result.column_checksums,
        mapping=target_node.result.widget_mapping,
    )
    data_nodes = {source_node.node_id: source_node, target_node.node_id: target_node}
    valid_candidate = TraceCandidate(
        candidate_id=f"{pair_id}-valid",
        pair_id=pair_id,
        template_checksum=sha256_text(target.template),
        mutation_kind=descriptor.mutation_kind,
        expected_valid=True,
        question_checksum=sha256_text(target.question),
        target_node_id=target_node.node_id,
        data_nodes=data_nodes,
        widget=target_widget,
    )
    contract = _build_contract(
        pair_id,
        target=target,
        source_node=source_node,
        target_node=target_node,
        widget=target_widget,
    )
    invalid_candidate = _mutated_candidate(
        valid_candidate,
        descriptor=descriptor,
        source=source,
        target=target,
        source_node=source_node,
        target_node=target_node,
        connection=connection,
        config=config,
    )
    if not oracle_candidate_valid(valid_candidate, contract):
        raise TraceBenchError("valid candidate does not satisfy the oracle")
    if oracle_candidate_valid(invalid_candidate, contract):
        raise TraceBenchError("invalid candidate satisfies the oracle")
    if not validate_candidate(
        invalid_candidate, contract, ValidationCondition.LOCAL_CHECKS
    ).accepted:
        raise TraceBenchError("invalid candidate failed local construction gate")
    return TracePair(
        pair_id=pair_id,
        mutation_kind=descriptor.mutation_kind,
        template_checksum=sha256_text(target.template),
        source_case_id=source.case_id,
        target_case_id=target.case_id,
        valid_candidate=valid_candidate,
        invalid_candidate=invalid_candidate,
        contract=contract,
    )


def _mutated_candidate(
    valid_candidate: TraceCandidate,
    *,
    descriptor: _PairDescriptor,
    source: TraceCase,
    target: TraceCase,
    source_node: DataArtifact,
    target_node: DataArtifact,
    connection: sqlite3.Connection,
    config: TraceBenchConfig,
) -> TraceCandidate:
    """妥当候補へ指定した単一不整合を注入する。"""

    mutation = descriptor.mutation_kind
    data_nodes = dict(valid_candidate.data_nodes)
    widget = valid_candidate.widget
    if mutation in _semantic_mutations():
        if descriptor.expectation_key is None:
            raise TraceBenchError("semantic mutation requires an expectation key")
        query = _mutate_semantic_query(
            target.query,
            source=source,
            target=target,
            mutation=mutation,
            key=descriptor.expectation_key,
        )
        result = execute_query_snapshot(
            connection,
            query,
            timeout_seconds=config.query_timeout_seconds,
            max_result_rows=config.max_result_rows,
        )
        mutated_node = target_node.model_copy(
            update={
                "query": query,
                "provenance_tables": referenced_tables(query),
                "result": result,
            }
        )
        data_nodes[target_node.node_id] = mutated_node
    elif mutation is MutationKind.INFORMATION_SOURCE:
        mutated_tables = _mutated_provenance(target_node.provenance_tables)
        data_nodes[target_node.node_id] = target_node.model_copy(
            update={"provenance_tables": mutated_tables}
        )
    elif mutation is MutationKind.WIDGET_MAPPING:
        widget = widget.model_copy(
            update={"mapping": _alternate_widget_mapping(widget.mapping)}
        )
    elif mutation is MutationKind.DATA_WIDGET_CONNECTION:
        widget = widget.model_copy(update={"data_node_id": source_node.node_id})
    elif mutation is MutationKind.STALE_RESULT:
        data_nodes[target_node.node_id] = target_node.model_copy(
            update={"result": source_node.result}
        )
    else:
        raise TraceBenchError(f"unsupported mutation: {mutation.value}")
    return valid_candidate.model_copy(
        update={
            "candidate_id": f"{valid_candidate.pair_id}-invalid",
            "expected_valid": False,
            "data_nodes": data_nodes,
            "widget": widget,
        }
    )


def _build_contract(
    pair_id: str,
    *,
    target: TraceCase,
    source_node: DataArtifact,
    target_node: DataArtifact,
    widget: WidgetArtifact,
) -> TraceContract:
    """目標ケースから層間契約を作る。"""

    return TraceContract(
        pair_id=pair_id,
        question_checksum=sha256_text(target.question),
        target_node_id=target_node.node_id,
        allowed_node_ids=sorted((source_node.node_id, target_node.node_id)),
        normalized_query_checksum=normalized_query_checksum(target_node.query),
        provenance_tables=target_node.provenance_tables,
        result_query_checksum=target_node.result.query_checksum,
        result_digest=target_node.result.result_digest,
        result_column_checksums=target_node.result.column_checksums,
        widget_id=widget.widget_id,
        widget_data_node_id=widget.data_node_id,
        widget_field_checksums=widget.field_checksums,
        widget_mapping=widget.mapping,
        semantic_expectations=semantic_expectations(target),
    )


def _evaluate_candidate(
    pair: TracePair,
    candidate: TraceCandidate,
    conditions: Sequence[ValidationCondition],
) -> list[CandidateRunRecord]:
    """一つの候補を全条件で評価して修復を一回だけ試す。"""

    oracle_valid = oracle_candidate_valid(candidate, pair.contract)
    records: list[CandidateRunRecord] = []
    for condition in conditions:
        started_at = time.monotonic()
        report = validate_candidate(candidate, pair.contract, condition)
        validation_seconds = time.monotonic() - started_at
        located_kinds = {
            issue.mutation_kind
            for issue in report.issues
            if issue.mutation_kind is not None
        }
        localization_correct = (
            pair.mutation_kind in located_kinds
            if not candidate.expected_valid
            else None
        )
        repair_attempted = not candidate.expected_valid and not report.accepted
        repair_success: bool | None = None
        if repair_attempted:
            repaired = _repair_candidate(candidate, pair, report)
            repaired_report = validate_candidate(repaired, pair.contract, condition)
            repair_success = repaired_report.accepted and oracle_candidate_valid(
                repaired, pair.contract
            )
        records.append(
            CandidateRunRecord(
                pair_id=pair.pair_id,
                candidate_id=candidate.candidate_id,
                template_checksum=pair.template_checksum,
                mutation_kind=pair.mutation_kind,
                condition=condition,
                expected_valid=candidate.expected_valid,
                oracle_valid=oracle_valid,
                accepted=report.accepted,
                unsafe_acceptance=not oracle_valid and report.accepted,
                safe_rejection=not oracle_valid and not report.accepted,
                over_rejection=oracle_valid and not report.accepted,
                localization_correct=localization_correct,
                repair_attempted=repair_attempted,
                repair_success=repair_success,
                issue_codes=[issue.code for issue in report.issues],
                validation_seconds=validation_seconds,
            )
        )
    return records


def _repair_candidate(
    candidate: TraceCandidate,
    pair: TracePair,
    report: ValidationReport,
) -> TraceCandidate:
    """局在した単一不整合の成果物だけを契約済み状態へ戻す。"""

    located = {
        issue.mutation_kind
        for issue in report.issues
        if issue.mutation_kind is not None
    }
    if pair.mutation_kind not in located:
        return candidate
    valid = pair.valid_candidate
    data_nodes = dict(candidate.data_nodes)
    widget = candidate.widget
    if pair.mutation_kind in (
        *_semantic_mutations(),
        MutationKind.INFORMATION_SOURCE,
        MutationKind.STALE_RESULT,
    ):
        data_nodes[valid.target_node_id] = valid.data_nodes[valid.target_node_id]
    elif pair.mutation_kind in (
        MutationKind.WIDGET_MAPPING,
        MutationKind.DATA_WIDGET_CONNECTION,
    ):
        widget = valid.widget
    return candidate.model_copy(update={"data_nodes": data_nodes, "widget": widget})


def _local_issues(candidate: TraceCandidate) -> list[ValidationIssue]:
    """各成果物の構文、実行結果形状、参照存在だけを確認する。"""

    issues: list[ValidationIssue] = []
    if candidate.target_node_id not in candidate.data_nodes:
        issues.append(ValidationIssue(code="missing_target_node", layer="data"))
    bound_node = candidate.data_nodes.get(candidate.widget.data_node_id)
    if bound_node is None:
        issues.append(ValidationIssue(code="missing_widget_binding", layer="widget"))
    for data_node in candidate.data_nodes.values():
        try:
            normalize_query(data_node.query)
        except TraceBenchError:
            issues.append(ValidationIssue(code="invalid_sql", layer="sql"))
        if not data_node.result.column_checksums:
            issues.append(ValidationIssue(code="empty_result_schema", layer="result"))
    if bound_node is not None:
        if not set(candidate.widget.field_checksums).issubset(
            set(bound_node.result.column_checksums)
        ):
            issues.append(ValidationIssue(code="unknown_widget_field", layer="widget"))
        if candidate.widget.mapping is WidgetMapping.METRIC and (
            len(bound_node.result.column_checksums) != 1
            or bound_node.result.row_count != 1
        ):
            issues.append(ValidationIssue(code="invalid_metric_shape", layer="widget"))
    return issues


def _artifact_issues(candidate: TraceCandidate) -> list[ValidationIssue]:
    """SQL、結果、Widgetそれぞれの自己整合性を確認する。"""

    issues: list[ValidationIssue] = []
    for data_node in candidate.data_nodes.values():
        if data_node.provenance_tables != referenced_tables(data_node.query):
            issues.append(
                ValidationIssue(
                    code="query_provenance_mismatch",
                    layer="sql",
                    mutation_kind=MutationKind.INFORMATION_SOURCE,
                )
            )
        if data_node.result.query_checksum != normalized_query_checksum(
            data_node.query
        ):
            issues.append(
                ValidationIssue(
                    code="query_result_mismatch",
                    layer="result",
                    mutation_kind=MutationKind.STALE_RESULT,
                )
            )
    bound_node = candidate.data_nodes.get(candidate.widget.data_node_id)
    if bound_node is not None and candidate.widget.mapping is not (
        bound_node.result.widget_mapping
    ):
        issues.append(
            ValidationIssue(
                code="widget_shape_mismatch",
                layer="widget",
                mutation_kind=MutationKind.WIDGET_MAPPING,
            )
        )
    return issues


def _graph_issues(
    candidate: TraceCandidate,
    contract: TraceContract,
) -> list[ValidationIssue]:
    """質問からWidgetまでグラフの経路順に層間契約を確認する。"""

    issues: list[ValidationIssue] = []
    if candidate.question_checksum != contract.question_checksum:
        issues.append(ValidationIssue(code="question_mismatch", layer="question"))
    target = candidate.data_nodes.get(contract.target_node_id)
    if target is None:
        issues.append(ValidationIssue(code="missing_contract_target", layer="data"))
        return issues
    issues.extend(_semantic_query_issues(target.query, contract))
    issues.extend(_target_data_issues(target, contract))
    issues.extend(_target_widget_issues(candidate.widget, contract))
    if sorted(candidate.data_nodes) != contract.allowed_node_ids:
        issues.append(ValidationIssue(code="unexpected_graph_nodes", layer="graph"))
    return issues


def _sidecar_issues(
    candidate: TraceCandidate,
    contract: TraceContract,
) -> list[ValidationIssue]:
    """平坦なサイドカーの各期待値を成果物へ直接照合する。"""

    issues: list[ValidationIssue] = []
    target = candidate.data_nodes.get(contract.target_node_id)
    flat_checks = {
        "question_checksum": candidate.question_checksum,
        "target_node_id": candidate.target_node_id,
        "widget_id": candidate.widget.widget_id,
        "widget_data_node_id": candidate.widget.data_node_id,
        "widget_mapping": candidate.widget.mapping.value,
    }
    expected = {
        "question_checksum": contract.question_checksum,
        "target_node_id": contract.target_node_id,
        "widget_id": contract.widget_id,
        "widget_data_node_id": contract.widget_data_node_id,
        "widget_mapping": contract.widget_mapping.value,
    }
    for key, value in flat_checks.items():
        if value != expected[key]:
            mutation = {
                "widget_data_node_id": MutationKind.DATA_WIDGET_CONNECTION,
                "widget_mapping": MutationKind.WIDGET_MAPPING,
            }.get(key)
            issues.append(
                ValidationIssue(
                    code=f"sidecar_{key}_mismatch",
                    layer="sidecar",
                    mutation_kind=mutation,
                )
            )
    if target is None:
        issues.append(ValidationIssue(code="sidecar_missing_target", layer="sidecar"))
        return issues
    issues.extend(_semantic_query_issues(target.query, contract))
    issues.extend(_target_data_issues(target, contract))
    issues.extend(_target_widget_issues(candidate.widget, contract))
    return issues


def _semantic_query_issues(
    query: str,
    contract: TraceContract,
) -> list[ValidationIssue]:
    """質問注釈から作った各意味要素をSQLへ照合する。"""

    issues = [
        ValidationIssue(
            code=f"semantic_{expectation.mutation_kind.value}_mismatch",
            layer="question_sql",
            mutation_kind=expectation.mutation_kind,
        )
        for expectation in contract.semantic_expectations
        if not _expectation_present(query, expectation)
    ]
    if normalized_query_checksum(query) != contract.normalized_query_checksum:
        located = {issue.mutation_kind for issue in issues}
        issues.append(
            ValidationIssue(
                code="target_query_mismatch",
                layer="question_sql",
                mutation_kind=next(iter(located)) if len(located) == 1 else None,
            )
        )
    return issues


def _target_data_issues(
    target: DataArtifact,
    contract: TraceContract,
) -> list[ValidationIssue]:
    """目標DataArtifactとSQL・結果間の層間契約を確認する。"""

    issues: list[ValidationIssue] = []
    if target.provenance_tables != contract.provenance_tables:
        issues.append(
            ValidationIssue(
                code="target_provenance_mismatch",
                layer="query_provenance",
                mutation_kind=MutationKind.INFORMATION_SOURCE,
            )
        )
    if (
        target.result.query_checksum == contract.result_query_checksum
        and target.result.result_digest != contract.result_digest
    ):
        issues.append(
            ValidationIssue(
                code="target_result_mismatch",
                layer="sql_result",
                mutation_kind=MutationKind.STALE_RESULT,
            )
        )
    if target.result.column_checksums != contract.result_column_checksums:
        issues.append(
            ValidationIssue(
                code="target_result_schema_mismatch",
                layer="result_widget",
            )
        )
    return issues


def _target_widget_issues(
    widget: WidgetArtifact,
    contract: TraceContract,
) -> list[ValidationIssue]:
    """目標WidgetとDataArtifactの接続・列対応を確認する。"""

    issues: list[ValidationIssue] = []
    if widget.data_node_id != contract.widget_data_node_id:
        issues.append(
            ValidationIssue(
                code="target_widget_connection_mismatch",
                layer="data_widget",
                mutation_kind=MutationKind.DATA_WIDGET_CONNECTION,
            )
        )
    if widget.field_checksums != contract.widget_field_checksums:
        issues.append(
            ValidationIssue(
                code="target_widget_fields_mismatch",
                layer="result_widget",
            )
        )
    if widget.mapping is not contract.widget_mapping:
        issues.append(
            ValidationIssue(
                code="target_widget_mapping_mismatch",
                layer="widget",
                mutation_kind=MutationKind.WIDGET_MAPPING,
            )
        )
    return issues


def _alternate_widget_mapping(mapping: WidgetMapping) -> WidgetMapping:
    """基準表示とは異なり、同じ結果形状を描画できる表示方式を返す。"""

    if mapping is WidgetMapping.METRIC:
        return WidgetMapping.DATAFRAME
    if mapping is WidgetMapping.DATAFRAME:
        return WidgetMapping.TABLE
    raise TraceBenchError(f"no alternate mapping for baseline: {mapping.value}")


def _baseline_artifact(
    case: TraceCase,
    *,
    connection: sqlite3.Connection,
    timeout_seconds: float,
    max_result_rows: int,
) -> DataArtifact:
    """一つのEHRSQLケースから基準DataArtifactを作る。"""

    result = execute_query_snapshot(
        connection,
        case.query,
        timeout_seconds=timeout_seconds,
        max_result_rows=max_result_rows,
    )
    return DataArtifact(
        node_id=case.case_id,
        query=case.query,
        provenance_tables=referenced_tables(case.query),
        result=result,
    )


def _open_read_only_connection(database_path: Path) -> sqlite3.Connection:
    """SQLiteを読み取り専用かつ書き込み拒否で開く。"""

    resolved = database_path.resolve()
    if not resolved.is_file():
        raise TraceBenchError(f"database does not exist: {database_path}")
    connection = sqlite3.connect(
        f"{resolved.as_uri()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.execute("PRAGMA query_only = ON")
    connection.set_authorizer(_sqlite_authorizer)
    return connection


def _sqlite_authorizer(
    action_code: int,
    _argument_one: str | None,
    _argument_two: str | None,
    _database_name: str | None,
    _trigger_name: str | None,
) -> int:
    """SQLiteの書き込み、DDL、PRAGMAを拒否する。"""

    return sqlite3.SQLITE_DENY if action_code in _WRITE_ACTIONS else sqlite3.SQLITE_OK


def _result_digest(
    column_checksums: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    """行順に依存しない結果値のダイジェストを作る。"""

    normalized_rows = sorted(
        json.dumps(
            [_normalize_cell(cell) for cell in row],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for row in rows
    )
    payload = json.dumps(
        {"columns": list(column_checksums), "rows": normalized_rows},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256_text(payload)


def _normalize_cell(value: Any) -> dict[str, str]:
    """型を保ったままセル値をハッシュ入力用文字列へ変換する。"""

    if value is None:
        return {"type": "null", "value": ""}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": hashlib.sha256(value).hexdigest()}
    return {"type": type(value).__name__, "value": repr(value)}


def _value_mutation_kind(key: str) -> MutationKind | None:
    """値プレースホルダーを患者または臨床項目へ分類する。"""

    if key == "patient_id":
        return MutationKind.PATIENT
    if any(part in key for part in _ITEM_KEY_PARTS):
        return MutationKind.CLINICAL_ITEM
    return None


def _semantic_mutations() -> tuple[MutationKind, ...]:
    """SQL意味要素を書き換える変異を返す。"""

    return (
        MutationKind.PATIENT,
        MutationKind.CLINICAL_ITEM,
        MutationKind.TIME_CONSTRAINT,
        MutationKind.AGGREGATION_OPERATION,
    )


def _eligible_expectation_keys(
    source: TraceCase,
    target: TraceCase,
    mutation: MutationKind,
) -> list[str]:
    """同じ種類で値が異なる置換可能な意味要素キーを返す。"""

    source_by_key = {
        item.key: item
        for item in semantic_expectations(source)
        if item.mutation_kind is mutation
    }
    target_by_key = {
        item.key: item
        for item in semantic_expectations(target)
        if item.mutation_kind is mutation
    }
    return [
        key
        for key in sorted(source_by_key.keys() & target_by_key.keys())
        if source_by_key[key].value != target_by_key[key].value
        and source_by_key[key].mode is target_by_key[key].mode
    ]


def _mutate_semantic_query(
    query: str,
    *,
    source: TraceCase,
    target: TraceCase,
    mutation: MutationKind,
    key: str,
) -> str:
    """目標SQLの一つの意味要素だけを更新前の値へ戻す。"""

    source_expectation = _expectation_by_key(source, mutation, key)
    target_expectation = _expectation_by_key(target, mutation, key)
    if source_expectation.mode is ExpectationMode.LITERAL:
        mutated = _replace_literal(
            query,
            target=target_expectation.value,
            source=source_expectation.value,
        )
    else:
        mutated = _replace_fragment(
            query,
            target=str(target_expectation.value),
            source=str(source_expectation.value),
        )
    if normalized_query_checksum(mutated) == normalized_query_checksum(query):
        raise TraceBenchError("semantic mutation did not change the query")
    if _expectation_present(mutated, target_expectation):
        raise TraceBenchError("target expectation remained after mutation")
    if not _expectation_present(mutated, source_expectation):
        raise TraceBenchError("source expectation is absent after mutation")
    return mutated


def _expectation_by_key(
    case: TraceCase,
    mutation: MutationKind,
    key: str,
) -> SemanticExpectation:
    """ケースから指定した意味要素を一つ返す。"""

    matches = [
        item
        for item in semantic_expectations(case)
        if item.mutation_kind is mutation and item.key == key
    ]
    if len(matches) != 1:
        raise TraceBenchError(f"expected one semantic expectation for {key}")
    return matches[0]


def _expectation_present(query: str, expectation: SemanticExpectation) -> bool:
    """意味要素の期待値がSQLに現れるか確認する。"""

    if expectation.mode is ExpectationMode.FRAGMENT:
        return _compact_sql(str(expectation.value)) in _compact_sql(query)
    try:
        expression = parse_one(query, read="sqlite")
    except ParseError:
        return False
    return any(
        _literal_matches(literal, expectation.value)
        for literal in expression.find_all(exp.Literal)
    )


def _replace_literal(
    query: str,
    *,
    target: str | int | float,
    source: str | int | float,
) -> str:
    """SQL AST中で一致するリテラルをすべて置換する。"""

    expression = parse_one(query, read="sqlite")
    replacement_count = 0

    def transform(node: exp.Expression) -> exp.Expression:
        """一致するLiteralを型を保って置換する。"""

        nonlocal replacement_count
        if isinstance(node, exp.Literal) and _literal_matches(node, target):
            replacement_count += 1
            if isinstance(source, str):
                return exp.Literal.string(source)
            return exp.Literal.number(str(source))
        return node

    mutated = expression.transform(transform)
    if replacement_count == 0:
        raise TraceBenchError("target literal was not found")
    return mutated.sql(dialect="sqlite", pretty=False)


def _replace_fragment(query: str, *, target: str, source: str) -> str:
    """生成注釈のSQL断片を同じキーの更新前断片へ置換する。"""

    if target in query:
        return query.replace(target, source)
    pattern = re.compile(re.escape(target), re.IGNORECASE)
    mutated, count = pattern.subn(source, query)
    if count == 0:
        raise TraceBenchError("target SQL fragment was not found")
    return mutated


def _literal_matches(literal: exp.Literal, value: str | int | float) -> bool:
    """SQL Literalと注釈値を型に応じて比較する。"""

    if isinstance(value, str):
        return literal.is_string and str(literal.this).casefold() == value.casefold()
    if literal.is_string:
        return False
    try:
        return float(str(literal.this)) == float(value)
    except ValueError:
        return False


def _compact_sql(value: str) -> str:
    """SQL断片の空白と大文字小文字を正規化する。"""

    return re.sub(r"\s+", "", value).casefold().rstrip(";")


def _mutated_provenance(tables: Sequence[str]) -> list[str]:
    """実在テーブル名だけを使って誤った来歴集合を作る。"""

    if len(tables) >= 2:
        return list(tables[1:])
    decoy = "admissions" if "admissions" not in tables else "patients"
    return sorted([*tables, decoy])


def _case_by_id(cases: Sequence[TraceCase], case_id: str) -> TraceCase:
    """ケースIDに一致する個票を一つ返す。"""

    matches = [case for case in cases if case.case_id == case_id]
    if len(matches) != 1:
        raise TraceBenchError(f"expected one case for {case_id}")
    return matches[0]


def _unique_issues(issues: Iterable[ValidationIssue]) -> list[ValidationIssue]:
    """同じ問題コードと局在の重複を除く。"""

    unique: dict[tuple[str, str, MutationKind | None], ValidationIssue] = {}
    for issue in issues:
        unique[(issue.code, issue.layer, issue.mutation_kind)] = issue
    return list(unique.values())


def _model_checksum(model: BaseModel) -> str:
    """モデルの正規化JSONからチェックサムを返す。"""

    return sha256_text(
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _safe_rate(numerator: int, denominator: int) -> float:
    """分母が0なら0を返す割合計算を行う。"""

    return numerator / denominator if denominator else 0.0
