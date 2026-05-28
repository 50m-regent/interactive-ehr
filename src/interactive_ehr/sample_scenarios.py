"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

import pandas as pd

from interactive_ehr.scenario_graph import (
    DataNode,
    GraphEdge,
    ScenarioGraph,
    TaskNode,
    WidgetNode,
    build_sql_context_for_graph,
)
from interactive_ehr.widgets import (
    AnyWidget,
    BarChartSpec,
    ColumnsSpec,
    LineChartSpec,
    MetricSpec,
    TabsSpec,
)


SAMPLE_DATA_NODE_SPECS = [
    {
        "id": "data_patient_profile",
        "context_key": "metric_patient_profile",
        "model_name": None,
        "data_type": "scalar",
        "description": "患者背景",
        "primary_fields": ["患者背景"],
        "sql": (
            'SELECT "患者表示名" || " / " || "年齢" || "歳 / " || "主要疾患" '
            'AS "患者背景" FROM "慢性疾患外来_患者サマリ"'
        ),
    },
    {
        "id": "data_latest_bp",
        "context_key": "metric_latest_bp",
        "model_name": None,
        "data_type": "scalar",
        "description": "直近の外来血圧",
        "primary_fields": ["外来血圧"],
        "sql": (
            'SELECT CAST("収縮期血圧" AS TEXT) || "/" || CAST("拡張期血圧" AS TEXT) '
            '|| " mmHg" AS "外来血圧" FROM "慢性疾患外来_患者サマリ"'
        ),
    },
    {
        "id": "data_home_bp",
        "context_key": "metric_home_bp",
        "model_name": None,
        "data_type": "scalar",
        "description": "家庭血圧の概況",
        "primary_fields": ["家庭血圧"],
        "sql": 'SELECT "家庭血圧" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_latest_egfr",
        "context_key": "metric_latest_egfr",
        "model_name": None,
        "data_type": "scalar",
        "description": "直近eGFR",
        "primary_fields": ["eGFR"],
        "sql": 'SELECT "eGFR" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_latest_uacr",
        "context_key": "metric_latest_uacr",
        "model_name": None,
        "data_type": "scalar",
        "description": "直近尿アルブミン/Cr比",
        "primary_fields": ["UACR"],
        "sql": 'SELECT "UACR" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_latest_potassium",
        "context_key": "metric_latest_potassium",
        "model_name": None,
        "data_type": "scalar",
        "description": "直近K",
        "primary_fields": ["K"],
        "sql": 'SELECT "K" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_latest_a1c",
        "context_key": "metric_latest_a1c",
        "model_name": None,
        "data_type": "scalar",
        "description": "直近HbA1c",
        "primary_fields": ["HbA1c"],
        "sql": 'SELECT "HbA1c" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_bp_trend",
        "context_key": "chart_bp_trend",
        "model_name": None,
        "data_type": "dataframe",
        "description": "血圧の推移",
        "primary_fields": ["測定日", "外来収縮期", "外来拡張期", "家庭収縮期"],
        "sql": (
            'SELECT "測定日", "外来収縮期", "外来拡張期", "家庭収縮期" '
            'FROM "慢性疾患外来_血圧推移" ORDER BY "測定日"'
        ),
    },
    {
        "id": "data_kidney_trend",
        "context_key": "chart_kidney_trend",
        "model_name": None,
        "data_type": "dataframe",
        "description": "腎機能の推移",
        "primary_fields": ["検査日", "eGFR", "UACR"],
        "sql": (
            'SELECT "検査日", "eGFR", "UACR" '
            'FROM "慢性疾患外来_検査推移" ORDER BY "検査日"'
        ),
    },
    {
        "id": "data_antihypertensive_rx",
        "context_key": "metric_antihypertensive_rx",
        "model_name": None,
        "data_type": "scalar",
        "description": "降圧薬・腎保護薬",
        "primary_fields": ["処方"],
        "sql": (
            'SELECT GROUP_CONCAT("薬剤名" || " " || "用量", " / ") AS "処方" '
            'FROM "慢性疾患外来_処方" WHERE "カテゴリ" = "降圧・腎保護"'
        ),
    },
    {
        "id": "data_diabetes_rx",
        "context_key": "metric_diabetes_rx",
        "model_name": None,
        "data_type": "scalar",
        "description": "糖尿病薬",
        "primary_fields": ["処方"],
        "sql": (
            'SELECT GROUP_CONCAT("薬剤名" || " " || "用量", " / ") AS "処方" '
            'FROM "慢性疾患外来_処方" WHERE "カテゴリ" = "糖尿病"'
        ),
    },
    {
        "id": "data_lipid_rx",
        "context_key": "metric_lipid_rx",
        "model_name": None,
        "data_type": "scalar",
        "description": "脂質異常症薬",
        "primary_fields": ["処方"],
        "sql": (
            'SELECT GROUP_CONCAT("薬剤名" || " " || "用量", " / ") AS "処方" '
            'FROM "慢性疾患外来_処方" WHERE "カテゴリ" = "脂質"'
        ),
    },
    {
        "id": "data_medication_categories",
        "context_key": "chart_medication_categories",
        "model_name": None,
        "data_type": "dataframe",
        "description": "処方カテゴリ別の薬剤数",
        "primary_fields": ["カテゴリ", "薬剤数"],
        "sql": (
            'SELECT "カテゴリ", COUNT(*) AS "薬剤数" FROM "慢性疾患外来_処方" '
            'GROUP BY "カテゴリ" ORDER BY "薬剤数" DESC'
        ),
    },
    {
        "id": "data_side_effect_note",
        "context_key": "metric_side_effect_note",
        "model_name": None,
        "data_type": "scalar",
        "description": "過去カルテから抽出した副作用確認事項",
        "primary_fields": ["内容"],
        "sql": 'SELECT "内容" FROM "慢性疾患外来_カルテ記載" WHERE "種別" = "副作用"',
    },
    {
        "id": "data_adherence_note",
        "context_key": "metric_adherence_note",
        "model_name": None,
        "data_type": "scalar",
        "description": "過去カルテから抽出した服薬コンプライアンス",
        "primary_fields": ["内容"],
        "sql": 'SELECT "内容" FROM "慢性疾患外来_カルテ記載" WHERE "種別" = "服薬"',
    },
    {
        "id": "data_latest_exam_summary",
        "context_key": "metric_latest_exam_summary",
        "model_name": None,
        "data_type": "scalar",
        "description": "検査結果に基づく処方調整の論点",
        "primary_fields": ["本日の論点"],
        "sql": 'SELECT "本日の論点" FROM "慢性疾患外来_患者サマリ"',
    },
    {
        "id": "data_adjustment_note",
        "context_key": "metric_adjustment_note",
        "model_name": None,
        "data_type": "scalar",
        "description": "処方調整時の注意点",
        "primary_fields": ["内容"],
        "sql": 'SELECT "内容" FROM "慢性疾患外来_カルテ記載" WHERE "種別" = "処方調整"',
    },
    {
        "id": "data_lifestyle_status",
        "context_key": "chart_lifestyle_status",
        "model_name": None,
        "data_type": "dataframe",
        "description": "生活習慣の実施状況",
        "primary_fields": ["項目", "達成率"],
        "sql": 'SELECT "項目", "達成率" FROM "慢性疾患外来_生活指導" ORDER BY "達成率"',
    },
    {
        "id": "data_patient_material",
        "context_key": "metric_patient_material",
        "model_name": None,
        "data_type": "scalar",
        "description": "患者向け資料の要点",
        "primary_fields": ["資料要点"],
        "sql": 'SELECT "資料要点" FROM "慢性疾患外来_患者向け資料"',
    },
    {
        "id": "data_next_action",
        "context_key": "metric_next_action",
        "model_name": None,
        "data_type": "scalar",
        "description": "次回までの確認事項",
        "primary_fields": ["次回ToDo"],
        "sql": 'SELECT "次回ToDo" FROM "慢性疾患外来_患者サマリ"',
    },
]


def get_chronic_disease_graph_scenario() -> tuple[ScenarioGraph, dict[str, object]]:
    """Return the default task graph based on the Notion chronic disease example."""

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
            id="task_bp_kidney",
            title="血圧・腎機能評価",
            description="最近の血圧コントロール状況と腎機能の経時的変化を評価する。",
            order=1,
            widget_ids=["widget_1", "widget_2", "widget_3"],
        ),
        TaskNode(
            id="task_side_effect_adherence",
            title="副作用・服薬確認",
            description="現在の処方内容、過去のカルテ記載から副作用と服薬状況を確認する。",
            order=2,
            widget_ids=["widget_4", "widget_5", "widget_6"],
        ),
        TaskNode(
            id="task_prescription_adjustment",
            title="検査に基づく処方調整",
            description="直近の検査結果、現在処方、過去記載を合わせて処方調整を検討する。",
            order=3,
            widget_ids=["widget_7", "widget_8"],
        ),
        TaskNode(
            id="task_lifestyle_guidance",
            title="生活習慣指導",
            description="患者向け資料を使い、生活習慣の重要性を再度指導する。",
            order=4,
            widget_ids=["widget_9", "widget_10"],
        ),
    ]
    graph = ScenarioGraph(
        id="chronic_disease_outpatient",
        title="複数の慢性疾患を持つ高齢患者の外来診察",
        description="Notionのタスク仮定例に基づく、血圧・腎機能・処方・生活指導のサンプル。",
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
        ColumnsSpec(
            widths=[1, 1, 1, 1],
            columns=[
                [MetricSpec(label="患者背景", value_key="metric_patient_profile")],
                [MetricSpec(label="直近外来血圧", value_key="metric_latest_bp")],
                [MetricSpec(label="家庭血圧", value_key="metric_home_bp")],
                [MetricSpec(label="eGFR", value_key="metric_latest_egfr")],
            ],
        ),
        TabsSpec(
            labels=["血圧推移", "腎機能推移"],
            tabs=[
                [
                    LineChartSpec(
                        data_key="chart_bp_trend",
                        x="測定日",
                        y=["外来収縮期", "外来拡張期", "家庭収縮期"],
                        height=300,
                    )
                ],
                [
                    LineChartSpec(
                        data_key="chart_kidney_trend",
                        x="検査日",
                        y=["eGFR", "UACR"],
                        height=300,
                    )
                ],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="UACR", value_key="metric_latest_uacr")],
                [MetricSpec(label="K", value_key="metric_latest_potassium")],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1, 1],
            columns=[
                [MetricSpec(label="降圧・腎保護", value_key="metric_antihypertensive_rx")],
                [MetricSpec(label="糖尿病薬", value_key="metric_diabetes_rx")],
                [MetricSpec(label="脂質薬", value_key="metric_lipid_rx")],
            ],
        ),
        BarChartSpec(
            data_key="chart_medication_categories",
            x="カテゴリ",
            y="薬剤数",
            height=260,
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="副作用確認", value_key="metric_side_effect_note")],
                [MetricSpec(label="服薬状況", value_key="metric_adherence_note")],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1, 1, 1],
            columns=[
                [MetricSpec(label="HbA1c", value_key="metric_latest_a1c")],
                [MetricSpec(label="eGFR", value_key="metric_latest_egfr")],
                [MetricSpec(label="UACR", value_key="metric_latest_uacr")],
                [MetricSpec(label="K", value_key="metric_latest_potassium")],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="本日の論点", value_key="metric_latest_exam_summary")],
                [MetricSpec(label="処方調整メモ", value_key="metric_adjustment_note")],
            ],
        ),
        BarChartSpec(
            data_key="chart_lifestyle_status",
            x="項目",
            y="達成率",
            height=300,
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="患者向け説明", value_key="metric_patient_material")],
                [MetricSpec(label="次回までの確認", value_key="metric_next_action")],
            ],
        ),
    ]


def _data_node_from_spec(spec: dict[str, object]) -> DataNode:
    model_name = spec["model_name"]
    return DataNode(
        id=str(spec["id"]),
        context_key=str(spec["context_key"]),
        model_name=str(model_name) if model_name is not None else None,
        data_type=str(spec["data_type"]),
        description=str(spec["description"]),
        primary_fields=[str(field) for field in spec["primary_fields"]],
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
    return [data_node_by_key[key].id for key in keys if key in data_node_by_key]


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
