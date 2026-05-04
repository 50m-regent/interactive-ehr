"""Task graph models, rendering, and Gemini generation helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Iterator, Literal

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.llm import GeminiMixin
from interactive_ehr.models.registry import (
    DEFAULT_FAKE_ROWS,
    build_dwh_context_for_model_names,
    dwh_context_key,
    dwh_field_names,
    has_dwh_model,
    iter_dwh_model_info,
)
from interactive_ehr.widgets import AnyWidget, WidgetType
from interactive_ehr.widgets.renderer import render_widget


class TaskNode(BaseModel):
    """A clinical task that owns an ordered set of widgets."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="タスクID")
    title: str = Field(description="タブに表示するタスク名")
    description: str | None = Field(None, description="タスクの説明")
    order: int = Field(0, description="表示順")
    widget_ids: list[str] = Field(default_factory=list, description="関連ウィジェットID")


class DataNode(BaseModel):
    """A context data item referenced by widgets."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="データノードID")
    context_key: str = Field(description="固定サンプル context のキー")
    model_name: str | None = Field(None, description="参照するDWH Pydanticモデル名")
    data_type: str = Field(description="データ種別")
    description: str = Field(description="データ内容の説明")
    primary_fields: list[str] = Field(
        default_factory=list,
        description="表形式データなどの主要フィールド",
    )


class WidgetNode(BaseModel):
    """A graph node wrapping an existing WidgetSpec."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="ウィジェットノードID")
    title: str | None = Field(None, description="ウィジェットの表示上の説明")
    widget: AnyWidget = Field(description="既存 WidgetSpec")
    data_node_ids: list[str] = Field(
        default_factory=list,
        description="参照するデータノードID",
    )


class GraphEdge(BaseModel):
    """An explicit graph relation."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(description="始点ノードID")
    target_id: str = Field(description="終点ノードID")
    edge_type: Literal["scenario_to_task", "task_to_widget", "widget_to_data"] = (
        Field(description="関係種別")
    )


class ScenarioGraph(BaseModel):
    """Scenario-level task graph used to render the EHR UI."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="シナリオID")
    title: str = Field(description="シナリオ名")
    description: str | None = Field(None, description="シナリオ説明")
    tasks: list[TaskNode] = Field(default_factory=list)
    data_nodes: list[DataNode] = Field(default_factory=list)
    widget_nodes: list[WidgetNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TaskNodeGenerationPlan(BaseModel):
    """Planned task node identity used for incremental generation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="生成する task node ID")
    title: str = Field(description="タブに表示するタスク名")
    description: str | None = Field(None, description="タスクの説明")
    order: int = Field(0, description="表示順")
    widget_ids: list[str] = Field(default_factory=list, description="関連 widget node ID")


class DataNodeGenerationPlan(BaseModel):
    """Planned data node identity used for incremental generation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="生成する data node ID")
    model_name: str = Field(description="参照するDWH Pydanticモデル名")
    context_key: str | None = Field(None, description="DWH fake context のキー")
    data_type: str = Field(description="データ種別")
    description: str = Field(description="データ内容の説明")
    primary_fields: list[str] = Field(default_factory=list, description="主要フィールド")


class WidgetNodeGenerationPlan(BaseModel):
    """Planned widget node identity used for incremental generation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="生成する widget node ID")
    task_id: str = Field(description="この widget を表示する task node ID")
    title: str | None = Field(None, description="ウィジェットの表示上の説明")
    widget_type: WidgetType = Field(description="生成する WidgetSpec の widget_type")
    data_node_ids: list[str] = Field(default_factory=list, description="参照する data node ID")


class ScenarioGraphGenerationPlan(BaseModel):
    """Small plan that controls node-by-node ScenarioGraph generation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="シナリオID")
    title: str = Field(description="シナリオ名")
    description: str | None = Field(None, description="シナリオ説明")
    tasks: list[TaskNodeGenerationPlan] = Field(default_factory=list)
    data_nodes: list[DataNodeGenerationPlan] = Field(default_factory=list)
    widget_nodes: list[WidgetNodeGenerationPlan] = Field(default_factory=list)


class ScenarioGraphGenerationEvent(BaseModel):
    """Progress event emitted while incrementally generating a ScenarioGraph."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    status: Literal["started", "task", "data", "widget", "completed", "failed"]
    message: str
    graph: ScenarioGraph
    node_id: str | None = None
    context: dict[str, object] = Field(default_factory=dict)


def parse_scenario_graph_json(json_text: str) -> ScenarioGraph:
    """Parse JSON text into a validated ScenarioGraph."""

    data = json.loads(json_text)
    return ScenarioGraph.model_validate(data)


def render_scenario_graph(
    graph: ScenarioGraph,
    context: Mapping[str, object],
    *,
    show_missing_reference_warnings: bool = True,
) -> None:
    """Render a ScenarioGraph as Streamlit task tabs.

    Broken references are reported as warnings so the rest of the graph remains
    inspectable while editing or generating JSON.
    """

    data_by_id = {node.id: node for node in graph.data_nodes}
    widget_by_id = {node.id: node for node in graph.widget_nodes}
    tasks = sorted(graph.tasks, key=lambda task: (task.order, task.id))

    if not tasks:
        st.warning("タスクグラフに task がありません。")
        return

    tab_handles = st.tabs([task.title for task in tasks])
    for tab, task in zip(tab_handles, tasks, strict=True):
        with tab:
            if task.description:
                st.caption(task.description)
            for widget_id in task.widget_ids:
                widget_node = widget_by_id.get(widget_id)
                if widget_node is None:
                    if show_missing_reference_warnings:
                        st.warning(
                            f"task '{task.id}' が存在しない widget '{widget_id}' を参照しています。"
                        )
                    continue

                if show_missing_reference_warnings:
                    _warn_for_data_references(widget_node, data_by_id, context)
                render_widget(widget_node.widget, context)


def build_dwh_context_for_graph(
    graph: ScenarioGraph,
    *,
    n: int = DEFAULT_FAKE_ROWS,
) -> dict[str, object]:
    """Build display context from DWH fake data for data nodes in ``graph``."""

    return build_dwh_context_for_model_names(
        [
            data_node.model_name
            for data_node in graph.data_nodes
            if data_node.model_name is not None
        ],
        n=n,
    )


def generate_scenario_graph(
    prompt: str,
    context: Mapping[str, object],
) -> ScenarioGraph:
    """Generate a ScenarioGraph using Gemini structured output."""

    final_graph: ScenarioGraph | None = None
    failed_message: str | None = None
    for event in generate_scenario_graph_incrementally(prompt, context):
        final_graph = event.graph
        if event.status == "failed":
            failed_message = event.message
            break
    if failed_message is not None:
        raise RuntimeError(failed_message)
    if final_graph is None:
        raise RuntimeError("ScenarioGraph を生成できませんでした。")
    return final_graph


def generate_scenario_graph_incrementally(
    prompt: str,
    context: Mapping[str, object],
) -> Iterator[ScenarioGraphGenerationEvent]:
    """Generate a ScenarioGraph node by node, yielding partial graphs."""

    client = _ScenarioGraphGenerator()
    try:
        plan = client.generate(
            _build_generation_plan_prompt(prompt, context),
            ScenarioGraphGenerationPlan,
        )
    except Exception as exc:
        empty_graph = ScenarioGraph(id="generated_scenario", title="生成中")
        yield ScenarioGraphGenerationEvent(
            status="failed",
            message=f"生成計画の作成に失敗しました: {exc}",
            graph=empty_graph,
        )
        return

    graph = ScenarioGraph(
        id=plan.id,
        title=plan.title,
        description=plan.description,
    )
    generated_context: dict[str, object] = {}
    yield ScenarioGraphGenerationEvent(
        status="started",
        message="生成計画を作成しました。",
        graph=graph,
        context=generated_context,
    )

    for task_plan in plan.tasks:
        try:
            task = client.generate(
                _build_task_node_prompt(prompt, context, plan, task_plan, graph),
                TaskNode,
            )
            task = _normalize_task_node(task, task_plan)
            graph = _append_task_node(graph, task)
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"task node '{task_plan.id}' の生成に失敗しました: {exc}",
                graph=graph,
                node_id=task_plan.id,
                context=generated_context,
            )
            return
        yield ScenarioGraphGenerationEvent(
            status="task",
            message=f"task node '{task.id}' を生成しました。",
            graph=graph,
            node_id=task.id,
            context=generated_context,
        )

    for data_plan in plan.data_nodes:
        try:
            data_node = _build_data_node_from_plan(data_plan)
            graph = _append_data_node(graph, data_node)
            generated_context = build_dwh_context_for_graph(graph)
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"data node '{data_plan.id}' の生成に失敗しました: {exc}",
                graph=graph,
                node_id=data_plan.id,
                context=generated_context,
            )
            return
        yield ScenarioGraphGenerationEvent(
            status="data",
            message=f"data node '{data_node.id}' ({data_node.model_name}) を生成しました。",
            graph=graph,
            node_id=data_node.id,
            context=generated_context,
        )

    for widget_plan in plan.widget_nodes:
        try:
            widget_node = client.generate(
                _build_widget_node_prompt(prompt, context, plan, widget_plan, graph),
                WidgetNode,
            )
            widget_node = _normalize_widget_node(widget_node, widget_plan)
            graph = _append_widget_node(graph, widget_node, plan)
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"widget node '{widget_plan.id}' の生成に失敗しました: {exc}",
                graph=graph,
                node_id=widget_plan.id,
                context=generated_context,
            )
            return
        yield ScenarioGraphGenerationEvent(
            status="widget",
            message=f"widget node '{widget_node.id}' を生成しました。",
            graph=graph,
            node_id=widget_node.id,
            context=generated_context,
        )

    graph = graph.model_copy(update={"edges": _build_edges(graph)})
    yield ScenarioGraphGenerationEvent(
        status="completed",
        message="タスクグラフを生成しました。",
        graph=ScenarioGraph.model_validate(graph.model_dump(mode="json")),
        context=generated_context,
    )


class _ScenarioGraphGenerator(GeminiMixin):
    """Concrete Gemini client for scenario graph generation."""


def _warn_for_data_references(
    widget_node: WidgetNode,
    data_by_id: Mapping[str, DataNode],
    context: Mapping[str, object],
) -> None:
    for data_node_id in widget_node.data_node_ids:
        data_node = data_by_id.get(data_node_id)
        if data_node is None:
            st.warning(
                f"widget '{widget_node.id}' が存在しない data node "
                f"'{data_node_id}' を参照しています。"
            )
            continue
        if data_node.context_key not in context:
            st.warning(
                f"data node '{data_node.id}' の context_key "
                f"'{data_node.context_key}' が表示コンテキストに存在しません。"
            )


def _build_generation_prompt(
    user_prompt: str,
    context: Mapping[str, object],
) -> str:
    dwh_summary = _build_dwh_model_prompt_section()
    widget_types = "\n".join(f"- {widget_type.value}" for widget_type in WidgetType)
    return f"""\
あなたは電子カルテ UI のタスクグラフを設計するアシスタントです。
ユーザーの要望を、ScenarioGraph JSON として出力してください。

制約:
- 出力は ScenarioGraph スキーマに一致する JSON のみ。
- widget は既存 WidgetSpec の discriminated union です。
- widget.widget_type は下記の利用可能な値だけを使ってください。
- データ本体、患者名、検査値、処方内容、カルテ本文などの実データ値をJSONに埋め込まないでください。
- data_nodes.model_name は下記のDWHモデル名だけを使ってください。
- data_nodes.context_key は必ず dwh_{{model_name}} にしてください。
- 各 widget の data_key は生成済み data node の context_key だけを参照してください。
- chart/table/dataframe widget の x/y/column_order は、参照先DWHモデルのフィールド名だけを使ってください。
- scenario_to_task, task_to_widget, widget_to_data の edges を明示してください。
- task.widget_ids はそのタスクで表示する widget node ID を表示順に並べてください。
- 存在しない task/widget/data ID を参照しないでください。

利用可能なDWHモデルと主要フィールド:
{dwh_summary}

利用可能な widget_type:
{widget_types}

ユーザー要望:
{user_prompt}
"""


def _build_generation_plan_prompt(
    user_prompt: str,
    context: Mapping[str, object],
) -> str:
    dwh_summary = _build_dwh_model_prompt_section()
    widget_types = "\n".join(f"- {widget_type.value}" for widget_type in WidgetType)
    return f"""\
あなたは電子カルテ UI のタスクグラフ生成計画を作るアシスタントです。
ユーザーの要望を、ScenarioGraphGenerationPlan JSON として出力してください。

制約:
- ここでは node の中身を詳細生成せず、生成順とIDだけを計画してください。
- tasks は表示順に並べてください。
- 各 task.widget_ids は、その task に後で生成する widget node ID を表示順に並べてください。
- data_nodes.model_name は下記のDWHモデル名だけを使ってください。
- data_nodes.context_key を出す場合は必ず dwh_{{model_name}} にしてください。省略しても構いません。
- データ本体、患者名、検査値、処方内容、カルテ本文などの実データ値をJSONに埋め込まないでください。
- chart/table/dataframe widget の x/y/column_order は参照先DWHモデルのフィールド名だけを使ってください。
- widget_nodes.task_id は既存 task ID、widget_nodes.data_node_ids は既存 data node ID だけを参照してください。
- widget_nodes.widget_type は下記 widget_type だけを使ってください。
- ID は英数字とアンダースコアで安定した値にしてください。

利用可能なDWHモデルと主要フィールド:
{dwh_summary}

利用可能な widget_type:
{widget_types}

ユーザー要望:
{user_prompt}
"""


def _build_task_node_prompt(
    user_prompt: str,
    context: Mapping[str, object],
    plan: ScenarioGraphGenerationPlan,
    task_plan: TaskNodeGenerationPlan,
    graph: ScenarioGraph,
) -> str:
    return _build_node_prompt(
        user_prompt,
        context,
        plan,
        graph,
        "TaskNode",
        task_plan.model_dump(mode="json"),
    )


def _build_data_node_prompt(
    user_prompt: str,
    context: Mapping[str, object],
    plan: ScenarioGraphGenerationPlan,
    data_plan: DataNodeGenerationPlan,
    graph: ScenarioGraph,
) -> str:
    return _build_node_prompt(
        user_prompt,
        context,
        plan,
        graph,
        "DataNode",
        data_plan.model_dump(mode="json"),
    )


def _build_widget_node_prompt(
    user_prompt: str,
    context: Mapping[str, object],
    plan: ScenarioGraphGenerationPlan,
    widget_plan: WidgetNodeGenerationPlan,
    graph: ScenarioGraph,
) -> str:
    return _build_node_prompt(
        user_prompt,
        context,
        plan,
        graph,
        "WidgetNode",
        widget_plan.model_dump(mode="json"),
    )


def _build_node_prompt(
    user_prompt: str,
    context: Mapping[str, object],
    plan: ScenarioGraphGenerationPlan,
    graph: ScenarioGraph,
    node_type: str,
    node_plan: object,
) -> str:
    context_summary = _build_context_prompt_section_from_graph(graph)
    return f"""\
あなたは電子カルテ UI のタスクグラフをノード単位で生成するアシスタントです。
指定された計画に一致する {node_type} JSON だけを出力してください。

制約:
- node_plan の id と参照関係を変更しないでください。
- データ本体、患者名、検査値、処方内容、カルテ本文などの実データ値をJSONに埋め込まないでください。
- DataNode は node_plan.model_name のDWHモデルだけを参照してください。
- WidgetNode の data_key は生成済み data node の context_key だけを使ってください。
- chart/table/dataframe widget の x/y/column_order は参照先DWHモデルのフィールド名だけを使ってください。
- WidgetNode の widget.widget_type は node_plan.widget_type と一致させてください。
- 現在の partial graph と矛盾しない node を生成してください。

生成済み data node の context key と列:
{context_summary}

全体計画:
{plan.model_dump_json(indent=2)}

現在の partial graph:
{graph.model_dump_json(indent=2)}

生成する node_plan:
{json.dumps(node_plan, ensure_ascii=False, indent=2)}

ユーザー要望:
{user_prompt}
"""


def _build_dwh_model_prompt_section(*, max_fields_per_model: int = 12) -> str:
    lines: list[str] = []
    for model_info in iter_dwh_model_info():
        field_names = _select_prompt_field_names(
            [field.name for field in model_info.fields],
            max_fields=max_fields_per_model,
        )
        suffix = ""
        if len(model_info.fields) > len(field_names):
            suffix = f", ... ({len(model_info.fields)} fields)"
        description = f" - {model_info.description}" if model_info.description else ""
        lines.append(
            f"- {model_info.name}{description} "
            f"(context_key: {dwh_context_key(model_info.name)}, "
            f"fields: {', '.join(field_names)}{suffix})"
        )
    return "\n".join(lines)


def _select_prompt_field_names(
    field_names: list[str],
    *,
    max_fields: int,
) -> list[str]:
    generic_prefixes = ("キー",)
    generic_names = {
        "ROW_ID",
        "親ROW_ID",
        "件数",
        "シーケンスID",
        "トランザクション名",
        "ETL更新日",
        "ETL更新時刻",
        "施設コード",
        "施設名",
        "患者ID",
        "患者番号",
    }
    preferred = [
        field_name
        for field_name in field_names
        if field_name not in generic_names
        and not field_name.startswith(generic_prefixes)
        and not field_name.endswith("コード")
    ]
    selected = preferred[:max_fields]
    if len(selected) < max_fields:
        selected.extend(
            field_name
            for field_name in field_names
            if field_name not in selected
        )
    return selected[:max_fields]


def _build_context_prompt_section_from_graph(graph: ScenarioGraph) -> str:
    if not graph.data_nodes:
        return "- まだ生成済み data node はありません。"
    lines: list[str] = []
    for data_node in graph.data_nodes:
        if data_node.model_name is None:
            lines.append(
                f"- {data_node.context_key}{_describe_context_columns_from_fields(data_node.primary_fields)}"
            )
            continue
        lines.append(
            f"- {data_node.context_key} "
            f"(model_name: {data_node.model_name}, "
            f"columns: {', '.join(dwh_field_names(data_node.model_name))})"
        )
    return "\n".join(lines)


def _describe_context_columns_from_fields(fields: list[str]) -> str:
    if not fields:
        return ""
    return f" (columns: {', '.join(fields)})"


def _build_context_prompt_section(context: Mapping[str, object]) -> str:
    return "\n".join(
        f"- {key}{_describe_context_columns(value)}"
        for key, value in sorted(context.items())
    )


def _describe_context_columns(value: object) -> str:
    columns = _extract_context_columns(value)
    if not columns:
        return ""
    return f" (columns: {', '.join(columns)})"


def _extract_context_columns(value: object) -> list[str]:
    dataframe_columns = getattr(value, "columns", None)
    if dataframe_columns is not None:
        return [str(column) for column in dataframe_columns]
    if isinstance(value, list):
        columns: list[str] = []
        seen: set[str] = set()
        for row in value:
            if not isinstance(row, Mapping):
                continue
            for column in row:
                column_name = str(column)
                if column_name not in seen:
                    seen.add(column_name)
                    columns.append(column_name)
        return columns
    return []


def _normalize_task_node(
    task: TaskNode,
    plan: TaskNodeGenerationPlan,
) -> TaskNode:
    return TaskNode(
        id=plan.id,
        title=task.title or plan.title,
        description=task.description if task.description is not None else plan.description,
        order=plan.order,
        widget_ids=plan.widget_ids,
    )


def _normalize_data_node(
    data_node: DataNode,
    plan: DataNodeGenerationPlan,
) -> DataNode:
    return DataNode(
        id=plan.id,
        context_key=plan.context_key or dwh_context_key(plan.model_name),
        model_name=plan.model_name,
        data_type=data_node.data_type or plan.data_type,
        description=data_node.description or plan.description,
        primary_fields=data_node.primary_fields or plan.primary_fields,
    )


def _build_data_node_from_plan(plan: DataNodeGenerationPlan) -> DataNode:
    if not has_dwh_model(plan.model_name):
        raise ValueError(f"未定義のDWHモデルです: {plan.model_name}")
    field_names = dwh_field_names(plan.model_name)
    context_key = dwh_context_key(plan.model_name)
    if plan.context_key is not None and plan.context_key != context_key:
        raise ValueError(
            f"data node '{plan.id}' の context_key は '{context_key}' である必要があります。"
        )
    return DataNode(
        id=plan.id,
        context_key=context_key,
        model_name=plan.model_name,
        data_type="dataframe",
        description=plan.description,
        primary_fields=plan.primary_fields or field_names,
    )


def _normalize_widget_node(
    widget_node: WidgetNode,
    plan: WidgetNodeGenerationPlan,
) -> WidgetNode:
    widget_dump = widget_node.widget.model_dump(mode="json")
    widget_dump["widget_type"] = plan.widget_type
    return WidgetNode(
        id=plan.id,
        title=widget_node.title if widget_node.title is not None else plan.title,
        widget=widget_dump,
        data_node_ids=plan.data_node_ids,
    )


def _append_task_node(graph: ScenarioGraph, task: TaskNode) -> ScenarioGraph:
    tasks = [existing for existing in graph.tasks if existing.id != task.id]
    tasks.append(task)
    tasks = sorted(tasks, key=lambda node: (node.order, node.id))
    return ScenarioGraph.model_validate(
        graph.model_copy(
            update={
                "tasks": tasks,
                "edges": _build_edges_for_parts(graph.id, tasks, graph.widget_nodes),
            }
        ).model_dump(mode="json")
    )


def _append_data_node(graph: ScenarioGraph, data_node: DataNode) -> ScenarioGraph:
    data_nodes = [existing for existing in graph.data_nodes if existing.id != data_node.id]
    data_nodes.append(data_node)
    return ScenarioGraph.model_validate(
        graph.model_copy(update={"data_nodes": data_nodes}).model_dump(mode="json")
    )


def _append_widget_node(
    graph: ScenarioGraph,
    widget_node: WidgetNode,
    plan: ScenarioGraphGenerationPlan,
) -> ScenarioGraph:
    widget_node = _drop_unknown_data_references(widget_node, graph)
    widget_nodes = [existing for existing in graph.widget_nodes if existing.id != widget_node.id]
    widget_nodes.append(widget_node)
    tasks = _ensure_task_references_widget(graph.tasks, widget_node.id, plan)
    return ScenarioGraph.model_validate(
        graph.model_copy(
            update={
                "tasks": tasks,
                "widget_nodes": widget_nodes,
                "edges": _build_edges_for_parts(graph.id, tasks, widget_nodes),
            }
        ).model_dump(mode="json")
    )


def _ensure_task_references_widget(
    tasks: list[TaskNode],
    widget_id: str,
    plan: ScenarioGraphGenerationPlan,
) -> list[TaskNode]:
    widget_plan = next(
        (candidate for candidate in plan.widget_nodes if candidate.id == widget_id),
        None,
    )
    if widget_plan is None:
        return tasks
    updated: list[TaskNode] = []
    for task in tasks:
        if task.id != widget_plan.task_id or widget_id in task.widget_ids:
            updated.append(task)
            continue
        updated.append(task.model_copy(update={"widget_ids": [*task.widget_ids, widget_id]}))
    return sorted(updated, key=lambda node: (node.order, node.id))


def _drop_unknown_data_references(
    widget_node: WidgetNode,
    graph: ScenarioGraph,
) -> WidgetNode:
    data_node_ids = {data_node.id for data_node in graph.data_nodes}
    return widget_node.model_copy(
        update={
            "data_node_ids": [
                data_node_id
                for data_node_id in widget_node.data_node_ids
                if data_node_id in data_node_ids
            ]
        }
    )


def _build_edges(graph: ScenarioGraph) -> list[GraphEdge]:
    return _build_edges_for_parts(graph.id, graph.tasks, graph.widget_nodes)


def _build_edges_for_parts(
    scenario_id: str,
    tasks: list[TaskNode],
    widget_nodes: list[WidgetNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    widget_by_id = {widget.id: widget for widget in widget_nodes}
    for task in tasks:
        edges.append(
            GraphEdge(
                source_id=scenario_id,
                target_id=task.id,
                edge_type="scenario_to_task",
            )
        )
        for widget_id in task.widget_ids:
            widget = widget_by_id.get(widget_id)
            if widget is None:
                continue
            edges.append(
                GraphEdge(
                    source_id=task.id,
                    target_id=widget.id,
                    edge_type="task_to_widget",
                )
            )
            for data_node_id in widget.data_node_ids:
                edges.append(
                    GraphEdge(
                        source_id=widget.id,
                        target_id=data_node_id,
                        edge_type="widget_to_data",
                    )
                )
    return edges
