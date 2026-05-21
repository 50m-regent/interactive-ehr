"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from interactive_ehr.models.registry import (
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
    BarChartSpec,
    ColumnsSpec,
    LineChartSpec,
    MarkdownSpec,
    MetricSpec,
    TabsSpec,
)
from interactive_ehr.scenario_graph import build_sql_context_for_graph


SAMPLE_DATA_NODE_SPECS = [
    {
        "id": "data_patient_age",
        "context_key": "metric_patient_age",
        "model_name": "患者基本",
        "data_type": "scalar",
        "description": "患者の現在年齢",
        "primary_fields": ["現在年齢"],
        "sql": (
            'SELECT COALESCE((SELECT "現在年齢" FROM "患者基本" '
            "WHERE \"現在年齢\" IS NOT NULL LIMIT 1), '未記録') AS \"現在年齢\""
        ),
    },
    {
        "id": "data_latest_sbp",
        "context_key": "metric_latest_sbp",
        "model_name": "バイタル",
        "data_type": "scalar",
        "description": "直近の収縮期血圧",
        "primary_fields": ["血圧(最高)"],
        "sql": (
            'SELECT COALESCE((SELECT "血圧(最高)" FROM "バイタル" '
            'WHERE "血圧(最高)" IS NOT NULL ORDER BY "測定日" DESC LIMIT 1), '
            "'未記録') AS \"血圧(最高)\""
        ),
    },
    {
        "id": "data_latest_dbp",
        "context_key": "metric_latest_dbp",
        "model_name": "バイタル",
        "data_type": "scalar",
        "description": "直近の拡張期血圧",
        "primary_fields": ["血圧(最低)"],
        "sql": (
            'SELECT COALESCE((SELECT "血圧(最低)" FROM "バイタル" '
            'WHERE "血圧(最低)" IS NOT NULL ORDER BY "測定日" DESC LIMIT 1), '
            "'未記録') AS \"血圧(最低)\""
        ),
    },
    {
        "id": "data_vital_trend",
        "context_key": "chart_vital_trend",
        "model_name": "バイタル",
        "data_type": "dataframe",
        "description": "バイタル推移",
        "primary_fields": ["測定日", "体温", "脈拍", "血圧(最高)", "血圧(最低)"],
        "sql": (
            'SELECT "測定日", "体温", "脈拍", "血圧(最高)", "血圧(最低)" '
            'FROM "バイタル" ORDER BY "測定日" LIMIT 20'
        ),
    },
    {
        "id": "data_latest_lab_value",
        "context_key": "metric_latest_lab_value",
        "model_name": "検体検査結果",
        "data_type": "scalar",
        "description": "直近の数値検査結果",
        "primary_fields": ["結果(数値)"],
        "sql": (
            'SELECT COALESCE((SELECT "結果(数値)" FROM "検体検査結果" '
            'WHERE "結果(数値)" IS NOT NULL ORDER BY "検索日(採取日)" DESC LIMIT 1), '
            "'未記録') AS \"結果(数値)\""
        ),
    },
    {
        "id": "data_prescription_count",
        "context_key": "metric_prescription_count",
        "model_name": "処方",
        "data_type": "scalar",
        "description": "処方件数",
        "primary_fields": ["処方件数"],
        "sql": 'SELECT COUNT(*) AS "処方件数" FROM "処方"',
    },
    {
        "id": "data_average_prescription_days",
        "context_key": "metric_average_prescription_days",
        "model_name": "処方",
        "data_type": "scalar",
        "description": "平均処方日数",
        "primary_fields": ["平均処方日数"],
        "sql": (
            "SELECT COALESCE(ROUND(AVG(\"処方日数\"), 1), '未記録') AS \"平均処方日数\" "
            'FROM "処方" WHERE "処方日数" IS NOT NULL'
        ),
    },
    {
        "id": "data_lab_trend",
        "context_key": "chart_lab_trend",
        "model_name": "検体検査結果",
        "data_type": "dataframe",
        "description": "検査値推移",
        "primary_fields": ["検索日(採取日)", "結果(数値)"],
        "sql": (
            'SELECT "検索日(採取日)", "結果(数値)" FROM "検体検査結果" '
            'WHERE "結果(数値)" IS NOT NULL ORDER BY "検索日(採取日)" LIMIT 20'
        ),
    },
    {
        "id": "data_prescription_days",
        "context_key": "chart_prescription_days",
        "model_name": "処方",
        "data_type": "dataframe",
        "description": "薬剤別処方日数",
        "primary_fields": ["薬剤名", "処方日数"],
        "sql": (
            'SELECT "薬剤名", "処方日数" FROM "処方" '
            'WHERE "処方日数" IS NOT NULL ORDER BY "服薬開始日" DESC LIMIT 10'
        ),
    },
    {
        "id": "data_record_count",
        "context_key": "metric_record_count",
        "model_name": "カルテ記事DR",
        "data_type": "scalar",
        "description": "医師カルテ記事数",
        "primary_fields": ["記事数"],
        "sql": 'SELECT COUNT(*) AS "記事数" FROM "カルテ記事DR"',
    },
    {
        "id": "data_latest_record_date",
        "context_key": "metric_latest_record_date",
        "model_name": "カルテ記事DR",
        "data_type": "scalar",
        "description": "直近カルテ記載日",
        "primary_fields": ["記載日"],
        "sql": (
            'SELECT COALESCE((SELECT "記載日" FROM "カルテ記事DR" '
            'WHERE "記載日" IS NOT NULL ORDER BY "記載日" DESC LIMIT 1), '
            "'未記録') AS \"記載日\""
        ),
    },
    {
        "id": "data_record_type_counts",
        "context_key": "chart_record_type_counts",
        "model_name": "カルテ記事DR",
        "data_type": "dataframe",
        "description": "記事種別件数",
        "primary_fields": ["記事種別", "件数"],
        "sql": (
            'SELECT "記事種別", COUNT(*) AS "件数" FROM "カルテ記事DR" '
            'GROUP BY "記事種別" ORDER BY "件数" DESC LIMIT 10'
        ),
    },
]


def get_chronic_disease_graph_scenario() -> tuple[ScenarioGraph, dict[str, object]]:
    """Return a DWH fake-data based task graph sample."""

    data_nodes = [_data_node_from_spec(spec) for spec in SAMPLE_DATA_NODE_SPECS]
    widgets = _chronic_disease_widgets()
    widget_nodes = [
        WidgetNode(
            id=f"widget_{index}",
            title=type(widget).__name__,
            widget=widget,
            data_node_ids=_referenced_data_node_ids(widget, data_nodes),
        )
        for index, widget in enumerate(widgets, start=1)
    ]
    tasks = [
        TaskNode(
            id="task_patient_overview",
            title="患者・バイタル",
            description="患者背景とバイタルの要点を確認する。",
            order=1,
            widget_ids=["widget_1", "widget_2", "widget_3"],
        ),
        TaskNode(
            id="task_labs_orders",
            title="検査・処方",
            description="検査値と処方継続の確認ポイントを見る。",
            order=2,
            widget_ids=["widget_4", "widget_5", "widget_6"],
        ),
        TaskNode(
            id="task_records",
            title="カルテ",
            description="直近記録と記事種別の偏りを確認する。",
            order=3,
            widget_ids=["widget_7", "widget_8", "widget_9"],
        ),
    ]
    graph = ScenarioGraph(
        id="chronic_disease_outpatient",
        title="慢性疾患外来レビュー",
        description="SQLで抽出した要点を使う診療タスク別サンプル。",
        tasks=tasks,
        data_nodes=data_nodes,
        widget_nodes=widget_nodes,
        edges=_build_edges("chronic_disease_outpatient", tasks, widget_nodes),
    )
    context = build_sql_context_for_graph(graph)
    return graph, context


def get_chronic_disease_scenario() -> tuple[list[AnyWidget], dict[str, object]]:
    """Return widgets and context generated from DWH SQLite SQL."""

    graph, context = get_chronic_disease_graph_scenario()
    return [widget_node.widget for widget_node in graph.widget_nodes], context


def _chronic_disease_widgets() -> list[AnyWidget]:
    return [
        MarkdownSpec(
            body=(
                "### 慢性疾患外来レビュー\n"
                "診察前に患者背景、バイタル推移、検査値、処方継続、直近記録を確認します。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1, 1],
            columns=[
                [MetricSpec(label="現在年齢", value_key="metric_patient_age")],
                [MetricSpec(label="直近 収縮期血圧", value_key="metric_latest_sbp")],
                [MetricSpec(label="直近 拡張期血圧", value_key="metric_latest_dbp")],
            ],
        ),
        LineChartSpec(
            data_key="chart_vital_trend",
            x="測定日",
            y=["体温", "脈拍", "血圧(最高)", "血圧(最低)"],
            height=280,
        ),
        MarkdownSpec(
            body=(
                "### 検査・処方確認\n"
                "検査値の変化と処方日数を見て、追加確認が必要な項目を絞り込みます。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1, 1],
            columns=[
                [MetricSpec(label="直近 数値検査結果", value_key="metric_latest_lab_value")],
                [MetricSpec(label="処方件数", value_key="metric_prescription_count")],
                [
                    MetricSpec(
                        label="平均処方日数",
                        value_key="metric_average_prescription_days",
                    )
                ],
            ],
        ),
        TabsSpec(
            labels=["検査値推移", "処方日数"],
            tabs=[
                [
                    LineChartSpec(
                        data_key="chart_lab_trend",
                        x="検索日(採取日)",
                        y="結果(数値)",
                        height=280,
                    )
                ],
                [
                    BarChartSpec(
                        data_key="chart_prescription_days",
                        x="薬剤名",
                        y="処方日数",
                        height=280,
                    )
                ],
            ],
        ),
        MarkdownSpec(
            body=(
                "### カルテ確認\n"
                "直近記載日と記事種別を確認し、診察前に読むべき記録の優先度を決めます。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="医師記事数", value_key="metric_record_count")],
                [MetricSpec(label="直近記載日", value_key="metric_latest_record_date")],
            ],
        ),
        BarChartSpec(
            data_key="chart_record_type_counts",
            x="記事種別",
            y="件数",
            height=280,
        ),
    ]


def _data_node_from_spec(spec: dict[str, object]) -> DataNode:
    model_name = str(spec["model_name"])
    description = str(spec["description"])
    model_description = (get_dwh_model_info(model_name).description or "").strip()
    primary_fields = spec["primary_fields"]
    if not isinstance(primary_fields, Sequence) or isinstance(
        primary_fields, str | bytes
    ):
        primary_fields = []
    return DataNode(
        id=str(spec["id"]),
        context_key=str(spec["context_key"]),
        model_name=model_name,
        data_type=str(spec["data_type"]),
        description=description or model_description,
        primary_fields=[str(field) for field in primary_fields],
        sql=str(spec["sql"]),
    )


def _build_edges(
    scenario_id: str,
    tasks: list[TaskNode],
    widget_nodes: list[WidgetNode],
) -> list[GraphEdge]:
    edges = [
        GraphEdge(source_id=scenario_id, target_id=task.id, edge_type="scenario_to_task")
        for task in tasks
    ]
    widget_by_id = {widget.id: widget for widget in widget_nodes}
    for task in tasks:
        for widget_id in task.widget_ids:
            widget_node = widget_by_id[widget_id]
            edges.append(
                GraphEdge(
                    source_id=task.id,
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
