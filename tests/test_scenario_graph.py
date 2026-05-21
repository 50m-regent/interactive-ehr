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
    WidgetNodeSqlGeneration,
    WidgetNode,
    build_sql_context_for_graph,
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


def test_chronic_disease_graph_scenario_builds_valid_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    graph, context = get_chronic_disease_graph_scenario()

    validated = ScenarioGraph.model_validate(graph.model_dump(mode="json"))

    assert validated.id == "chronic_disease_outpatient"
    assert validated.tasks[0].widget_ids
    assert "chart_lab_trend" in context
    assert "metric_prescription_count" in context
    assert all(data_node.model_name is not None for data_node in validated.data_nodes)


def test_generate_scenario_graph_passes_schema_and_context_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="changed", title="確認", widget_ids=[]),
        WidgetNodeSqlGeneration(
            widget_node=WidgetNode(
                id="changed",
                widget=TableSpec(data_key="ignored"),
                data_node_ids=[],
            ),
            sql='SELECT "匿名ID" FROM "患者基本"',
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    result = generate_scenario_graph("検査を見たい", {"rows": []})

    assert result.id == "generated"
    assert result.tasks[0].id == "task_1"
    assert result.data_nodes[0].context_key == "sql_data_1"
    assert result.data_nodes[0].model_name == "患者基本"
    assert result.data_nodes[0].sql == 'SELECT "匿名ID" FROM "患者基本"'
    assert result.widget_nodes[0].id == "widget_1"
    assert result.widget_nodes[0].widget.data_key == "sql_data_1"
    call_args = client.generate.call_args.args
    assert "sql_data_1" in call_args[0]
    assert call_args[1] is WidgetNodeSqlGeneration


def test_generation_plan_prompt_includes_context_columns() -> None:
    prompt = scenario_graph._build_generation_plan_prompt(
        "腎機能を確認したい",
        {"renal_trend": [{"検査日": "2026-04-20", "eGFR": 38.2, "Cr": 1.19}]},
    )

    assert "検体検査結果" in prompt
    assert "x/y/column_order" in prompt


def test_generate_scenario_graph_incrementally_yields_partial_graphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="changed", title="確認", widget_ids=[]),
        WidgetNodeSqlGeneration(
            widget_node=WidgetNode(
                id="changed",
                widget=TableSpec(data_key="ignored"),
                data_node_ids=[],
            ),
            sql='SELECT "匿名ID" FROM "患者基本"',
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

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
    assert events[2].context == {}
    assert events[3].graph.widget_nodes[0].id == "widget_1"
    assert "sql_data_1" in events[3].context
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
    assert client.generate.call_count == 3


def test_generate_scenario_graph_incrementally_builds_context_from_widget_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="task_1", title="確認", widget_ids=[]),
        WidgetNodeSqlGeneration(
            widget_node=WidgetNode(
                id="widget_1",
                widget=TableSpec(data_key="ignored"),
                data_node_ids=[],
            ),
            sql='SELECT "匿名ID" FROM "患者基本"',
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(generate_scenario_graph_incrementally("検査を見たい", {"rows": []}))

    assert [event.status for event in events] == ["started", "task", "data", "widget", "completed"]
    assert events[-1].context["sql_data_1"] is not None


def test_generate_scenario_graph_incrementally_fails_unknown_dwh_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan().model_copy(
        update={
            "data_nodes": [
                DataNodeGenerationPlan(
                    id="data_1",
                    model_name="存在しないモデル",
                    data_type="dataframe",
                    description="missing",
                )
            ]
        }
    )
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="task_1", title="確認", widget_ids=[]),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))

    events = list(generate_scenario_graph_incrementally("検査を見たい", {}))

    assert [event.status for event in events] == ["started", "task", "failed"]
    assert events[-1].graph.tasks[0].id == "task_1"
    assert events[-1].graph.data_nodes == []
    assert "data node 'data_1'" in events[-1].message


def test_generate_scenario_graph_incrementally_drops_unknown_widget_data_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _minimal_generation_plan().model_copy(
        update={
            "widget_nodes": [
                WidgetNodeGenerationPlan(
                    id="widget_1",
                    task_id="task_1",
                    widget_type=WidgetType.TABLE,
                    data_node_ids=["data_1", "missing_data"],
                )
            ]
        }
    )
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="task_1", title="確認", widget_ids=[]),
        WidgetNodeSqlGeneration(
            widget_node=WidgetNode(
                id="widget_1",
                widget=TableSpec(data_key="ignored"),
                data_node_ids=[],
            ),
            sql='SELECT "匿名ID" FROM "患者基本"',
        ),
    ]
    monkeypatch.setattr(scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client))
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(generate_scenario_graph_incrementally("検査を見たい", {"rows": []}))

    final_graph = events[-1].graph
    assert final_graph.widget_nodes[0].data_node_ids == ["data_1"]
    assert final_graph.edges[-1] == GraphEdge(
        source_id="widget_1",
        target_id="data_1",
        edge_type="widget_to_data",
    )


def test_build_sql_context_for_graph_executes_data_node_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_mock = MagicMock(return_value=_dataframe({"匿名ID": ["P001"]}))
    monkeypatch.setattr(scenario_graph, "execute_read_sql", execute_mock)
    graph = _minimal_graph().model_copy(
        update={
            "data_nodes": [
                DataNode(
                    id="data_1",
                    context_key="sql_data_1",
                    data_type="dataframe",
                    description="sql",
                    sql='SELECT "匿名ID" FROM "患者基本"',
                )
            ]
        }
    )

    context = build_sql_context_for_graph(graph)

    assert "sql_data_1" in context
    execute_mock.assert_called_once_with('SELECT "匿名ID" FROM "患者基本"')


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
                model_name="患者基本",
                data_type="dataframe",
                description="患者基本",
                primary_fields=["匿名ID"],
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


def _dataframe(data: dict[str, list[object]]) -> Any:
    import pandas as pd

    return pd.DataFrame(data)
