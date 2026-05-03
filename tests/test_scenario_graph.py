"""Scenario graph model and renderer tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import interactive_ehr.scenario_graph as scenario_graph
from interactive_ehr.sample_scenarios import get_chronic_disease_graph_scenario
from interactive_ehr.scenario_graph import (
    DataNode,
    DataNodeGenerationPlan,
    GraphEdge,
    ScenarioGraph,
    ScenarioGraphGenerationPlan,
    TaskNodeGenerationPlan,
    TaskNode,
    WidgetNodeGenerationPlan,
    WidgetNode,
    generate_scenario_graph_incrementally,
    generate_scenario_graph,
    parse_scenario_graph_json,
    render_scenario_graph,
)
from interactive_ehr.widgets import MarkdownSpec, TableSpec, WidgetType
from tests.test_renderer import FakeContainer, FakeStreamlit


def _minimal_graph() -> ScenarioGraph:
    return ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                order=1,
                widget_ids=["widget_1"],
            )
        ],
        data_nodes=[
            DataNode(
                id="data_1",
                context_key="rows",
                data_type="list",
                description="rows",
                primary_fields=["name"],
            )
        ],
        widget_nodes=[
            WidgetNode(
                id="widget_1",
                widget=TableSpec(data_key="rows"),
                data_node_ids=["data_1"],
            )
        ],
        edges=[
            GraphEdge(
                source_id="sample",
                target_id="task_1",
                edge_type="scenario_to_task",
            ),
            GraphEdge(
                source_id="task_1",
                target_id="widget_1",
                edge_type="task_to_widget",
            ),
            GraphEdge(
                source_id="widget_1",
                target_id="data_1",
                edge_type="widget_to_data",
            ),
        ],
    )


def test_scenario_graph_validates_widget_union() -> None:
    graph = ScenarioGraph.model_validate(_minimal_graph().model_dump(mode="json"))

    assert isinstance(graph.widget_nodes[0].widget, TableSpec)
    assert graph.edges[0].edge_type == "scenario_to_task"


def test_parse_scenario_graph_json_accepts_valid_json() -> None:
    graph = _minimal_graph()

    parsed = parse_scenario_graph_json(graph.model_dump_json())

    assert parsed == graph


def test_parse_scenario_graph_json_rejects_invalid_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_scenario_graph_json("{")


def test_parse_scenario_graph_json_rejects_schema_errors() -> None:
    with pytest.raises(ValidationError):
        parse_scenario_graph_json('{"id": "x"}')


def test_render_scenario_graph_uses_task_tabs_and_widget_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(scenario_graph, "st", fake)
    render_widget_mock = MagicMock()
    monkeypatch.setattr(scenario_graph, "render_widget", render_widget_mock)

    graph = _minimal_graph()
    render_scenario_graph(graph, {"rows": [{"name": "A"}]})

    assert fake.calls[0].name == "tabs"
    assert fake.calls[0].args == (["確認"],)
    render_widget_mock.assert_called_once_with(
        graph.widget_nodes[0].widget,
        {"rows": [{"name": "A"}]},
    )


def test_render_scenario_graph_warns_for_missing_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(scenario_graph, "st", fake)
    render_widget_mock = MagicMock()
    monkeypatch.setattr(scenario_graph, "render_widget", render_widget_mock)
    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                widget_ids=["missing_widget", "widget_1"],
            )
        ],
        data_nodes=[
            DataNode(
                id="data_1",
                context_key="missing_context",
                data_type="list",
                description="missing",
            )
        ],
        widget_nodes=[
            WidgetNode(
                id="widget_1",
                widget=MarkdownSpec(body="body"),
                data_node_ids=["missing_data", "data_1"],
            )
        ],
    )

    render_scenario_graph(graph, {})

    warnings = [call.args[0] for call in fake.calls if call.name == "warning"]
    assert len(warnings) == 3
    assert "missing_widget" in warnings[0]
    assert "missing_data" in warnings[1]
    assert "missing_context" in warnings[2]
    render_widget_mock.assert_called_once()


def test_render_scenario_graph_can_suppress_missing_reference_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(scenario_graph, "st", fake)
    render_widget_mock = MagicMock()
    monkeypatch.setattr(scenario_graph, "render_widget", render_widget_mock)
    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                widget_ids=["missing_widget", "widget_1"],
            )
        ],
        widget_nodes=[
            WidgetNode(
                id="widget_1",
                widget=MarkdownSpec(body="body"),
                data_node_ids=["missing_data"],
            )
        ],
    )

    render_scenario_graph(
        graph,
        {},
        show_missing_reference_warnings=False,
    )

    assert [call.name for call in fake.calls] == ["tabs"]
    render_widget_mock.assert_called_once()


def test_chronic_disease_graph_scenario_builds_valid_graph() -> None:
    graph, context = get_chronic_disease_graph_scenario()

    validated = ScenarioGraph.model_validate(graph.model_dump(mode="json"))

    assert validated.id == "chronic_disease_outpatient"
    assert validated.tasks[0].widget_ids
    assert "recent_labs" in context


def test_generate_scenario_graph_passes_schema_and_context_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="changed", title="確認", widget_ids=[]),
        DataNode(id="changed", context_key="bad", data_type="list", description="rows"),
        WidgetNode(
            id="changed",
            widget=TableSpec(data_key="rows"),
            data_node_ids=[],
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))

    result = generate_scenario_graph("検査を見たい", {"rows": []})

    assert result.id == "generated"
    assert result.tasks[0].id == "task_1"
    assert result.data_nodes[0].context_key == "rows"
    assert result.widget_nodes[0].id == "widget_1"
    call_args = client.generate.call_args.args
    assert "rows" in call_args[0]
    assert call_args[1] is WidgetNode


def test_generate_scenario_graph_incrementally_yields_partial_graphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="changed", title="確認", widget_ids=[]),
        DataNode(id="changed", context_key="bad", data_type="list", description="rows"),
        WidgetNode(
            id="changed",
            widget=TableSpec(data_key="rows"),
            data_node_ids=[],
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))

    events = list(generate_scenario_graph_incrementally("検査を見たい", {"rows": []}))

    assert [event.status for event in events] == [
        "started",
        "task",
        "data",
        "widget",
        "completed",
    ]
    assert events[1].graph.tasks[0].id == "task_1"
    assert events[2].graph.data_nodes[0].id == "data_1"
    assert events[3].graph.widget_nodes[0].id == "widget_1"
    final_graph = events[-1].graph
    assert final_graph.edges == [
        GraphEdge(
            source_id="generated",
            target_id="task_1",
            edge_type="scenario_to_task",
        ),
        GraphEdge(
            source_id="task_1",
            target_id="widget_1",
            edge_type="task_to_widget",
        ),
        GraphEdge(
            source_id="widget_1",
            target_id="data_1",
            edge_type="widget_to_data",
        ),
    ]
    assert client.generate.call_count == 4


def test_generate_scenario_graph_incrementally_keeps_partial_graph_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="task_1", title="確認", widget_ids=[]),
        RuntimeError("boom"),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))

    events = list(generate_scenario_graph_incrementally("検査を見たい", {"rows": []}))

    assert [event.status for event in events] == ["started", "task", "failed"]
    assert events[-1].graph.tasks[0].id == "task_1"
    assert events[-1].graph.data_nodes == []
    assert "data node 'data_1'" in events[-1].message


class _MiniStreamlit(FakeStreamlit):
    def tabs(self, *args: Any, **kwargs: Any) -> list[FakeContainer]:
        return super().tabs(*args, **kwargs)


def _minimal_generation_plan() -> ScenarioGraphGenerationPlan:
    return ScenarioGraphGenerationPlan(
        id="generated",
        title="generated",
        tasks=[
            TaskNodeGenerationPlan(
                id="task_1",
                title="確認",
                order=1,
                widget_ids=["widget_1"],
            )
        ],
        data_nodes=[
            DataNodeGenerationPlan(
                id="data_1",
                context_key="rows",
                data_type="list",
                description="rows",
                primary_fields=["name"],
            )
        ],
        widget_nodes=[
            WidgetNodeGenerationPlan(
                id="widget_1",
                task_id="task_1",
                widget_type=WidgetType.TABLE,
                data_node_ids=["data_1"],
            )
        ],
    )
