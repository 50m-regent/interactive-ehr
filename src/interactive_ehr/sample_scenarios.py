"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

import pandas as pd

from interactive_ehr.models.registry import (
    build_dwh_context_for_model_names,
    dwh_context_key,
    dwh_field_names,
    get_dwh_model_info,
)
from interactive_ehr.scenario_graph import (
    DataNode,
    GraphEdge,
    ScenarioGraph,
    TaskNode,
    WidgetNode,
)
from interactive_ehr.widgets import (
    AnyWidget,
    ColumnsSpec,
    DataframeSpec,
    LineChartSpec,
    MarkdownSpec,
    TableSpec,
    TabsSpec,
)


DEFAULT_SAMPLE_DWH_MODELS = [
    "患者基本",
    "検体検査結果",
    "処方",
    "カルテ記事DR",
    "バイタル",
]


def get_chronic_disease_graph_scenario() -> tuple[ScenarioGraph, dict[str, object]]:
    """Return a DWH fake-data based task graph sample."""

    widgets, context = get_chronic_disease_scenario()
    data_nodes = [
        _data_node_for_model(model_name, index)
        for index, model_name in enumerate(DEFAULT_SAMPLE_DWH_MODELS, start=1)
    ]
    widget_nodes = [
        WidgetNode(
            id=f"widget_{index}",
            title=type(widget).__name__,
            widget=widget,
            data_node_ids=_referenced_data_node_ids(widget, data_nodes),
        )
        for index, widget in enumerate(widgets, start=1)
    ]
    graph = ScenarioGraph(
        id="chronic_disease_outpatient",
        title="DWH fake データ確認",
        description="定義済みDWHモデルの fake() で生成した検証用シナリオ。",
        tasks=[
            TaskNode(
                id="task_patient_overview",
                title="患者・バイタル",
                description="患者基本とバイタルの fake データを確認する。",
                order=1,
                widget_ids=["widget_1", "widget_2"],
            ),
            TaskNode(
                id="task_labs_orders",
                title="検査・処方",
                description="検体検査結果と処方の fake データを確認する。",
                order=2,
                widget_ids=["widget_3"],
            ),
            TaskNode(
                id="task_records",
                title="カルテ",
                description="医師カルテ記事の fake データを確認する。",
                order=3,
                widget_ids=["widget_4"],
            ),
        ],
        data_nodes=data_nodes,
        widget_nodes=widget_nodes,
        edges=_build_edges("chronic_disease_outpatient", widget_nodes),
    )
    return graph, context


def get_chronic_disease_scenario() -> tuple[list[AnyWidget], dict[str, object]]:
    """Return widgets and context generated only from DWH model fake data."""

    context = build_dwh_context_for_model_names(DEFAULT_SAMPLE_DWH_MODELS)
    patient_key = dwh_context_key("患者基本")
    lab_key = dwh_context_key("検体検査結果")
    prescription_key = dwh_context_key("処方")
    record_key = dwh_context_key("カルテ記事DR")
    vital_key = dwh_context_key("バイタル")
    widgets: list[AnyWidget] = [
        MarkdownSpec(body="### DWH fake データサンプル"),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [
                    TableSpec(data_key=patient_key),
                ],
                [
                    LineChartSpec(
                        data_key=vital_key,
                        x="測定日",
                        y=["体温", "脈拍", "血圧(最高)", "血圧(最低)"],
                    ),
                ],
            ],
        ),
        TabsSpec(
            labels=["検体検査結果", "処方"],
            tabs=[
                [
                    DataframeSpec(
                        data_key=lab_key,
                        column_order=[
                            "匿名ID",
                            "検索日(採取日)",
                            "検査項目",
                            "結果(数値)",
                            "結果値単位",
                        ],
                        height=320,
                    )
                ],
                [
                    DataframeSpec(
                        data_key=prescription_key,
                        column_order=[
                            "匿名ID",
                            "服薬開始日",
                            "薬剤名",
                            "用法",
                            "処方日数",
                        ],
                        height=320,
                    )
                ],
            ],
        ),
        DataframeSpec(
            data_key=record_key,
            column_order=["匿名ID", "記載日", "診療科", "記事種別", "記事"],
            height=320,
        ),
    ]
    return widgets, context


def _data_node_for_model(model_name: str, index: int) -> DataNode:
    model_info = get_dwh_model_info(model_name)
    return DataNode(
        id=f"data_{index}",
        context_key=dwh_context_key(model_name),
        model_name=model_name,
        data_type="dataframe",
        description=model_info.description or f"DWH model {model_name} fake data",
        primary_fields=dwh_field_names(model_name),
    )


def _build_edges(scenario_id: str, widget_nodes: list[WidgetNode]) -> list[GraphEdge]:
    edges = [
        GraphEdge(
            source_id=scenario_id,
            target_id="task_patient_overview",
            edge_type="scenario_to_task",
        ),
        GraphEdge(
            source_id=scenario_id,
            target_id="task_labs_orders",
            edge_type="scenario_to_task",
        ),
        GraphEdge(
            source_id=scenario_id,
            target_id="task_records",
            edge_type="scenario_to_task",
        ),
    ]
    task_by_widget_id = {
        "widget_1": "task_patient_overview",
        "widget_2": "task_patient_overview",
        "widget_3": "task_labs_orders",
        "widget_4": "task_records",
    }
    for widget_node in widget_nodes:
        task_id = task_by_widget_id[widget_node.id]
        edges.append(
            GraphEdge(
                source_id=task_id,
                target_id=widget_node.id,
                edge_type="task_to_widget",
            )
        )
        for data_node_id in widget_node.data_node_ids:
            edges.append(
                GraphEdge(
                    source_id=widget_node.id,
                    target_id=data_node_id,
                    edge_type="widget_to_data",
                )
            )
    return edges


def _referenced_data_node_ids(
    widget: AnyWidget,
    data_nodes: list[DataNode],
) -> list[str]:
    data_node_by_key = {node.context_key: node for node in data_nodes}
    widget_json = widget.model_dump(mode="json")
    keys = _collect_reference_keys(widget_json)
    return [
        data_node_by_key[key].id
        for key in keys
        if key in data_node_by_key
    ]


def _collect_reference_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.endswith("_key") and isinstance(child, str):
                keys.append(child)
            else:
                keys.extend(_collect_reference_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_collect_reference_keys(child))
    return list(dict.fromkeys(keys))


def _describe_context_type(value: object) -> str:
    if isinstance(value, pd.DataFrame):
        return "dataframe"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _primary_fields(value: object) -> list[str]:
    if isinstance(value, pd.DataFrame):
        return [str(column) for column in value.columns]
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return [str(key) for key in value[0]]
    if isinstance(value, dict):
        return [str(key) for key in value]
    return []
