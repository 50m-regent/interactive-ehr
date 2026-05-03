"""Task graph models, rendering, and Gemini generation helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.llm import GeminiMixin
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


def parse_scenario_graph_json(json_text: str) -> ScenarioGraph:
    """Parse JSON text into a validated ScenarioGraph."""

    data = json.loads(json_text)
    return ScenarioGraph.model_validate(data)


def render_scenario_graph(
    graph: ScenarioGraph,
    context: Mapping[str, object],
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
                    st.warning(
                        f"task '{task.id}' が存在しない widget '{widget_id}' を参照しています。"
                    )
                    continue

                _warn_for_data_references(widget_node, data_by_id, context)
                render_widget(widget_node.widget, context)


def generate_scenario_graph(
    prompt: str,
    context: Mapping[str, object],
) -> ScenarioGraph:
    """Generate a ScenarioGraph using Gemini structured output."""

    client = _ScenarioGraphGenerator()
    return client.generate(_build_generation_prompt(prompt, context), ScenarioGraph)


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
    context_keys = "\n".join(f"- {key}" for key in sorted(context))
    widget_types = "\n".join(f"- {widget_type.value}" for widget_type in WidgetType)
    return f"""\
あなたは電子カルテ UI のタスクグラフを設計するアシスタントです。
ユーザーの要望を、ScenarioGraph JSON として出力してください。

制約:
- 出力は ScenarioGraph スキーマに一致する JSON のみ。
- widget は既存 WidgetSpec の discriminated union です。
- widget.widget_type は下記の利用可能な値だけを使ってください。
- データ本体は生成せず、data_nodes.context_key と各 widget の data_key/options_key/value_key/delta_key は下記 context key だけを参照してください。
- scenario_to_task, task_to_widget, widget_to_data の edges を明示してください。
- task.widget_ids はそのタスクで表示する widget node ID を表示順に並べてください。
- 存在しない task/widget/data ID を参照しないでください。

利用可能な context key:
{context_keys}

利用可能な widget_type:
{widget_types}

ユーザー要望:
{user_prompt}
"""
