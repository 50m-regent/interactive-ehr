"""Task graph models, rendering, and Gemini generation helpers."""

from __future__ import annotations

import concurrent.futures
import json
from collections.abc import Mapping
from enum import Enum
from typing import Iterator, Literal, cast

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.llm import GeminiMixin
from interactive_ehr.models.database import execute_read_sql
from interactive_ehr.models.registry import (
    DEFAULT_FAKE_ROWS,
    build_dwh_context_for_model_names,
    dwh_context_key,
    dwh_field_names,
    has_dwh_model,
    iter_dwh_model_info,
)
from interactive_ehr.provenance import (
    DataProvenanceSummary,
    source_overview,
    summarize_data_nodes,
)
from interactive_ehr.widgets import AnyWidget, WidgetType
from interactive_ehr.widgets.renderer import render_widget


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
    sql: str | None = Field(None, description="このデータを取得するSELECT SQL")


class WidgetNode(BaseModel):
    """A graph node wrapping an existing WidgetSpec."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="ウィジェットノードID")
    title: str | None = Field(None, description="ウィジェットの表示上の説明")
    widget: AnyWidget = Field(description="既存 WidgetSpec")
    data_nodes: list[DataNode] = Field(
        default_factory=list,
        description="このウィジェットが参照するデータノード",
    )


class TaskNode(BaseModel):
    """A clinical task that owns an ordered set of widgets."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="タスクID")
    title: str = Field(description="タブに表示するタスク名")
    description: str | None = Field(None, description="タスクの説明")
    order: int = Field(0, description="表示順")
    widgets: list[WidgetNode] = Field(
        default_factory=list,
        description="このタスクで表示するウィジェット",
    )


class ScenarioGraph(BaseModel):
    """Scenario-level task graph used to render the EHR UI."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="シナリオID")
    title: str = Field(description="シナリオ名")
    description: str | None = Field(None, description="シナリオ説明")
    patient_context_key: str | None = Field(
        None,
        description="患者識別情報を取得する表示コンテキストのキー",
    )
    tasks: list[TaskNode] = Field(default_factory=list)

    @property
    def widget_nodes(self) -> list[WidgetNode]:
        return [widget for task in self.tasks for widget in task.widgets]

    @property
    def data_nodes(self) -> list[DataNode]:
        return [data_node for widget in self.widget_nodes for data_node in widget.data_nodes]


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


class WidgetNodeSqlGeneration(BaseModel):
    """Generated widget node and the SELECT SQL that feeds it."""

    model_config = ConfigDict(frozen=True)

    widget_node: WidgetNode = Field(description="生成した widget node")
    sql: str = Field(description="widget 専用 data node に保存するSELECT SQL")


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


class ScenarioGraphUpdateScope(str, Enum):
    SCENARIO = "scenario"
    TASK = "task"
    WIDGET = "widget"
    DATA = "data"


class ScenarioGraphUpdateDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope: ScenarioGraphUpdateScope
    target_node_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


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

    tasks = sorted(graph.tasks, key=lambda task: (task.order, task.id))

    if not tasks:
        st.warning("タスクグラフに task がありません。")
        return

    tab_handles = st.tabs([task.title for task in tasks])
    for tab, task in zip(tab_handles, tasks, strict=True):
        with tab:
            summaries = summarize_data_nodes(
                (
                    data_node
                    for widget_node in task.widgets
                    for data_node in widget_node.data_nodes
                ),
                context,
            )
            _render_task_context(task, summaries)
            for widget_node in task.widgets:
                if show_missing_reference_warnings:
                    _warn_for_data_references(widget_node, context)
                _render_widget_title(widget_node)
                render_widget(widget_node.widget, context)
            _render_provenance_panel(summaries)


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


def build_sql_context_for_graph(graph: ScenarioGraph) -> dict[str, object]:
    """Build display context by executing SQL stored in graph data nodes."""

    context: dict[str, object] = {}
    for data_node in graph.data_nodes:
        if data_node.sql is None:
            continue
        dataframe = execute_read_sql(data_node.sql)
        if data_node.data_type == "scalar":
            context[data_node.context_key] = _scalar_from_dataframe(dataframe)
        else:
            context[data_node.context_key] = dataframe
    return context


def _scalar_from_dataframe(dataframe: pd.DataFrame) -> object | None:
    if dataframe.empty:
        return None
    return dataframe.iat[0, 0]


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

    generated_data_nodes: dict[str, DataNode] = {}
    for data_plan in plan.data_nodes:
        try:
            data_node = _build_data_node_from_plan(data_plan)
            generated_data_nodes[data_node.id] = data_node
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
            message=f"data node '{data_node.id}' ({data_node.model_name}) を準備しました。",
            graph=graph,
            node_id=data_node.id,
            context=generated_context,
        )

    graph_snapshot = graph
    if plan.widget_nodes:
        max_workers = min(len(plan.widget_nodes), _WIDGET_PARALLEL_MAX_WORKERS)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_plan: dict[concurrent.futures.Future[WidgetNodeSqlGeneration], WidgetNodeGenerationPlan] = {
                executor.submit(
                    _generate_widget_sql,
                    prompt,
                    context,
                    plan,
                    widget_plan,
                    graph_snapshot,
                ): widget_plan
                for widget_plan in plan.widget_nodes
            }
            for future in concurrent.futures.as_completed(future_to_plan):
                widget_plan = future_to_plan[future]
                try:
                    widget_sql = future.result()
                    widget_node = widget_sql.widget_node
                    widget_node = _normalize_widget_node(
                        widget_node,
                        widget_plan,
                        generated_data_nodes,
                    )
                    context_key = _context_key_for_widget_node(widget_node)
                    if context_key is not None:
                        widget_node = _bind_widget_to_data_context(widget_node, context_key)
                    graph = _append_widget_node(graph, widget_node, plan)
                    graph, generated_context = _attach_widget_sql_result(
                        graph,
                        widget_node.id,
                        widget_sql.sql,
                        generated_context,
                    )
                except Exception as exc:
                    for pending in future_to_plan:
                        pending.cancel()
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
                    message=f"widget node '{widget_node.id}' とSQLを生成しました。",
                    graph=graph,
                    node_id=widget_node.id,
                    context=generated_context,
                )

    yield ScenarioGraphGenerationEvent(
        status="completed",
        message="タスクグラフを生成しました。",
        graph=ScenarioGraph.model_validate(graph.model_dump(mode="json")),
        context=generated_context,
    )


def update_scenario_graph_incrementally(
    user_prompt: str,
    existing_graph: ScenarioGraph,
    existing_context: Mapping[str, object],
) -> Iterator[ScenarioGraphGenerationEvent]:
    """Regenerate only the nodes Gemini decides need updating in existing_graph."""

    try:
        decision = _decide_update_scope(user_prompt, existing_graph)
    except Exception as exc:
        yield ScenarioGraphGenerationEvent(
            status="failed",
            message=f"更新範囲の判断に失敗しました: {exc}",
            graph=existing_graph,
            context=dict(existing_context),
        )
        return

    if decision.scope == ScenarioGraphUpdateScope.SCENARIO:
        yield from generate_scenario_graph_incrementally(user_prompt, existing_context)
        return

    if decision.scope == ScenarioGraphUpdateScope.TASK:
        yield from _update_task_subtrees(
            user_prompt, existing_graph, existing_context, decision.target_node_ids
        )
        return

    if decision.scope == ScenarioGraphUpdateScope.WIDGET:
        yield from _update_widgets(
            user_prompt, existing_graph, existing_context, decision.target_node_ids
        )
        return

    if decision.scope == ScenarioGraphUpdateScope.DATA:
        yield from _update_data_nodes(
            user_prompt, existing_graph, existing_context, decision.target_node_ids
        )
        return


class _ScenarioGraphGenerator(GeminiMixin):
    """Concrete Gemini client for scenario graph generation."""


_WIDGET_PARALLEL_MAX_WORKERS = 8


def _generate_widget_sql(
    user_prompt: str,
    context: Mapping[str, object],
    plan: ScenarioGraphGenerationPlan,
    widget_plan: WidgetNodeGenerationPlan,
    graph_snapshot: ScenarioGraph,
) -> WidgetNodeSqlGeneration:
    """Generate a single WidgetNodeSqlGeneration using a fresh Gemini client.

    Each worker uses its own generator so callers do not depend on shared client
    thread safety.
    """

    client = _ScenarioGraphGenerator()
    return client.generate(
        _build_widget_node_prompt(user_prompt, context, plan, widget_plan, graph_snapshot),
        WidgetNodeSqlGeneration,
    )


def _warn_for_data_references(
    widget_node: WidgetNode,
    context: Mapping[str, object],
) -> None:
    """表示コンテキストに存在しない参照を警告する。"""

    for data_node in widget_node.data_nodes:
        if data_node.context_key not in context:
            st.warning(
                f"data node '{data_node.id}' の context_key "
                f"'{data_node.context_key}' が表示コンテキストに存在しません。"
            )


def _render_widget_title(widget_node: WidgetNode) -> None:
    """表やグラフの内容を示す見出しを表示する。"""

    if widget_node.title is None:
        return
    if widget_node.widget.widget_type not in {
        WidgetType.DATAFRAME,
        WidgetType.TABLE,
        WidgetType.JSON,
        WidgetType.LINE_CHART,
        WidgetType.BAR_CHART,
    }:
        return
    st.markdown(f"#### {widget_node.title}")


def _render_task_context(
    task: TaskNode,
    summaries: list[DataProvenanceSummary],
) -> None:
    """タスクの目的と主要な情報源をタブ上部へ表示する。"""

    if task.description is not None:
        st.markdown(task.description)
    if not summaries:
        return
    source_text, latest_text = source_overview(summaries)
    st.caption(f"情報源: {source_text} ｜ 最終データ日時: {latest_text}")


def _render_provenance_panel(summaries: list[DataProvenanceSummary]) -> None:
    """情報源、データ時点、取得条件を折りたたみ表示する。"""

    if not summaries:
        return
    with st.expander("情報源と取得条件", expanded=False):
        st.caption(
            "表示内容ごとの情報源、最終データ日時、件数、欠損状態を確認できます。"
        )
        st.dataframe(
            [summary.as_row() for summary in summaries],
            hide_index=True,
            width="stretch",
        )
        sql_summaries = [summary for summary in summaries if summary.sql is not None]
        if not sql_summaries:
            return
        st.markdown("##### 取得SQL")
        st.caption(
            "ローカルDWHへ実行した読み取り専用SQLです。患者の表示値はJSONへ埋め込んでいません。"
        )
        for summary in sql_summaries:
            st.markdown(f"{summary.description}")
            st.code(summary.sql, language="sql", wrap_lines=True)


def _decide_update_scope(
    user_prompt: str,
    graph: ScenarioGraph,
) -> ScenarioGraphUpdateDecision:
    client = _ScenarioGraphGenerator()
    return client.generate(
        _build_update_scope_prompt(user_prompt, graph),
        ScenarioGraphUpdateDecision,
    )


def _update_task_subtrees(
    user_prompt: str,
    graph: ScenarioGraph,
    context: Mapping[str, object],
    target_task_ids: list[str],
) -> Iterator[ScenarioGraphGenerationEvent]:
    working_graph = graph
    working_context = dict(context)

    yield ScenarioGraphGenerationEvent(
        status="started",
        message=f"task subtree を再生成します: {', '.join(target_task_ids)}",
        graph=working_graph,
        context=working_context,
    )

    for task_id in target_task_ids:
        task = next((t for t in working_graph.tasks if t.id == task_id), None)
        if task is None:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"task '{task_id}' が見つかりません。",
                graph=working_graph,
                context=working_context,
            )
            return

        client = _ScenarioGraphGenerator()
        try:
            task_plan = client.generate(
                _build_task_subtree_plan_prompt(user_prompt, context, working_graph, task),
                _TaskSubtreePlan,
            )
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"task '{task_id}' の再生成計画に失敗しました: {exc}",
                graph=working_graph,
                node_id=task_id,
                context=working_context,
            )
            return

        old_context_keys = {
            data_node.context_key for widget in task.widgets for data_node in widget.data_nodes
        }
        working_context = {
            k: v for k, v in working_context.items() if k not in old_context_keys
        }

        new_task = _normalize_task_node(
            TaskNode(
                id=task_plan.id,
                title=task_plan.title,
                description=task_plan.description,
                order=task_plan.order,
            ),
            TaskNodeGenerationPlan(
                id=task_plan.id,
                title=task_plan.title,
                description=task_plan.description,
                order=task_plan.order,
                widget_ids=task_plan.widget_ids,
            ),
        )
        working_graph = _replace_task_node(working_graph, new_task)

        generated_data_nodes: dict[str, DataNode] = {}
        for data_plan in task_plan.data_nodes:
            try:
                data_node = _build_data_node_from_plan(data_plan)
                generated_data_nodes[data_node.id] = data_node
            except Exception as exc:
                yield ScenarioGraphGenerationEvent(
                    status="failed",
                    message=f"data node '{data_plan.id}' の生成に失敗しました: {exc}",
                    graph=working_graph,
                    node_id=data_plan.id,
                    context=working_context,
                )
                return

        graph_snapshot = working_graph
        compat_plan = _subtree_plan_to_compat(task_plan)

        if task_plan.widget_nodes:
            max_workers = min(len(task_plan.widget_nodes), _WIDGET_PARALLEL_MAX_WORKERS)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_plan: dict[
                    concurrent.futures.Future[WidgetNodeSqlGeneration],
                    WidgetNodeGenerationPlan,
                ] = {
                    executor.submit(
                        _generate_widget_sql,
                        user_prompt,
                        context,
                        compat_plan,
                        widget_plan,
                        graph_snapshot,
                    ): widget_plan
                    for widget_plan in task_plan.widget_nodes
                }
                for future in concurrent.futures.as_completed(future_to_plan):
                    widget_plan = future_to_plan[future]
                    try:
                        widget_sql = future.result()
                        widget_node = widget_sql.widget_node
                        widget_node = _normalize_widget_node(
                            widget_node,
                            widget_plan,
                            generated_data_nodes,
                        )
                        context_key = _context_key_for_widget_node(widget_node)
                        if context_key is not None:
                            widget_node = _bind_widget_to_data_context(widget_node, context_key)
                        working_graph = _append_widget_node(working_graph, widget_node, compat_plan)
                        working_graph, working_context = _attach_widget_sql_result(
                            working_graph, widget_node.id, widget_sql.sql, working_context
                        )
                    except Exception as exc:
                        for pending in future_to_plan:
                            pending.cancel()
                        yield ScenarioGraphGenerationEvent(
                            status="failed",
                            message=f"widget '{widget_plan.id}' の生成に失敗しました: {exc}",
                            graph=working_graph,
                            node_id=widget_plan.id,
                            context=working_context,
                        )
                        return
                    yield ScenarioGraphGenerationEvent(
                        status="widget",
                        message=f"widget '{widget_node.id}' を再生成しました。",
                        graph=working_graph,
                        node_id=widget_node.id,
                        context=working_context,
                    )

    yield ScenarioGraphGenerationEvent(
        status="completed",
        message="task subtree の再生成が完了しました。",
        graph=ScenarioGraph.model_validate(working_graph.model_dump(mode="json")),
        context=working_context,
    )


def _update_widgets(
    user_prompt: str,
    graph: ScenarioGraph,
    context: Mapping[str, object],
    target_widget_ids: list[str],
) -> Iterator[ScenarioGraphGenerationEvent]:
    working_graph = graph
    working_context = dict(context)

    yield ScenarioGraphGenerationEvent(
        status="started",
        message=f"widget を再生成します: {', '.join(target_widget_ids)}",
        graph=working_graph,
        context=working_context,
    )

    target_widget_nodes = [w for w in graph.widget_nodes if w.id in target_widget_ids]
    if not target_widget_nodes:
        yield ScenarioGraphGenerationEvent(
            status="failed",
            message=f"対象 widget が見つかりません: {', '.join(target_widget_ids)}",
            graph=working_graph,
            context=working_context,
        )
        return

    existing_plans = [
        WidgetNodeGenerationPlan(
            id=w.id,
            task_id=next(
                (t.id for t in graph.tasks if any(widget.id == w.id for widget in t.widgets)),
                graph.tasks[0].id if graph.tasks else "",
            ),
            title=w.title,
            widget_type=w.widget.widget_type,
            data_node_ids=[data_node.id for data_node in w.data_nodes],
        )
        for w in target_widget_nodes
    ]
    compat_plan = ScenarioGraphGenerationPlan(
        id=graph.id,
        title=graph.title,
        description=graph.description,
        tasks=[
            TaskNodeGenerationPlan(
                id=t.id,
                title=t.title,
                description=t.description,
                order=t.order,
                widget_ids=[widget.id for widget in t.widgets],
            )
            for t in graph.tasks
        ],
        data_nodes=[
            DataNodeGenerationPlan(
                id=dn.id,
                model_name=dn.model_name or "",
                context_key=dn.context_key,
                data_type=dn.data_type,
                description=dn.description,
                primary_fields=dn.primary_fields,
            )
            for dn in graph.data_nodes
        ],
        widget_nodes=existing_plans,
    )

    graph_snapshot = working_graph
    existing_data_nodes = {data_node.id: data_node for data_node in graph.data_nodes}
    max_workers = min(len(existing_plans), _WIDGET_PARALLEL_MAX_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_plan: dict[
            concurrent.futures.Future[WidgetNodeSqlGeneration],
            WidgetNodeGenerationPlan,
        ] = {
            executor.submit(
                _generate_widget_sql,
                user_prompt,
                context,
                compat_plan,
                widget_plan,
                graph_snapshot,
            ): widget_plan
            for widget_plan in existing_plans
        }
        for future in concurrent.futures.as_completed(future_to_plan):
            widget_plan = future_to_plan[future]
            try:
                widget_sql = future.result()
                widget_node = widget_sql.widget_node
                widget_node = _normalize_widget_node(widget_node, widget_plan, existing_data_nodes)
                context_key = _context_key_for_widget_node(widget_node)
                if context_key is not None:
                    widget_node = _bind_widget_to_data_context(widget_node, context_key)
                working_graph = _append_widget_node(working_graph, widget_node, compat_plan)
                working_graph, working_context = _attach_widget_sql_result(
                    working_graph, widget_node.id, widget_sql.sql, working_context
                )
            except Exception as exc:
                for pending in future_to_plan:
                    pending.cancel()
                yield ScenarioGraphGenerationEvent(
                    status="failed",
                    message=f"widget '{widget_plan.id}' の再生成に失敗しました: {exc}",
                    graph=working_graph,
                    node_id=widget_plan.id,
                    context=working_context,
                )
                return
            yield ScenarioGraphGenerationEvent(
                status="widget",
                message=f"widget '{widget_node.id}' を再生成しました。",
                graph=working_graph,
                node_id=widget_node.id,
                context=working_context,
            )

    yield ScenarioGraphGenerationEvent(
        status="completed",
        message="widget の再生成が完了しました。",
        graph=ScenarioGraph.model_validate(working_graph.model_dump(mode="json")),
        context=working_context,
    )


def _update_data_nodes(
    user_prompt: str,
    graph: ScenarioGraph,
    context: Mapping[str, object],
    target_data_ids: list[str],
) -> Iterator[ScenarioGraphGenerationEvent]:
    working_graph = graph
    working_context = dict(context)

    yield ScenarioGraphGenerationEvent(
        status="started",
        message=f"data node SQL を再生成します: {', '.join(target_data_ids)}",
        graph=working_graph,
        context=working_context,
    )

    for data_id in target_data_ids:
        data_node = next((dn for dn in working_graph.data_nodes if dn.id == data_id), None)
        if data_node is None:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"data node '{data_id}' が見つかりません。",
                graph=working_graph,
                node_id=data_id,
                context=working_context,
            )
            return

        client = _ScenarioGraphGenerator()
        try:
            sql = client.generate(
                _build_data_sql_prompt(user_prompt, data_node, working_graph),
                _DataSqlOnly,
            ).sql
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"data node '{data_id}' のSQL再生成に失敗しました: {exc}",
                graph=working_graph,
                node_id=data_id,
                context=working_context,
            )
            return

        try:
            dataframe = execute_read_sql(sql)
        except Exception as exc:
            yield ScenarioGraphGenerationEvent(
                status="failed",
                message=f"data node '{data_id}' のSQL実行に失敗しました: {exc}",
                graph=working_graph,
                node_id=data_id,
                context=working_context,
            )
            return

        updated_node = data_node.model_copy(
            update={
                "sql": sql,
                "primary_fields": [str(col) for col in dataframe.columns],
            }
        )
        working_graph = _replace_data_node(working_graph, updated_node)
        next_context = dict(working_context)
        next_context[updated_node.context_key] = dataframe
        working_context = next_context

        yield ScenarioGraphGenerationEvent(
            status="data",
            message=f"data node '{data_id}' のSQLを再生成しました。",
            graph=working_graph,
            node_id=data_id,
            context=working_context,
        )

    yield ScenarioGraphGenerationEvent(
        status="completed",
        message="data node SQL の再生成が完了しました。",
        graph=ScenarioGraph.model_validate(working_graph.model_dump(mode="json")),
        context=working_context,
    )


class _TaskSubtreePlan(BaseModel):
    """Minimal plan for regenerating a single task subtree."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str | None = None
    order: int = 0
    widget_ids: list[str] = Field(default_factory=list)
    data_nodes: list[DataNodeGenerationPlan] = Field(default_factory=list)
    widget_nodes: list[WidgetNodeGenerationPlan] = Field(default_factory=list)


class _DataSqlOnly(BaseModel):
    """Holds only the regenerated SQL for a data node."""

    model_config = ConfigDict(frozen=True)

    sql: str


def _replace_task_node(graph: ScenarioGraph, task: TaskNode) -> ScenarioGraph:
    tasks = [task if t.id == task.id else t for t in graph.tasks]
    if task not in tasks:
        tasks.append(task)
    tasks = sorted(tasks, key=lambda t: (t.order, t.id))
    return ScenarioGraph.model_validate(
        graph.model_copy(update={"tasks": tasks}).model_dump(mode="json")
    )


def _subtree_plan_to_compat(plan: _TaskSubtreePlan) -> ScenarioGraphGenerationPlan:
    return ScenarioGraphGenerationPlan(
        id=plan.id,
        title=plan.title,
        description=plan.description,
        tasks=[
            TaskNodeGenerationPlan(
                id=plan.id,
                title=plan.title,
                description=plan.description,
                order=plan.order,
                widget_ids=plan.widget_ids,
            )
        ],
        data_nodes=plan.data_nodes,
        widget_nodes=plan.widget_nodes,
    )


def _build_update_scope_prompt(user_prompt: str, graph: ScenarioGraph) -> str:
    graph_summary = graph.model_dump_json(indent=2)
    task_list = "\n".join(f"- id={t.id}, title={t.title}" for t in graph.tasks)
    widget_list = "\n".join(f"- id={w.id}, type={w.widget.widget_type}" for w in graph.widget_nodes)
    data_list = "\n".join(
        f"- id={dn.id}, context_key={dn.context_key}" for dn in graph.data_nodes
    )
    return f"""\
あなたは電子カルテ UI のタスクグラフ更新範囲を判断するアシスタントです。
現在のグラフ構造と修正要望を読み、どの階層のノードを再生成すべきかを ScenarioGraphUpdateDecision で出力してください。

判断ルール:
- 要望が「タスクの構成・並び・全体方針」に関わるなら scope=scenario（target_node_ids は空）
- 特定タスクの中身を変える要望なら scope=task で target_node_ids にそのtask ID
- 特定 widget の種別・データ参照・SQL だけを変えるなら scope=widget で target_node_ids にその widget ID
- データの取り方（SQL）だけを変えたい場合は scope=data で target_node_ids にその data node ID

現在のタスク一覧:
{task_list}

現在の widget 一覧:
{widget_list}

現在の data node 一覧:
{data_list}

現在のグラフ (詳細):
{graph_summary}

ユーザー要望:
{user_prompt}
"""


def _build_task_subtree_plan_prompt(
    user_prompt: str,
    context: Mapping[str, object],
    graph: ScenarioGraph,
    task: TaskNode,
) -> str:
    dwh_summary = _build_dwh_model_prompt_section()
    widget_types = "\n".join(f"- {wt.value}" for wt in WidgetType)
    return f"""\
あなたは電子カルテ UI のタスクサブツリーを再設計するアシスタントです。
指定された task を作り直すための _TaskSubtreePlan JSON を出力してください。

制約:
- task.id は "{task.id}" を維持してください。
- task.order は {task.order} を維持してください。
- widget_ids は新しい widget node ID を表示順に並べてください。
- widget node ごとに専用 data node を 1 つ計画してください。
- data_nodes.context_key は省略してください。アプリが sql_{{id}} を割り当てます。
- widget_nodes.task_id は "{task.id}" にしてください。
- data_nodes.model_name は下記のDWHモデル名だけを使ってください。
- widget_nodes.widget_type は下記の値だけを使ってください。

利用可能なDWHモデルと主要フィールド:
{dwh_summary}

利用可能な widget_type:
{widget_types}

現在の task:
{task.model_dump_json(indent=2)}

現在のグラフ (参照用):
{graph.model_dump_json(indent=2)}

ユーザー要望:
{user_prompt}
"""


def _build_data_sql_prompt(
    user_prompt: str,
    data_node: DataNode,
    graph: ScenarioGraph,
) -> str:
    return f"""\
あなたは電子カルテ DWH のクエリ作成アシスタントです。
以下の data node 用の SELECT SQL を生成し、_DataSqlOnly JSON として出力してください。

制約:
- 読み取り専用の SELECT のみ使ってください。INSERT/UPDATE/DELETE/DDL は禁止です。
- テーブル名と列名はダブルクォートしてください。例: SELECT "匿名ID" FROM "患者基本" LIMIT 20
- 既存の context_key "{data_node.context_key}" 用の SQL を生成してください。

対象 data node:
{data_node.model_dump_json(indent=2)}

現在のグラフ (参照用):
{graph.model_dump_json(indent=2)}

ユーザー要望:
{user_prompt}
"""


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
- 各 TaskNode は widgets に表示順の WidgetNode を含めてください。
- 各 WidgetNode は data_nodes に参照する DataNode を含めてください。
- DataNode.model_name は下記のDWHモデル名だけを使ってください。
- DataNode.context_key は必ず dwh_{{model_name}} にしてください。
- 各 widget の data_key は生成済み data node の context_key だけを参照してください。
- chart/table/dataframe widget の x/y/column_order は、参照先DWHモデルのフィールド名だけを使ってください。
- edges、トップレベル widget_nodes、トップレベル data_nodes は出力しないでください。

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
- widget node ごとに専用 data node を1つ計画してください。
- data_nodes.context_key は省略してください。アプリが sql_{{data_node_id}} を割り当てます。
- データ本体、患者名、検査値、処方内容、カルテ本文などの実データ値をJSONに埋め込まないでください。
- chart/table/dataframe widget の x/y/column_order はSQLで取得する列名だけを使ってください。
- widget_nodes.task_id は既存 task ID、widget_nodes.data_node_ids は専用 data node ID だけを1つ参照してください。
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
    context_summary = _build_context_prompt_section_from_graph_or_plan(graph, plan)
    output_contract = (
        "- WidgetNode 生成では WidgetNodeSqlGeneration JSON を出力してください。\n"
        "- WidgetNodeSqlGeneration.sql は widget 専用 data node のための単一SELECT文にしてください。\n"
        "- SQLではテーブル名と列名をダブルクォートしてください。例: SELECT \"匿名ID\" FROM \"患者基本\" LIMIT 20\n"
        "- SQLは読み取り専用のSELECTだけにしてください。INSERT/UPDATE/DELETE/DDLは使わないでください。"
        if node_type == "WidgetNode"
        else "- 指定された node type のJSONだけを出力してください。"
    )
    output_type = "WidgetNodeSqlGeneration" if node_type == "WidgetNode" else node_type
    return f"""\
あなたは電子カルテ UI のタスクグラフをノード単位で生成するアシスタントです。
指定された計画に一致する {output_type} JSON だけを出力してください。

制約:
- node_plan の id と参照関係を変更しないでください。
- データ本体、患者名、検査値、処方内容、カルテ本文などの実データ値をJSONに埋め込まないでください。
- DataNode は node_plan.model_name のDWHモデルだけを参照してください。SQLやデータ本体は入れないでください。
{output_contract}
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


def _build_context_prompt_section_from_graph_or_plan(
    graph: ScenarioGraph,
    plan: ScenarioGraphGenerationPlan,
) -> str:
    if graph.data_nodes:
        return _build_context_prompt_section_from_graph(graph)
    if not plan.data_nodes:
        return "- まだ生成済み data node はありません。"
    lines: list[str] = []
    for data_plan in plan.data_nodes:
        context_key = data_plan.context_key or f"sql_{data_plan.id}"
        lines.append(
            f"- {context_key} "
            f"(model_name: {data_plan.model_name}, "
            f"columns: {', '.join(data_plan.primary_fields)})"
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
        widgets=[],
    )


def _build_data_node_from_plan(plan: DataNodeGenerationPlan) -> DataNode:
    if not has_dwh_model(plan.model_name):
        raise ValueError(f"未定義のDWHモデルです: {plan.model_name}")
    field_names = dwh_field_names(plan.model_name)
    context_key = plan.context_key or f"sql_{plan.id}"
    return DataNode(
        id=plan.id,
        context_key=context_key,
        model_name=plan.model_name,
        data_type="dataframe",
        description=plan.description,
        primary_fields=plan.primary_fields or field_names,
    )


def _context_key_for_widget_node(widget_node: WidgetNode) -> str | None:
    if not widget_node.data_nodes:
        return None
    return widget_node.data_nodes[0].context_key


def _bind_widget_to_data_context(widget_node: WidgetNode, context_key: str) -> WidgetNode:
    widget_dump = widget_node.widget.model_dump(mode="json")
    _replace_data_keys(widget_dump, context_key)
    return WidgetNode.model_validate(
        {
            "id": widget_node.id,
            "title": widget_node.title,
            "widget": widget_dump,
            "data_nodes": [data_node.model_dump(mode="json") for data_node in widget_node.data_nodes],
        }
    )


def _replace_data_keys(value: object, context_key: str) -> None:
    if isinstance(value, dict):
        value_dict = cast(dict[object, object], value)
        for key, child in value_dict.items():
            if key == "data_key":
                value_dict[key] = context_key
            else:
                _replace_data_keys(child, context_key)
    elif isinstance(value, list):
        for child in value:
            _replace_data_keys(child, context_key)


def _attach_widget_sql_result(
    graph: ScenarioGraph,
    widget_id: str,
    sql: str,
    context: dict[str, object],
) -> tuple[ScenarioGraph, dict[str, object]]:
    widget_node = _find_widget_node(graph, widget_id)
    if widget_node is None:
        raise ValueError(f"widget node '{widget_id}' が見つかりません。")
    if not widget_node.data_nodes:
        raise ValueError(f"widget node '{widget_id}' に data node 参照がありません。")
    target_node = widget_node.data_nodes[0]
    if target_node is None:
        raise ValueError(
            f"widget node '{widget_node.id}' が存在しない data node "
            "を参照しています。"
        )

    dataframe = execute_read_sql(sql)
    updated_node = target_node.model_copy(
        update={
            "sql": sql,
            "primary_fields": [str(column) for column in dataframe.columns],
        }
    )
    next_context = dict(context)
    next_context[updated_node.context_key] = dataframe
    return _replace_data_node(graph, updated_node), next_context


def _normalize_widget_node(
    widget_node: WidgetNode,
    plan: WidgetNodeGenerationPlan,
    data_nodes_by_id: Mapping[str, DataNode],
) -> WidgetNode:
    widget_dump = widget_node.widget.model_dump(mode="json")
    widget_dump["widget_type"] = plan.widget_type
    return WidgetNode(
        id=plan.id,
        title=widget_node.title if widget_node.title is not None else plan.title,
        widget=widget_dump,
        data_nodes=[
            data_nodes_by_id[data_node_id]
            for data_node_id in plan.data_node_ids
            if data_node_id in data_nodes_by_id
        ],
    )


def _append_task_node(graph: ScenarioGraph, task: TaskNode) -> ScenarioGraph:
    tasks = [existing for existing in graph.tasks if existing.id != task.id]
    tasks.append(task)
    tasks = sorted(tasks, key=lambda node: (node.order, node.id))
    return ScenarioGraph.model_validate(
        graph.model_copy(update={"tasks": tasks}).model_dump(mode="json")
    )


def _append_widget_node(
    graph: ScenarioGraph,
    widget_node: WidgetNode,
    plan: ScenarioGraphGenerationPlan,
) -> ScenarioGraph:
    widget_plan = next(
        (candidate for candidate in plan.widget_nodes if candidate.id == widget_node.id),
        None,
    )
    if widget_plan is None:
        return graph
    tasks: list[TaskNode] = []
    for task in graph.tasks:
        if task.id != widget_plan.task_id:
            tasks.append(task)
            continue
        widgets = [existing for existing in task.widgets if existing.id != widget_node.id]
        widgets.append(widget_node)
        widgets = _sort_widget_nodes_by_plan(widgets, plan)
        tasks.append(task.model_copy(update={"widgets": widgets}))
    return ScenarioGraph.model_validate(
        graph.model_copy(update={"tasks": tasks}).model_dump(mode="json")
    )


def _sort_widget_nodes_by_plan(
    widget_nodes: list[WidgetNode],
    plan: ScenarioGraphGenerationPlan,
) -> list[WidgetNode]:
    """Order widget nodes by plan position so partial graphs render stably."""

    plan_order = {widget_plan.id: index for index, widget_plan in enumerate(plan.widget_nodes)}
    fallback = len(plan_order)
    return sorted(
        widget_nodes,
        key=lambda node: (plan_order.get(node.id, fallback), node.id),
    )


def _find_widget_node(graph: ScenarioGraph, widget_id: str) -> WidgetNode | None:
    return next((widget for widget in graph.widget_nodes if widget.id == widget_id), None)


def _replace_data_node(graph: ScenarioGraph, updated_node: DataNode) -> ScenarioGraph:
    tasks: list[TaskNode] = []
    for task in graph.tasks:
        widgets: list[WidgetNode] = []
        for widget in task.widgets:
            data_nodes = [
                updated_node if data_node.id == updated_node.id else data_node
                for data_node in widget.data_nodes
            ]
            widgets.append(widget.model_copy(update={"data_nodes": data_nodes}))
        tasks.append(task.model_copy(update={"widgets": widgets}))
    return ScenarioGraph.model_validate(
        graph.model_copy(update={"tasks": tasks}).model_dump(mode="json")
    )
