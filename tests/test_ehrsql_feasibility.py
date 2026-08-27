"""EHRSQL-2024実行可能性確認のテスト。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from interactive_ehr.evaluation.ehrsql_feasibility import (
    EhrsqlCase,
    EhrsqlFeasibilityError,
    QueryOutcome,
    WidgetMapping,
    load_ehrsql_cases,
    run_ehrsql_feasibility,
    select_ehrsql_cases,
    summarize_feasibility,
    validate_read_only_query,
    write_feasibility_outputs,
)


def _case(
    case_id: str,
    *,
    template: str,
    query: str = "SELECT value FROM observations",
) -> EhrsqlCase:
    """テスト用EHRSQLケースを作る。"""

    return EhrsqlCase(
        case_id=case_id,
        split="train",
        question=f"Question {case_id}",
        query=query,
        template=template,
    )


def _create_database(path: Path) -> None:
    """テスト用SQLiteデータベースを作る。"""

    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE observations (name TEXT, value INTEGER)")
        connection.executemany(
            "INSERT INTO observations VALUES (?, ?)",
            [("alpha", 1), ("beta", 2)],
        )
        connection.commit()
    finally:
        connection.close()


def test_load_ehrsql_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    """同じケースIDが2回現れた入力を拒否する。"""

    annotated_path = tmp_path / "annotated.json"
    annotated_path.write_text(
        json.dumps(
            [
                {
                    "id": "same",
                    "question": "Question one",
                    "query": "SELECT 1",
                    "template": "Template one",
                },
                {
                    "id": "same",
                    "question": "Question two",
                    "query": "SELECT 2",
                    "template": "Template two",
                },
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(EhrsqlFeasibilityError, match="duplicate case id"):
        load_ehrsql_cases(annotated_path, split="train")


def test_select_ehrsql_cases_is_deterministic_and_template_diverse() -> None:
    """同じseedなら異なるテンプレートから同じケースを選ぶ。"""

    cases = [
        _case("a1", template="template-a"),
        _case("a2", template="template-a"),
        _case("b1", template="template-b"),
        _case("c1", template="template-c"),
        _case("none", template="template-none", query="null"),
    ]

    first = select_ehrsql_cases(cases, sample_size=3, seed=42)
    second = select_ehrsql_cases(cases, sample_size=3, seed=42)

    assert [case.case_id for case in first] == [case.case_id for case in second]
    assert len({case.template for case in first}) == 3
    assert all(case.case_id != "none" for case in first)


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE observations SET value = 3",
        "DELETE FROM observations",
        "SELECT 1; DROP TABLE observations",
    ],
)
def test_validate_read_only_query_rejects_writes(query: str) -> None:
    """書き込み文と複数文を事前に拒否する。"""

    with pytest.raises(EhrsqlFeasibilityError):
        validate_read_only_query(query)


def test_run_ehrsql_feasibility_maps_scalar_and_table(tmp_path: Path) -> None:
    """単一値をMetric、複数行列をDataframeへ割り当てる。"""

    database_path = tmp_path / "test.sqlite"
    _create_database(database_path)
    cases = [
        _case(
            "scalar",
            template="scalar-template",
            query="SELECT COUNT(*) AS observation_count FROM observations",
        ),
        _case(
            "table",
            template="table-template",
            query="SELECT name, value FROM observations ORDER BY name",
        ),
    ]

    results = run_ehrsql_feasibility(cases, database_path=database_path)

    assert [result.outcome for result in results] == [
        QueryOutcome.SUCCESS,
        QueryOutcome.SUCCESS,
    ]
    assert results[0].widget_mapping == WidgetMapping.METRIC
    assert results[1].widget_mapping == WidgetMapping.DATAFRAME
    assert all(result.graph_valid for result in results)


def test_database_authorizer_keeps_database_unchanged(tmp_path: Path) -> None:
    """WITHから始まる書き込みがSQLite authorizerで拒否される。"""

    database_path = tmp_path / "test.sqlite"
    _create_database(database_path)
    write_case = _case(
        "write",
        template="write-template",
        query=(
            "WITH replacement(value) AS (SELECT 9) "
            "UPDATE observations SET value = (SELECT value FROM replacement)"
        ),
    )

    result = run_ehrsql_feasibility([write_case], database_path=database_path)[0]

    assert result.outcome == QueryOutcome.SQL_ERROR
    connection = sqlite3.connect(database_path)
    try:
        values = connection.execute(
            "SELECT value FROM observations ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    assert values == [(1,), (2,)]


def test_outputs_exclude_questions_queries_and_values(tmp_path: Path) -> None:
    """保存成果物へ質問、SQL、患者単位の値を含めない。"""

    database_path = tmp_path / "test.sqlite"
    _create_database(database_path)
    case = EhrsqlCase(
        case_id="safe-case",
        split="train",
        question="Sensitive question text",
        query=(
            "SELECT (SELECT value FROM observations WHERE name = 'alpha') "
            "> (SELECT value FROM observations WHERE name = 'beta')"
        ),
        template="Sensitive template text",
    )
    results = run_ehrsql_feasibility([case], database_path=database_path)
    annotated_path = tmp_path / "annotated.json"
    annotated_path.write_text("[]", encoding="utf-8")
    dataset_data_path = tmp_path / "data.json"
    dataset_data_path.write_text('{"version":"train-test"}', encoding="utf-8")
    implementation_path = tmp_path / "implementation.py"
    implementation_path.write_text("pass\n", encoding="utf-8")

    output_dir = tmp_path / "results"
    write_feasibility_outputs(
        output_dir=output_dir,
        cases=[case],
        results=results,
        annotated_path=annotated_path,
        dataset_data_path=dataset_data_path,
        database_path=database_path,
        dataset_repository="https://example.test/ehrsql",
        dataset_commit="dataset-commit",
        dataset_version="train-test",
        code_commit="code-commit",
        sample_seed=42,
        query_timeout_seconds=5.0,
        max_result_rows=10_000,
        implementation_paths=[implementation_path],
    )

    combined_output = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir()
    )
    assert "Sensitive question text" not in combined_output
    assert "SELECT name, value" not in combined_output
    assert "SELECT value FROM observations" not in combined_output
    assert "alpha" not in combined_output
    assert "beta" not in combined_output
    assert "Open Database License v1.0" in combined_output

    summary = summarize_feasibility([case], results)
    assert summary.execution_success_rate == 1.0
    assert summary.graph_valid_rate == 1.0
