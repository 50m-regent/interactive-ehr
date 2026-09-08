"""Validate sequential labels, alternate SQL and checkers before any model run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from interactive_ehr.evaluation import sequential_update_pilot as pilot
from interactive_ehr.evaluation.generated_update_pilot import execute
from interactive_ehr.scenario_graph import ScenarioGraph
from interactive_ehr.widgets.chart import LineChartSpec
from interactive_ehr.widgets.display import DataframeSpec


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Prepare immutable inputs once for the pure evaluation tests."""
    path = tmp_path_factory.mktemp("sequential") / "inputs"
    pilot.prepare(path)
    return path


def conforming_event(target: pilot.SequentialTarget, inputs: Path) -> dict[str, Any]:
    """Build a known conforming graph and actual SQL context for checker calibration."""
    graph = pilot.initial_graph().model_dump(mode="json")
    main = graph["tasks"][0]["widgets"][0]
    main["data_nodes"][0]["sql"] = pilot.audit_sql(target)
    main["data_nodes"][0]["primary_fields"] = pilot.target_columns(target)
    main["widget"] = (
        LineChartSpec(data_key="main_data", x="observed_at", y="value")
        if target.kind == "line_chart"
        else DataframeSpec(
            data_key="main_data", column_order=pilot.target_columns(target)
        )
    ).model_dump(mode="json")
    validated = ScenarioGraph.model_validate(graph)
    context = {}
    for node in validated.data_nodes:
        columns, rows = execute(node.sql or "", inputs / "state_0.sqlite")
        context[node.context_key] = pd.DataFrame(rows, columns=columns)
    return {
        "status": "completed",
        "graph": graph,
        "context": pilot.pack_context(context),
    }


@pytest.mark.parametrize("step", pilot.make_steps(), ids=lambda step: step.id)
def test_all_reference_targets_match_independent_python(
    step: pilot.Step, inputs: Path
) -> None:
    """Check every cumulative target on all states, including NULLs and empty windows."""
    for state in range(7):
        rows = json.loads((inputs / f"state_{state}.json").read_text())
        actual = execute(pilot.audit_sql(step.target), inputs / f"state_{state}.sqlite")
        assert actual[0] == pilot.target_columns(step.target)
        assert pilot.same_rows(actual[1], pilot.interpret(step.target, rows))
    result = pilot.evaluate(step, conforming_event(step.target, inputs), inputs)
    assert result["audit_valid"]
    assert all(result["accepted"].values())


def test_contract_does_not_read_reference_sql(
    inputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent the tested semantic checker from secretly using the audit answer."""
    event = conforming_event(pilot.SequentialTarget(), inputs)

    def forbidden(target: pilot.SequentialTarget) -> str:
        """Fail if the execution checker consults the reference compiler."""
        raise AssertionError("audit SQL accessed")

    monkeypatch.setattr(pilot, "audit_sql", forbidden)
    assert not pilot.semantic_issues(
        ScenarioGraph.model_validate(event["graph"]),
        pilot.SequentialTarget(),
        inputs,
        (0, 1, 2),
    )


def test_simple_predicates_accept_between_and_datetime(inputs: Path) -> None:
    """Support common alternate syntax rather than testing literal string identity."""
    sql = pilot.audit_sql(pilot.SequentialTarget()).replace(
        "observed_at >= '2026-09-07 12:00:00' AND observed_at <= '2026-09-08 12:00:00'",
        "observed_at BETWEEN datetime('2026-09-08 12:00:00', '-1 days') AND '2026-09-08 12:00:00'",
    )
    assert not pilot.simple_sql_issues(
        sql, pilot.SequentialTarget(), inputs / "state_0.sqlite"
    )


def test_optional_or_predicate_is_not_mandatory(inputs: Path) -> None:
    """Do not mistake an OR branch for a patient restriction."""
    sql = pilot.audit_sql(pilot.SequentialTarget()).replace(
        "patient = 'SYN_A'", "(patient = 'SYN_A' OR patient = 'SYN_B')"
    )
    assert "predicate:patient:EQ" in pilot.simple_sql_issues(
        sql, pilot.SequentialTarget(), inputs / "state_0.sqlite"
    )


def test_simple_baseline_has_documented_arithmetic_limit(inputs: Path) -> None:
    """Keep an injected arithmetic counterexample as a test, never natural evidence."""
    target = pilot.SequentialTarget()
    sql = pilot.audit_sql(target).replace("value AS value", "value + 1 AS value")
    assert not pilot.simple_sql_issues(sql, target, inputs / "state_0.sqlite")
    graph = pilot.initial_graph().model_dump(mode="json")
    graph["tasks"][0]["widgets"][0]["data_nodes"][0]["sql"] = sql
    assert pilot.semantic_issues(
        ScenarioGraph.model_validate(graph), target, inputs, (0,)
    )


def test_count_star_is_rejected_even_when_current_values_are_complete(
    inputs: Path,
) -> None:
    """The simple baseline explicitly distinguishes non-null counts from all rows."""
    target = pilot.SequentialTarget(aggregate="count", days=7)
    sql = pilot.audit_sql(target).replace("COUNT(value)", "COUNT(*)")
    assert "count_nonnull" in pilot.simple_sql_issues(
        sql, target, inputs / "state_0.sqlite"
    )


def test_actual_cached_data_must_match_sql(inputs: Path) -> None:
    """Detect a stale result even when graph SQL satisfies all target conditions."""
    step = pilot.make_steps()[0]
    event = conforming_event(step.target, inputs)
    event["context"]["main_data"]["data"][0][1] = -999
    result = pilot.evaluate(step, event, inputs)
    assert not any(result["accepted"].values())
    assert "stale_context:main_data" in result["issues"]["structure"]


def test_companion_changes_and_failed_pipeline_are_retained(inputs: Path) -> None:
    """Reject incomplete states and semantic companion drift in the common denominator."""
    step = pilot.make_steps()[0]
    event = conforming_event(step.target, inputs)
    event["status"] = "failed"
    result = pilot.evaluate(step, event, inputs)
    assert not result["audit_valid"]
    assert not any(result["accepted"].values())
    event = conforming_event(step.target, inputs)
    event["graph"]["tasks"][0]["widgets"][1]["data_nodes"][0]["sql"] = pilot.audit_sql(
        pilot.SequentialTarget()
    )
    assert not pilot.evaluate(step, event, inputs)["audit_valid"]


def test_context_roundtrip_and_null_numeric_comparison() -> None:
    """Preserve actual cached NULLs and avoid treating missing values as numeric zero."""
    original = {"data": pd.DataFrame({"value": [1.5, None], "unit": ["kg", "kg"]})}
    packed = pilot.pack_context(original)
    assert packed["data"]["data"][1][0] is None
    restored = pilot.unpack_context(packed)
    pd.testing.assert_frame_equal(original["data"], restored["data"])
    assert not pilot.same_rows([[None]], [[0]])
    assert pilot.same_rows([[1 / 3]], [[0.333333333333333]])
