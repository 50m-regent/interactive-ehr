"""Scenario graph model and renderer tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import interactive_ehr.scenario_graph as scenario_graph
from interactive_ehr.sample_scenarios import (
    get_anesthesia_preop_graph_scenario,
    get_chronic_disease_graph_scenario,
)
from interactive_ehr.scenario_graph import (
    DataNode,
    DataNodeGenerationPlan,
    ScenarioGraph,
    ScenarioGraphGenerationPlan,
    ScenarioGraphUpdateDecision,
    ScenarioGraphUpdateScope,
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
    update_scenario_graph_incrementally,
)
from interactive_ehr.widgets import (
    DataframeSpec,
    LineChartSpec,
    MarkdownSpec,
    TableSpec,
    WidgetType,
)
from tests.test_renderer import FakeContainer, FakeStreamlit


def _minimal_graph() -> ScenarioGraph:
    data_node = DataNode(
        id="data_1",
        context_key="rows",
        data_type="list",
        description="rows",
        primary_fields=["name"],
    )
    return ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                order=1,
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        widget=TableSpec(data_key="rows"),
                        data_nodes=[data_node],
                    )
                ],
            )
        ],
    )


def test_scenario_graph_validates_widget_union() -> None:
    graph = ScenarioGraph.model_validate(_minimal_graph().model_dump(mode="json"))

    assert isinstance(graph.widget_nodes[0].widget, TableSpec)
    assert graph.tasks[0].widgets[0].data_nodes[0].id == "data_1"


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


def test_render_scenario_graph_shows_chart_widget_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(scenario_graph, "st", fake)
    render_widget_mock = MagicMock()
    monkeypatch.setattr(scenario_graph, "render_widget", render_widget_mock)
    data_node = DataNode(
        id="data_1",
        context_key="trend",
        data_type="dataframe",
        description="trend",
    )
    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        title="HbA1c 推移",
                        widget=LineChartSpec(data_key="trend", x="日付", y="HbA1c"),
                        data_nodes=[data_node],
                    )
                ],
            )
        ],
    )

    render_scenario_graph(graph, {"trend": [{"日付": "2026-01-01", "HbA1c": 7.1}]})

    markdown_calls = [call for call in fake.calls if call.name == "markdown"]
    assert [call.args[0] for call in markdown_calls] == ["#### HbA1c 推移"]
    render_widget_mock.assert_called_once()


def test_render_scenario_graph_does_not_render_task_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(scenario_graph, "st", fake)
    monkeypatch.setattr(scenario_graph, "render_widget", MagicMock())

    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                description="生成処理へ渡すタスクの説明。",
            )
        ],
    )

    render_scenario_graph(graph, {})

    assert "markdown" not in [call.name for call in fake.calls]


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
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        widget=MarkdownSpec(body="body"),
                        data_nodes=[
                            DataNode(
                                id="data_1",
                                context_key="missing_context",
                                data_type="list",
                                description="missing",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    render_scenario_graph(graph, {})

    warnings = [call.args[0] for call in fake.calls if call.name == "warning"]
    assert len(warnings) == 1
    assert "missing_context" in warnings[0]
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
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        widget=MarkdownSpec(body="body"),
                        data_nodes=[
                            DataNode(
                                id="data_1",
                                context_key="missing_context",
                                data_type="list",
                                description="missing",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    render_scenario_graph(
        graph,
        {},
        show_missing_reference_warnings=False,
    )

    assert "warning" not in [call.name for call in fake.calls]
    assert "expander" in [call.name for call in fake.calls]
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
    assert validated.patient_context_key == "metric_patient_profile"
    assert [task.title for task in validated.tasks] == [
        "血圧・腎機能評価",
        "副作用・服薬確認",
        "検査に基づく処方調整",
        "生活習慣指導",
    ]
    assert "chart_bp_trend" in context
    assert "metric_latest_egfr" in context
    assert "metric_patient_material" in context


def test_anesthesia_preop_scenario_has_patient_header_and_compact_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """麻酔科デモが患者ヘッダーとスクロール可能な表を持つ。"""

    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"値": ["sample"]})),
    )

    graph, context = get_anesthesia_preop_graph_scenario()

    assert graph.patient_context_key == "header_patient_identity"
    assert "header_patient_identity" in context
    assert all(
        isinstance(widget_node.widget, DataframeSpec)
        for widget_node in graph.widget_nodes
        if widget_node.id
        in {"widget_3", "widget_4", "widget_6", "widget_7", "widget_9"}
    )


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
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
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
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
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
    assert events[2].graph.data_nodes == []
    assert events[2].context == {}
    assert events[3].graph.widget_nodes[0].id == "widget_1"
    assert "sql_data_1" in events[3].context
    final_graph = events[-1].graph
    assert final_graph.tasks[0].widgets[0].data_nodes[0].id == "data_1"
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
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
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
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )

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
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(generate_scenario_graph_incrementally("検査を見たい", {"rows": []}))

    final_graph = events[-1].graph
    assert [data_node.id for data_node in final_graph.widget_nodes[0].data_nodes] == [
        "data_1"
    ]


def test_generate_scenario_graph_incrementally_orders_widgets_by_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _multi_widget_generation_plan()

    def fake_generate(prompt: str, schema: Any) -> Any:
        if schema is ScenarioGraphGenerationPlan:
            return plan
        if schema is TaskNode:
            return TaskNode(id="task_1", title="task1", widget_ids=[])
        if schema is WidgetNodeSqlGeneration:
            widget_plan = _widget_plan_for_prompt(plan, prompt)
            return WidgetNodeSqlGeneration(
                widget_node=WidgetNode(
                    id=widget_plan.id,
                    widget=TableSpec(data_key="ignored"),
                    data_node_ids=widget_plan.data_node_ids,
                ),
                sql=f'SELECT "匿名ID" FROM "{widget_plan.id}"',
            )
        raise AssertionError(f"unexpected schema: {schema!r}")

    client = MagicMock()
    client.generate.side_effect = fake_generate
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(generate_scenario_graph_incrementally("並列確認", {}))

    widget_events = [event for event in events if event.status == "widget"]
    assert len(widget_events) == 3
    assert {event.node_id for event in widget_events} == {
        "widget_a",
        "widget_b",
        "widget_c",
    }

    final_graph = events[-1].graph
    assert [widget.id for widget in final_graph.widget_nodes] == [
        "widget_a",
        "widget_b",
        "widget_c",
    ]
    assert events[-1].status == "completed"


def test_generate_scenario_graph_incrementally_widget_failure_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _multi_widget_generation_plan()

    def fake_generate(prompt: str, schema: Any) -> Any:
        if schema is ScenarioGraphGenerationPlan:
            return plan
        if schema is TaskNode:
            return TaskNode(id="task_1", title="task1", widget_ids=[])
        if schema is WidgetNodeSqlGeneration:
            widget_plan = _widget_plan_for_prompt(plan, prompt)
            if widget_plan.id == "widget_b":
                raise RuntimeError("widget_b の生成に失敗")
            return WidgetNodeSqlGeneration(
                widget_node=WidgetNode(
                    id=widget_plan.id,
                    widget=TableSpec(data_key="ignored"),
                    data_node_ids=widget_plan.data_node_ids,
                ),
                sql=f'SELECT "匿名ID" FROM "{widget_plan.id}"',
            )
        raise AssertionError(f"unexpected schema: {schema!r}")

    client = MagicMock()
    client.generate.side_effect = fake_generate
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(generate_scenario_graph_incrementally("失敗確認", {}))

    statuses = [event.status for event in events]
    assert "failed" in statuses
    assert "completed" not in statuses
    failed_event = next(event for event in events if event.status == "failed")
    assert failed_event.node_id == "widget_b"
    assert "widget_b" in failed_event.message


def test_build_sql_context_for_graph_executes_data_node_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_mock = MagicMock(return_value=_dataframe({"匿名ID": ["P001"]}))
    monkeypatch.setattr(scenario_graph, "execute_read_sql", execute_mock)
    data_node = DataNode(
        id="data_1",
        context_key="sql_data_1",
        data_type="dataframe",
        description="sql",
        sql='SELECT "匿名ID" FROM "患者基本"',
    )
    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        widget=TableSpec(data_key="sql_data_1"),
                        data_nodes=[data_node],
                    )
                ],
            )
        ],
    )

    context = build_sql_context_for_graph(graph)

    assert "sql_data_1" in context
    execute_mock.assert_called_once_with('SELECT "匿名ID" FROM "患者基本"')


class _MiniStreamlit(FakeStreamlit):
    def tabs(self, *args: Any, **kwargs: Any) -> list[FakeContainer]:
        return super().tabs(*args, **kwargs)


def _widget_plan_for_prompt(
    plan: ScenarioGraphGenerationPlan, prompt: str
) -> WidgetNodeGenerationPlan:
    marker = "生成する node_plan:"
    node_plan_section = prompt[prompt.index(marker) :]
    for widget_plan in plan.widget_nodes:
        if f'"id": "{widget_plan.id}"' in node_plan_section:
            return widget_plan
    raise AssertionError(
        f"widget_plan not found in prompt section: {node_plan_section[:200]}"
    )


def _multi_widget_generation_plan() -> ScenarioGraphGenerationPlan:
    widget_ids = ["widget_a", "widget_b", "widget_c"]
    return ScenarioGraphGenerationPlan(
        id="multi_widget",
        title="multi_widget",
        tasks=[
            TaskNodeGenerationPlan(
                id="task_1",
                title="task1",
                order=1,
                widget_ids=widget_ids,
            )
        ],
        data_nodes=[
            DataNodeGenerationPlan(
                id=f"data_{suffix}",
                model_name="患者基本",
                data_type="dataframe",
                description="dummy",
            )
            for suffix in ("a", "b", "c")
        ],
        widget_nodes=[
            WidgetNodeGenerationPlan(
                id=widget_id,
                task_id="task_1",
                widget_type=WidgetType.TABLE,
                data_node_ids=[widget_id.replace("widget_", "data_")],
            )
            for widget_id in widget_ids
        ],
    )


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


# --- update_scenario_graph_incrementally tests ---


def test_update_incremental_scope_scenario_delegates_to_full_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ScenarioGraphUpdateDecision(scope=ScenarioGraphUpdateScope.SCENARIO)
    monkeypatch.setattr(
        scenario_graph,
        "_decide_update_scope",
        MagicMock(return_value=decision),
    )

    plan = _minimal_generation_plan()
    client = MagicMock()
    client.generate.side_effect = [
        plan,
        TaskNode(id="task_1", title="確認", widget_ids=[]),
        WidgetNodeSqlGeneration(
            widget_node=WidgetNode(
                id="widget_1",
                widget=TableSpec(data_key="ignored"),
                data_node_ids=["data_1"],
            ),
            sql='SELECT "匿名ID" FROM "患者基本"',
        ),
    ]
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(
        update_scenario_graph_incrementally(
            "全体作り直し", _minimal_graph(), {"rows": []}
        )
    )

    assert events[-1].status == "completed"
    assert events[-1].graph.id == "generated"


def test_update_incremental_scope_widget_regenerates_target_widgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph()
    decision = ScenarioGraphUpdateDecision(
        scope=ScenarioGraphUpdateScope.WIDGET,
        target_node_ids=["widget_1"],
    )
    monkeypatch.setattr(
        scenario_graph,
        "_decide_update_scope",
        MagicMock(return_value=decision),
    )

    new_widget_sql = WidgetNodeSqlGeneration(
        widget_node=WidgetNode(
            id="widget_1",
            widget=TableSpec(data_key="ignored"),
            data_node_ids=["data_1"],
        ),
        sql='SELECT "匿名ID" FROM "患者基本"',
    )
    client = MagicMock()
    client.generate.return_value = new_widget_sql
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P001"]})),
    )

    events = list(
        update_scenario_graph_incrementally("widget修正", graph, {"rows": []})
    )

    statuses = [e.status for e in events]
    assert "failed" not in statuses
    assert events[-1].status == "completed"
    widget_events = [e for e in events if e.status == "widget"]
    assert len(widget_events) == 1
    assert widget_events[0].node_id == "widget_1"


def test_update_incremental_scope_data_regenerates_sql_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_node = DataNode(
        id="data_1",
        context_key="rows",
        data_type="dataframe",
        description="rows",
        sql='SELECT "匿名ID" FROM "患者基本" LIMIT 10',
    )
    graph = ScenarioGraph(
        id="sample",
        title="sample",
        tasks=[
            TaskNode(
                id="task_1",
                title="確認",
                widgets=[
                    WidgetNode(
                        id="widget_1",
                        widget=TableSpec(data_key="rows"),
                        data_nodes=[data_node],
                    )
                ],
            )
        ],
    )
    decision = ScenarioGraphUpdateDecision(
        scope=ScenarioGraphUpdateScope.DATA,
        target_node_ids=["data_1"],
    )
    monkeypatch.setattr(
        scenario_graph,
        "_decide_update_scope",
        MagicMock(return_value=decision),
    )

    from interactive_ehr.scenario_graph import _DataSqlOnly

    client = MagicMock()
    client.generate.return_value = _DataSqlOnly(
        sql='SELECT "匿名ID" FROM "患者基本" WHERE "性別" = \'M\' LIMIT 10'
    )
    monkeypatch.setattr(
        scenario_graph, "_ScenarioGraphGenerator", MagicMock(return_value=client)
    )
    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        MagicMock(return_value=_dataframe({"匿名ID": ["P002"]})),
    )

    events = list(update_scenario_graph_incrementally("SQLだけ変更", graph, {}))

    statuses = [e.status for e in events]
    assert "failed" not in statuses
    assert events[-1].status == "completed"
    data_events = [e for e in events if e.status == "data"]
    assert len(data_events) == 1
    assert data_events[0].node_id == "data_1"
    updated_data = events[-1].graph.data_nodes[0]
    assert "M" in updated_data.sql


def test_update_incremental_scope_decision_failure_yields_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scenario_graph,
        "_decide_update_scope",
        MagicMock(side_effect=RuntimeError("Gemini判断エラー")),
    )

    graph = _minimal_graph()
    events = list(update_scenario_graph_incrementally("なにか変更", graph, {}))

    assert len(events) == 1
    assert events[0].status == "failed"
    assert "更新範囲の判断に失敗" in events[0].message


def test_update_incremental_scope_widget_missing_target_yields_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ScenarioGraphUpdateDecision(
        scope=ScenarioGraphUpdateScope.WIDGET,
        target_node_ids=["nonexistent_widget"],
    )
    monkeypatch.setattr(
        scenario_graph,
        "_decide_update_scope",
        MagicMock(return_value=decision),
    )

    events = list(
        update_scenario_graph_incrementally("存在しないwidget", _minimal_graph(), {})
    )

    statuses = [e.status for e in events]
    assert "failed" in statuses
