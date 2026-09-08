"""Adversarial checks for the bounded generated-update evaluation, without APIs."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from interactive_ehr.evaluation.generated_update_pilot import (
    Case,
    Interface,
    Target,
    audit_artifact,
    check_contract,
    create_database,
    evaluate,
    execute,
    expected_rows,
    make_cases,
    make_rows,
    prepare_inputs,
    reference_interface,
    reference_sql,
    summarize,
)


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Freeze seven independent synthetic database states once for this module."""
    path = tmp_path_factory.mktemp("generated-pilot") / "inputs"
    prepare_inputs(path)
    return path


def change_sql(artifact: Interface, sql: str, index: int = 0) -> Interface:
    """Copy an artifact while mutating exactly one query for an adversarial test."""
    changed = artifact.model_copy(deep=True)
    changed.queries[index].sql = sql
    return changed


def test_reference_matches_independent_python_interpretation(inputs: Path) -> None:
    """Check both independently implemented expected-result paths for all cases/states."""
    for case in make_cases():
        for state in range(7):
            assert execute(
                reference_sql(case.target), inputs / f"state_{state}.sqlite"
            )[1] == expected_rows(case.target, make_rows(state))
        assert (
            check_contract(
                reference_interface(case.target), case.target, inputs, (0, 1, 2)
            )
            == []
        )
        assert (
            audit_artifact(reference_interface(case.target), case.target, inputs) == []
        )


def test_reference_string_is_not_needed_by_contract(
    inputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure the contract never falls back to reference SQL or its compiler."""
    artifact = reference_interface(Target(days=7))

    def forbidden_reference(target: Target) -> str:
        """Fail any accidental oracle use during contract validation."""
        raise AssertionError("runtime accessed reference SQL")

    monkeypatch.setattr(
        "interactive_ehr.evaluation.generated_update_pilot.reference_sql",
        forbidden_reference,
    )
    assert check_contract(artifact, Target(days=7), inputs, (0, 1, 2)) == []


def test_valid_alternative_is_accepted_without_string_match(inputs: Path) -> None:
    """Accept an independently executed subquery form while the strict baseline rejects."""
    case = make_cases()[0]
    artifact = reference_interface(case.target)
    sql = artifact.queries[0].sql
    # Move the WHERE relation into a subquery while retaining the outer ordering.
    prefix, ordering = sql.rsplit(" ORDER BY ", 1)
    alternative = change_sql(
        artifact, f"SELECT * FROM ({prefix}) WHERE 1=1 ORDER BY {ordering}"
    )
    result = evaluate(case, alternative.model_dump_json(), inputs)
    assert result["audit_valid"] is True
    assert result["accepted"] == {
        "structure": True,
        "reference": False,
        "one_state": True,
        "three_states": True,
    }


@pytest.mark.parametrize(
    "before,after",
    [
        ("SYN_A", "SYN_B"),
        ("weight", "pulse"),
        (">=", ">"),
        (" ASC", " DESC"),
        ("AS value", "+ 1 AS value"),
    ],
)
def test_execution_valid_faults_are_detected(
    inputs: Path, before: str, after: str
) -> None:
    """Detect wrong patient, measure, boundary, order and result value after valid execution."""
    case = make_cases()[0]
    artifact = reference_interface(case.target)
    altered = change_sql(artifact, artifact.queries[0].sql.replace(before, after))
    result = evaluate(case, altered.model_dump_json(), inputs)
    assert result["accepted"]["structure"] is True
    assert result["accepted"]["three_states"] is False
    assert result["audit_valid"] is False


def test_unrequested_widget_change_is_detected(inputs: Path) -> None:
    """Catch an unchanged companion widget accidentally following a patient switch."""
    case = make_cases()[4]
    artifact = reference_interface(case.target)
    altered = change_sql(artifact, artifact.queries[1].sql.replace("SYN_A", "SYN_B"), 1)
    assert check_contract(altered, case.target, inputs, (0, 1, 2))


def test_wrong_binding_and_hidden_unit_are_detected(inputs: Path) -> None:
    """Inspect display wiring and visible units even with otherwise correct SQL."""
    case = make_cases()[0]
    artifact = reference_interface(case.target)
    artifact.widgets[0].data_key = "stable_data"
    artifact.widgets[0].columns = ["observed_at", "value"]
    result = evaluate(case, artifact.model_dump_json(), inputs)
    assert result["accepted"]["structure"] is True
    assert result["accepted"]["three_states"] is False
    assert result["audit_valid"] is False


def test_second_state_exposes_data_dependent_error(inputs: Path) -> None:
    """Show why passing one finite database is not semantic equivalence."""
    case = make_cases()[2]
    artifact = reference_interface(case.target)
    sql = artifact.queries[0].sql
    # State 0 weights are integral; other states contain fractional weights.
    altered = change_sql(
        artifact, sql.replace("value AS value", "CAST(value AS INTEGER) AS value")
    )
    result = evaluate(case, altered.model_dump_json(), inputs)
    assert result["accepted"]["one_state"] is True
    assert result["accepted"]["three_states"] is False
    assert result["audit_valid"] is False


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM measurements",
        "DROP TABLE measurements",
        "SELECT * FROM sqlite_master",
        "ATTACH DATABASE ':memory:' AS attached",
        "SELECT load_extension('missing')",
        "SELECT * FROM measurements; DELETE FROM measurements",
    ],
)
def test_generated_sql_cannot_write_or_access_external_resources(
    inputs: Path, sql: str
) -> None:
    """Reject unsafe or multi-statement SQL at the isolated execution boundary."""
    with pytest.raises(sqlite3.Error):
        execute(sql, inputs / "state_0.sqlite")


def test_bad_response_remains_in_denominator(inputs: Path) -> None:
    """Count malformed model output as an evaluated failure without repairing it."""
    case = make_cases()[0]
    malformed = evaluate(case, "not JSON", inputs)
    valid = evaluate(case, reference_interface(case.target).model_dump_json(), inputs)
    result = summarize([malformed, valid])
    assert result["n"] == 2
    assert result["parse_errors"] == 1
    assert result["audit_invalid"] == 1


def test_expensive_query_stops_at_instruction_budget(inputs: Path) -> None:
    """Abort a read-only Cartesian product before it can consume unbounded CPU."""
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        execute(
            "SELECT COUNT(*) FROM measurements a, measurements b, measurements c, measurements d",
            inputs / "state_0.sqlite",
        )


def test_preparation_never_overwrites(inputs: Path, tmp_path: Path) -> None:
    """Refuse accidental replacement of an existing frozen input or database."""
    with pytest.raises(FileExistsError):
        prepare_inputs(inputs)
    path = tmp_path / "existing.sqlite"
    create_database(make_rows(0), path)
    with pytest.raises(FileExistsError):
        create_database(make_rows(0), path)


def test_requested_unit_conversion_retains_missing_values(inputs: Path) -> None:
    """Check converted values and units without silently imputing missing rows."""
    target = Target(days=7, grams=True)
    rows = execute(reference_sql(target), inputs / "state_0.sqlite")[1]
    assert any(row[1] is None for row in rows)
    assert all(row[2] == "g" for row in rows)
    assert not check_contract(reference_interface(target), target, inputs, (0, 1, 2))


def test_identical_fixture_does_not_prove_all_sql_semantics(inputs: Path) -> None:
    """Document finite-suite limitation with a constant tailored to all frozen states."""
    case = Case(id="limitation", family="limitation", request="", target=Target())
    artifact = reference_interface(case.target)
    # This agrees on all frozen states but would fail if a weight exceeded 9999 kg.
    artifact.queries[0].sql = artifact.queries[0].sql.replace(
        "value AS value", "CASE WHEN value > 9999 THEN 0 ELSE value END AS value"
    )
    assert (
        evaluate(case, artifact.model_dump_json(), inputs)["accepted"]["three_states"]
        is True
    )


def test_real_streamlit_renderer_uses_query_result(inputs: Path) -> None:
    """Inspect data rendered by the actual repository widget implementation."""
    from streamlit.testing.v1 import AppTest

    def app(raw: str, database: str) -> None:
        """Render only the supplied synthetic interface inside Streamlit AppTest."""
        from pathlib import Path
        from interactive_ehr.evaluation.generated_update_pilot import (
            Interface,
            render_interface,
        )

        render_interface(Interface.model_validate_json(raw), Path(database))

    artifact = reference_interface(Target(days=7))
    at = AppTest.from_function(
        app, args=(artifact.model_dump_json(), str(inputs / "state_0.sqlite"))
    ).run(timeout=15)
    assert not at.exception
    assert not at.warning
    assert len(at.dataframe) == 2
    assert len(at.dataframe[0].value) == len(
        expected_rows(Target(days=7), make_rows(0))
    )


def test_real_chart_renderer_uses_declared_axes(inputs: Path) -> None:
    """Verify the supported chart path through the production widget renderer."""
    from streamlit.testing.v1 import AppTest

    def app(raw: str, database: str) -> None:
        """Render a chart plus unchanged table for AppTest inspection."""
        from pathlib import Path
        from interactive_ehr.evaluation.generated_update_pilot import (
            Interface,
            render_interface,
        )

        render_interface(Interface.model_validate_json(raw), Path(database))

    artifact = reference_interface(Target(kind="line_chart"))
    at = AppTest.from_function(
        app, args=(artifact.model_dump_json(), str(inputs / "state_0.sqlite"))
    ).run(timeout=15)
    assert not at.exception
    assert not at.warning
    assert len(at.get("vega_lite_chart")) == 1
    assert "observed_at" in at.get("vega_lite_chart")[0].proto.spec
    assert "kg" in at.get("vega_lite_chart")[0].proto.spec
