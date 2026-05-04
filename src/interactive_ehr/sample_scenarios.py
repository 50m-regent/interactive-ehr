"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

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
    ExpanderSpec,
    LineChartSpec,
    MarkdownSpec,
    TabsSpec,
)


DEFAULT_SAMPLE_DWH_MODELS = [
    "患者基本",
    "患者プロフィール",
    "身体測定情報",
    "患者アレルギー情報",
    "入退院歴",
    "病名",
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
    tasks = _build_tasks()
    graph = ScenarioGraph(
        id="chronic_disease_outpatient",
        title="慢性疾患外来レビュー",
        description="患者背景、経過、診断・治療、記録をDWHモデル横断で確認する検証用シナリオ。",
        tasks=tasks,
        data_nodes=data_nodes,
        widget_nodes=widget_nodes,
        edges=_build_edges("chronic_disease_outpatient", tasks, widget_nodes),
    )
    return graph, context


def get_chronic_disease_scenario() -> tuple[list[AnyWidget], dict[str, object]]:
    """Return widgets and context generated only from DWH model fake data."""

    context = build_dwh_context_for_model_names(DEFAULT_SAMPLE_DWH_MODELS)
    patient_key = dwh_context_key("患者基本")
    profile_key = dwh_context_key("患者プロフィール")
    measurement_key = dwh_context_key("身体測定情報")
    allergy_key = dwh_context_key("患者アレルギー情報")
    admission_key = dwh_context_key("入退院歴")
    diagnosis_key = dwh_context_key("病名")
    lab_key = dwh_context_key("検体検査結果")
    prescription_key = dwh_context_key("処方")
    record_key = dwh_context_key("カルテ記事DR")
    vital_key = dwh_context_key("バイタル")
    widgets: list[AnyWidget] = [
        MarkdownSpec(
            body=(
                "### 慢性疾患外来レビュー\n"
                "患者背景、バイタル・検査推移、処方、病名、アレルギー、"
                "カルテ記事と入退院歴を同じDWH context経路で確認します。"
            )
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [
                    DataframeSpec(
                        data_key=patient_key,
                        column_order=[
                            "匿名ID",
                            "現在年齢",
                            "性別",
                            "生年月日",
                            "患者状態",
                            "入院回数",
                            "初来院日",
                        ],
                        height=260,
                    ),
                ],
                [
                    DataframeSpec(
                        data_key=profile_key,
                        column_order=[
                            "匿名ID",
                            "職業",
                            "身長",
                            "体重",
                            "造影剤アレルギーの有無",
                            "薬物アレルギーの有無",
                            "食物アレルギーの有無",
                        ],
                        height=260,
                    ),
                ],
            ],
        ),
        ColumnsSpec(
            widths=[1, 1],
            columns=[
                [
                    LineChartSpec(
                        data_key=vital_key,
                        x="測定日",
                        y=["体温", "脈拍", "血圧(最高)", "血圧(最低)", "SPO2"],
                        height=280,
                    ),
                ],
                [
                    LineChartSpec(
                        data_key=measurement_key,
                        x="検索日(測定日)",
                        y=["身長", "体重", "体表面積"],
                        height=280,
                    ),
                ],
            ],
        ),
        TabsSpec(
            labels=["検体検査結果", "検査推移", "処方"],
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
                    LineChartSpec(
                        data_key=lab_key,
                        x="検索日(採取日)",
                        y="結果(数値)",
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
        TabsSpec(
            labels=["病名", "アレルギー"],
            tabs=[
                [
                    DataframeSpec(
                        data_key=diagnosis_key,
                        column_order=[
                            "匿名ID",
                            "病名開始日",
                            "病名",
                            "病名(+修飾語)",
                            "主病名区分",
                            "疑い対象",
                            "転帰日",
                            "転帰区分",
                        ],
                        height=320,
                    )
                ],
                [
                    DataframeSpec(
                        data_key=allergy_key,
                        column_order=[
                            "匿名ID",
                            "診断日",
                            "アレルギー種別名",
                            "アレルギー名称",
                            "症状",
                            "診断根拠",
                            "フリーコメント",
                        ],
                        height=320,
                    )
                ],
            ],
        ),
        TabsSpec(
            labels=["カルテ記事", "入退院歴"],
            tabs=[
                [
                    DataframeSpec(
                        data_key=record_key,
                        column_order=["匿名ID", "記載日", "診療科", "記事種別", "記事", "プロブレム"],
                        height=320,
                    )
                ],
                [
                    ExpanderSpec(
                        label="入退院・紹介の詳細",
                        expanded=True,
                        children=[
                            DataframeSpec(
                                data_key=admission_key,
                                column_order=[
                                    "匿名ID",
                                    "入院日",
                                    "退院日",
                                    "在院期間",
                                    "入院時病名",
                                    "入院目的",
                                    "退院後の行方",
                                    "次回受診日",
                                ],
                                height=320,
                            )
                        ],
                    )
                ],
            ],
        ),
    ]
    return widgets, context


def _build_tasks() -> list[TaskNode]:
    return [
        TaskNode(
            id="task_patient_summary",
            title="患者背景",
            description="患者基本、プロフィール、身体測定を確認する。",
            order=1,
            widget_ids=["widget_1", "widget_2", "widget_3"],
        ),
        TaskNode(
            id="task_clinical_course",
            title="検査・処方",
            description="検体検査結果の一覧と推移、処方内容を確認する。",
            order=2,
            widget_ids=["widget_4"],
        ),
        TaskNode(
            id="task_risks_diagnoses",
            title="病名・リスク",
            description="病名とアレルギー情報を確認する。",
            order=3,
            widget_ids=["widget_5"],
        ),
        TaskNode(
            id="task_records_admissions",
            title="記録・入退院",
            description="カルテ記事と入退院歴を確認する。",
            order=4,
            widget_ids=["widget_6"],
        ),
    ]


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


def _build_edges(
    scenario_id: str,
    tasks: list[TaskNode],
    widget_nodes: list[WidgetNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    widget_by_id = {widget_node.id: widget_node for widget_node in widget_nodes}
    for task in tasks:
        edges.append(
            GraphEdge(
                source_id=scenario_id,
                target_id=task.id,
                edge_type="scenario_to_task",
            )
        )
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
