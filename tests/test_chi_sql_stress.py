"""追加評価の独立比較、候補生成、除外、集計を合成データで検証する。"""

import sqlite3

import pytest

from interactive_ehr.evaluation.chi_sql_stress import (
    QueryFailure,
    Record,
    evaluate_case,
    exclusion_reason,
    invert_equality,
    observe,
    summarize,
    transform_query,
)
from interactive_ehr.evaluation.tracebench_ehr import TraceCase, TraceSplit


@pytest.fixture
def connection() -> sqlite3.Connection:
    """実在の患者を含まない表を作る。"""

    database = sqlite3.connect(":memory:")
    database.execute("CREATE TABLE sample (item INTEGER, score INTEGER)")
    database.executemany("INSERT INTO sample VALUES (?, ?)", [(1, 2), (1, 2), (2, 3), (2, 4)])
    return database


def test_comparison_keeps_types_duplicates_and_columns(
    connection: sqlite3.Connection,
) -> None:
    """単なる集合や数値の等値で異なる結果を同じとしない。"""

    assert observe(connection, "SELECT score FROM sample") != observe(
        connection, "SELECT DISTINCT score FROM sample"
    )
    assert observe(connection, "SELECT 1 AS n") != observe(
        connection, "SELECT 1.0 AS n"
    )
    assert observe(connection, "SELECT 1 AS n") != observe(connection, "SELECT 1 AS m")
    assert observe(connection, "SELECT score FROM sample ORDER BY score") == observe(
        connection, "SELECT score FROM sample ORDER BY score DESC"
    )


def test_wrapper_and_rejection_isolate_exact_query(
    connection: sqlite3.Connection,
) -> None:
    """結果を保つ別解の拒否と、等号反転の流出を合成例で確認する。"""

    case = TraceCase(
        case_id="synthetic",
        split=TraceSplit.TEST,
        question="synthetic question",
        query="SELECT score FROM sample WHERE item = 1",
        template="synthetic template",
        val_dict={"val_placeholder": {"patient_id": 1}},
    )
    records = {r.transform: r for r in evaluate_case(case, connection)}
    for name in ("original", "whitespace"):
        assert records[name].status == "equivalent_result"
        assert all((records[name].accepted or {}).values())
    wrapper = records["wrapper"]
    assert wrapper.status == "equivalent_result"
    assert wrapper.accepted and not wrapper.accepted["graph_contract"]
    assert wrapper.accepted["without_query_equality"]
    changed = records["invert_equality"]
    assert changed.status == "changed_result"
    assert changed.accepted and not changed.accepted["graph_contract"]
    assert changed.accepted["without_query_equality"]


@pytest.mark.parametrize(
    "query, expected",
    [
        ("SELECT * FROM x WHERE item = 1", "SELECT * FROM x WHERE item <> 1"),
        ("SELECT * FROM x WHERE 1 = item", "SELECT * FROM x WHERE 1 <> item"),
        (
            "SELECT * FROM x JOIN y ON x.a = y.a WHERE x.a = 'x=y'",
            "SELECT * FROM x JOIN y ON x.a = y.a WHERE x.a <> 'x=y'",
        ),
        ("SELECT * FROM x JOIN y ON x.a = 1", None),
        ("SELECT * FROM x WHERE a = b", None),
    ],
)
def test_mutation_preserves_original_text(query: str, expected: str | None) -> None:
    """選んだ演算子以外のSQL文字列を変えない。"""

    assert invert_equality(query) == expected


def test_exclusions() -> None:
    """読み取り、時間依存、順序未指定の上限を検査する。"""

    assert exclusion_reason("DELETE FROM x") == "not_read_only_or_parse_error"
    assert exclusion_reason("SELECT random()") == "nondeterministic_function"
    assert exclusion_reason("SELECT datetime('now')") == "nondeterministic_function"
    assert exclusion_reason("SELECT * FROM x LIMIT 1") == "limit_without_order"
    assert exclusion_reason("SELECT * FROM x ORDER BY a LIMIT 1") is None


def test_row_cap_and_sql_errors_are_not_truth_labels(
    connection: sqlite3.Connection,
) -> None:
    """実行失敗を比較結果や患者情報に変換しない。"""

    with pytest.raises(QueryFailure, match="^sql_error$"):
        observe(connection, "SELECT * FROM missing")
    with pytest.raises(QueryFailure, match="^row_cap$"):
        observe(
            connection,
            "WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<10002) SELECT n FROM x",
        )


def test_unchanged_negative_not_counted_as_invalid(
    connection: sqlite3.Connection,
) -> None:
    """結果が変わらなければ、注入操作だけで不正解と採点しない。"""

    case = TraceCase(
        case_id="empty",
        split=TraceSplit.TEST,
        question="synthetic",
        query="SELECT score FROM sample WHERE item = 99 AND score = 99",
        template="empty",
        val_dict={},
    )
    record = evaluate_case(case, connection)[-1]
    assert record.status == "unchanged_result"
    summary = summarize([record])
    group = summary["invert_equality"]
    assert group["evaluated"] == 0


def test_summary_preserves_exclusions() -> None:
    """全候補の分母を、成功したケースだけに縮めない。"""

    records = [
        Record("a", "t", "wrapper", "equivalent_result", accepted={"graph": False}),
        Record("b", "t", "wrapper", "excluded_limit_without_order"),
    ]
    assert summarize(records)["wrapper"] == {
        "attempted": 2,
        "statuses": {"equivalent_result": 1, "excluded_limit_without_order": 1},
        "evaluated": 1,
        "evaluated_templates": 1,
        "baseline_empty": 0,
        "transformed_empty": 0,
        "normalized_same": 0,
        "accepted": {"graph": 0},
        "issues": {"graph": {}},
    }


def test_wrapper_preserves_trailing_comment(connection: sqlite3.Connection) -> None:
    """行コメントが閉じ括弧を消さないよう改行を保つ。"""

    query = "SELECT score FROM sample -- example"
    transformed = transform_query(query, "wrapper")
    assert transformed is not None
    assert observe(connection, transformed) == observe(connection, query)
