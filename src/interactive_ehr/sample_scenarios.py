"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

import pandas as pd

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
        "model_name": None,
        "data_type": "scalar",
        "description": "患者の現在年齢",
        "primary_fields": ["年齢"],
        "sql": 'SELECT "年齢" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_diabetes_duration",
        "context_key": "metric_diabetes_duration",
        "model_name": None,
        "data_type": "scalar",
        "description": "糖尿病罹病年数",
        "primary_fields": ["糖尿病罹病年数"],
        "sql": 'SELECT "糖尿病罹病年数" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_latest_a1c",
        "context_key": "metric_latest_a1c",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新HbA1c",
        "primary_fields": ["最新HbA1c"],
        "sql": 'SELECT "最新HbA1c" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_latest_bp",
        "context_key": "metric_latest_bp",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新外来血圧",
        "primary_fields": ["血圧"],
        "sql": (
            'SELECT CAST("収縮期血圧" AS TEXT) || "/" || CAST("拡張期血圧" AS TEXT) '
            '|| " mmHg" AS "血圧" FROM "糖尿病外来_患者サマリ"'
        ),
    },
    {
        "id": "data_latest_bmi",
        "context_key": "metric_latest_bmi",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新BMI",
        "primary_fields": ["BMI"],
        "sql": 'SELECT "BMI" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_hypoglycemia",
        "context_key": "metric_hypoglycemia",
        "model_name": None,
        "data_type": "scalar",
        "description": "低血糖エピソード",
        "primary_fields": ["低血糖"],
        "sql": 'SELECT "低血糖" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_a1c_trend",
        "context_key": "chart_a1c_trend",
        "model_name": None,
        "data_type": "dataframe",
        "description": "HbA1c推移",
        "primary_fields": ["検査日", "HbA1c"],
        "sql": 'SELECT "検査日", "HbA1c" FROM "糖尿病外来_検査推移" ORDER BY "検査日"',
    },
    {
        "id": "data_bp_weight_trend",
        "context_key": "chart_bp_weight_trend",
        "model_name": None,
        "data_type": "dataframe",
        "description": "血圧とBMIの推移",
        "primary_fields": ["測定日", "収縮期血圧", "拡張期血圧", "BMI"],
        "sql": (
            'SELECT "測定日", "収縮期血圧", "拡張期血圧", "BMI" '
            'FROM "糖尿病外来_バイタル推移" ORDER BY "測定日"'
        ),
    },
    {
        "id": "data_latest_egfr",
        "context_key": "metric_latest_egfr",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新eGFR",
        "primary_fields": ["eGFR"],
        "sql": 'SELECT "eGFR" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_latest_uacr",
        "context_key": "metric_latest_uacr",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新UACR",
        "primary_fields": ["UACR"],
        "sql": 'SELECT "UACR" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_latest_ldl",
        "context_key": "metric_latest_ldl",
        "model_name": None,
        "data_type": "scalar",
        "description": "最新LDL",
        "primary_fields": ["LDL"],
        "sql": 'SELECT "LDL" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_eye_exam",
        "context_key": "metric_eye_exam",
        "model_name": None,
        "data_type": "scalar",
        "description": "最終眼科受診",
        "primary_fields": ["最終眼科受診"],
        "sql": 'SELECT "最終眼科受診" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_foot_check",
        "context_key": "metric_foot_check",
        "model_name": None,
        "data_type": "scalar",
        "description": "最終足チェック",
        "primary_fields": ["最終足チェック"],
        "sql": 'SELECT "最終足チェック" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_kidney_trend",
        "context_key": "chart_kidney_trend",
        "model_name": None,
        "data_type": "dataframe",
        "description": "腎機能推移",
        "primary_fields": ["検査日", "eGFR", "UACR"],
        "sql": (
            'SELECT "検査日", "eGFR", "UACR" '
            'FROM "糖尿病外来_検査推移" ORDER BY "検査日"'
        ),
    },
    {
        "id": "data_medication_categories",
        "context_key": "chart_medication_categories",
        "model_name": None,
        "data_type": "dataframe",
        "description": "薬剤カテゴリ別件数",
        "primary_fields": ["カテゴリ", "薬剤数"],
        "sql": (
            'SELECT "カテゴリ", COUNT(*) AS "薬剤数" FROM "糖尿病外来_治療" '
            'GROUP BY "カテゴリ" ORDER BY "薬剤数" DESC'
        ),
    },
    {
        "id": "data_lifestyle_adherence",
        "context_key": "chart_lifestyle_adherence",
        "model_name": None,
        "data_type": "dataframe",
        "description": "生活習慣達成率",
        "primary_fields": ["項目", "達成率"],
        "sql": 'SELECT "項目", "達成率" FROM "糖尿病外来_生活" ORDER BY "達成率"',
    },
    {
        "id": "data_visit_issue",
        "context_key": "metric_visit_issue",
        "model_name": None,
        "data_type": "scalar",
        "description": "本日の論点",
        "primary_fields": ["本日の論点"],
        "sql": 'SELECT "本日の論点" FROM "糖尿病外来_患者サマリ"',
    },
    {
        "id": "data_next_todo",
        "context_key": "metric_next_todo",
        "model_name": None,
        "data_type": "scalar",
        "description": "次回までのToDo",
        "primary_fields": ["次回ToDo"],
        "sql": 'SELECT "次回ToDo" FROM "糖尿病外来_患者サマリ"',
    },
]


def get_chronic_disease_graph_scenario() -> tuple[ScenarioGraph, dict[str, object]]:
    """Return the default diabetes outpatient task graph sample."""

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
            id="task_visit_summary",
            title="診察前サマリ",
            description="血糖、血圧、体重、低血糖の要点を診察前に確認する。",
            order=1,
            widget_ids=["widget_1", "widget_2", "widget_3", "widget_4"],
        ),
        TaskNode(
            id="task_complications",
            title="血糖・合併症",
            description="血糖推移、腎症、脂質、眼科/足チェックを確認する。",
            order=2,
            widget_ids=["widget_5", "widget_6", "widget_7", "widget_8"],
        ),
        TaskNode(
            id="task_treatment_lifestyle",
            title="治療・生活",
            description="薬物療法と生活習慣の継続状況を確認する。",
            order=3,
            widget_ids=["widget_9", "widget_10", "widget_11"],
        ),
        TaskNode(
            id="task_today_plan",
            title="本日の診察メモ",
            description="今日の確認事項と次回までのToDoを整理する。",
            order=4,
            widget_ids=["widget_12", "widget_13", "widget_14"],
        ),
    ]
    graph = ScenarioGraph(
        id="diabetes_outpatient",
        title="糖尿病患者の外来診察",
        description="糖尿病外来で確認する血糖、合併症、治療、生活指導のサンプル。",
        tasks=tasks,
        data_nodes=data_nodes,
        widget_nodes=widget_nodes,
        edges=_build_edges("diabetes_outpatient", tasks, widget_nodes),
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
                "### 糖尿病外来レビュー\n"
                "A1C、血圧、体重、低血糖、腎症・網膜症・足病変の確認漏れを防ぐための診察前サマリです。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1, 1, 1],
            columns=[
                [MetricSpec(label="年齢", value_key="metric_patient_age")],
                [MetricSpec(label="糖尿病罹病年数", value_key="metric_diabetes_duration")],
                [MetricSpec(label="最新HbA1c", value_key="metric_latest_a1c")],
                [MetricSpec(label="低血糖", value_key="metric_hypoglycemia")],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [MetricSpec(label="外来血圧", value_key="metric_latest_bp")],
                [MetricSpec(label="BMI", value_key="metric_latest_bmi")],
            ],
        ),
        LineChartSpec(
            data_key="chart_bp_weight_trend",
            x="測定日",
            y=["収縮期血圧", "拡張期血圧", "BMI"],
            height=300,
        ),
        MarkdownSpec(
            body=(
                "### 血糖・合併症チェック\n"
                "A1Cは多くの成人で7%未満を目安にしつつ、腎機能・尿アルブミン・眼科/足チェックを合わせて確認します。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1, 1, 1],
            columns=[
                [MetricSpec(label="eGFR", value_key="metric_latest_egfr")],
                [MetricSpec(label="UACR", value_key="metric_latest_uacr")],
                [MetricSpec(label="LDL-C", value_key="metric_latest_ldl")],
                [MetricSpec(label="最終眼科受診", value_key="metric_eye_exam")],
            ],
        ),
        TabsSpec(
            labels=["HbA1c推移", "腎機能推移"],
            tabs=[
                [
                    LineChartSpec(
                        data_key="chart_a1c_trend",
                        x="検査日",
                        y="HbA1c",
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
        MetricSpec(label="最終足チェック", value_key="metric_foot_check"),
        MarkdownSpec(
            body=(
                "### 治療・生活\n"
                "薬物療法の役割を確認し、服薬継続、食事、運動、家庭血圧、足セルフチェックを診察で聞き取ります。"
            )
        ),
        BarChartSpec(
            data_key="chart_medication_categories",
            x="カテゴリ",
            y="薬剤数",
            height=300,
        ),
        BarChartSpec(
            data_key="chart_lifestyle_adherence",
            x="項目",
            y="達成率",
            height=300,
        ),
        MarkdownSpec(
            body=(
                "### 本日の診察メモ\n"
                "検査値だけでなく、低血糖、服薬負担、感染症状、眼科/足チェックの予定を確認します。"
            )
        ),
        MetricSpec(label="本日の論点", value_key="metric_visit_issue"),
        MetricSpec(label="次回までのToDo", value_key="metric_next_todo"),
        MarkdownSpec(
            body=(
                "#### 参考にした確認観点\n"
                "- A1Cと血圧・体重を外来ごとに確認\n"
                "- eGFR/UACR、脂質、眼科、足チェックを定期確認\n"
                "- 薬剤の心腎保護、服薬継続、食事・運動・セルフケアを合わせて確認"
            )
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
