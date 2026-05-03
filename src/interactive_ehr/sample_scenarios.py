"""Fixed sample scenarios for local UI verification."""

from __future__ import annotations

from datetime import date

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
    CheckboxSpec,
    ColumnsSpec,
    DataframeSpec,
    DateInputSpec,
    ExpanderSpec,
    JsonSpec,
    LineChartSpec,
    MarkdownSpec,
    MetricSpec,
    MultiselectSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TableSpec,
    TabsSpec,
    TextInputSpec,
)


def get_chronic_disease_graph_scenario() -> tuple[ScenarioGraph, dict[str, object]]:
    """Return the chronic disease outpatient sample as a task graph."""

    widgets, context = get_chronic_disease_scenario()
    data_nodes = [
        DataNode(
            id=f"data_{index}",
            context_key=context_key,
            data_type=_describe_context_type(value),
            description=f"固定サンプル context['{context_key}']",
            primary_fields=_primary_fields(value),
        )
        for index, (context_key, value) in enumerate(context.items(), start=1)
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
        title="慢性疾患を持つ高齢患者の外来診察",
        description="複数の慢性疾患を持つ高齢患者の定期外来を想定した検証用シナリオ。",
        tasks=[
            TaskNode(
                id="task_outpatient_review",
                title="外来診察",
                description="患者選択、主要指標、検査・処方・カルテ確認を行う。",
                order=1,
                widget_ids=[node.id for node in widget_nodes],
            )
        ],
        data_nodes=data_nodes,
        widget_nodes=widget_nodes,
        edges=[
            GraphEdge(
                source_id="chronic_disease_outpatient",
                target_id="task_outpatient_review",
                edge_type="scenario_to_task",
            ),
            *[
                GraphEdge(
                    source_id="task_outpatient_review",
                    target_id=node.id,
                    edge_type="task_to_widget",
                )
                for node in widget_nodes
            ],
            *[
                GraphEdge(
                    source_id=widget_node.id,
                    target_id=data_node_id,
                    edge_type="widget_to_data",
                )
                for widget_node in widget_nodes
                for data_node_id in widget_node.data_node_ids
            ],
        ],
    )
    return graph, context


def get_chronic_disease_scenario() -> tuple[list[AnyWidget], dict[str, object]]:
    """Return a reproducible chronic disease outpatient sample."""

    context: dict[str, object] = {
        "患者候補": ["P000317 山田 花子", "P000822 佐藤 一郎"],
        "表示カテゴリ": ["概要", "検査", "処方", "カルテ"],
        "診察目的": ["定期外来", "検査値悪化の確認", "服薬調整"],
        "patient_summary": [
            {
                "匿名ID": "P000317",
                "年齢": 78,
                "性別": "女性",
                "主病名": "2型糖尿病、慢性腎臓病、高血圧症",
                "受診日": "2026-04-20",
                "診療科": "腎臓・糖尿病内科",
            }
        ],
        "systolic_bp": "148 mmHg",
        "systolic_bp_delta": "+6",
        "hba1c": "7.4 %",
        "hba1c_delta": "+0.2",
        "egfr": "38.2 mL/min/1.73m2",
        "egfr_delta": "-2.1",
        "ldl": "112 mg/dL",
        "ldl_delta": "-8",
        "bp_trend": pd.DataFrame(
            [
                {"測定日": "2025-10-20", "収縮期血圧": 142, "拡張期血圧": 78},
                {"測定日": "2025-12-15", "収縮期血圧": 136, "拡張期血圧": 74},
                {"測定日": "2026-02-16", "収縮期血圧": 144, "拡張期血圧": 76},
                {"測定日": "2026-04-20", "収縮期血圧": 148, "拡張期血圧": 80},
            ]
        ),
        "renal_trend": pd.DataFrame(
            [
                {"検査日": "2025-10-20", "eGFR": 44.0, "Cr": 1.02},
                {"検査日": "2025-12-15", "eGFR": 42.1, "Cr": 1.08},
                {"検査日": "2026-02-16", "eGFR": 40.3, "Cr": 1.13},
                {"検査日": "2026-04-20", "eGFR": 38.2, "Cr": 1.19},
            ]
        ),
        "current_prescriptions": pd.DataFrame(
            [
                {
                    "オーダ日": "2026-04-20",
                    "薬剤名": "テルミサルタン錠40mg",
                    "用量": "1錠",
                    "用法": "朝食後",
                    "日数": 56,
                },
                {
                    "オーダ日": "2026-04-20",
                    "薬剤名": "アムロジピンOD錠5mg",
                    "用量": "1錠",
                    "用法": "朝食後",
                    "日数": 56,
                },
                {
                    "オーダ日": "2026-04-20",
                    "薬剤名": "リナグリプチン錠5mg",
                    "用量": "1錠",
                    "用法": "朝食後",
                    "日数": 56,
                },
                {
                    "オーダ日": "2026-04-20",
                    "薬剤名": "ロスバスタチン錠2.5mg",
                    "用量": "1錠",
                    "用法": "夕食後",
                    "日数": 56,
                },
            ]
        ),
        "recent_labs": pd.DataFrame(
            [
                {
                    "検査日": "2026-04-20",
                    "検査項目名": "HbA1c",
                    "結果値": "7.4",
                    "単位": "%",
                    "基準範囲": "4.6-6.2",
                },
                {
                    "検査日": "2026-04-20",
                    "検査項目名": "Cr",
                    "結果値": "1.19",
                    "単位": "mg/dL",
                    "基準範囲": "0.46-0.79",
                },
                {
                    "検査日": "2026-04-20",
                    "検査項目名": "eGFR",
                    "結果値": "38.2",
                    "単位": "mL/min/1.73m2",
                    "基準範囲": "60以上",
                },
                {
                    "検査日": "2026-04-20",
                    "検査項目名": "LDL-C",
                    "結果値": "112",
                    "単位": "mg/dL",
                    "基準範囲": "70-139",
                },
                {
                    "検査日": "2026-04-20",
                    "検査項目名": "尿蛋白",
                    "結果値": "2+",
                    "単位": "",
                    "基準範囲": "陰性",
                },
            ]
        ),
        "lab_abnormal_counts": pd.DataFrame(
            [
                {"分類": "腎機能", "件数": 3},
                {"分類": "糖代謝", "件数": 2},
                {"分類": "脂質", "件数": 1},
                {"分類": "尿検査", "件数": 2},
            ]
        ),
        "chart_notes": {
            "bp_trend": "外来血圧は直近2回で上昇傾向。",
            "renal_trend": "eGFRは半年で約6 mL/min/1.73m2低下。",
        },
    }

    widgets: list[AnyWidget] = [
        MarkdownSpec(
            body=(
                "### 慢性疾患外来サンプル\n"
                "複数の慢性疾患を持つ高齢患者の定期外来を想定した"
                "ダミーデータです。"
            )
        ),
        ColumnsSpec(
            widths=[1.4, 1.0, 1.0],
            columns=[
                [
                    SelectboxSpec(
                        label="患者",
                        options_key="患者候補",
                        key="patient_select",
                    )
                ],
                [
                    DateInputSpec(
                        label="基準日",
                        default_value=date(2026, 4, 20),
                        key="reference_date",
                    )
                ],
                [
                    CheckboxSpec(
                        label="過去カルテを表示",
                        default_value=True,
                        key="show_records",
                    )
                ],
            ],
        ),
        ColumnsSpec(
            columns=[
                [
                    MetricSpec(
                        label="収縮期血圧",
                        value_key="systolic_bp",
                        delta_key="systolic_bp_delta",
                        delta_color="inverse",
                    )
                ],
                [
                    MetricSpec(
                        label="HbA1c",
                        value_key="hba1c",
                        delta_key="hba1c_delta",
                        delta_color="inverse",
                    )
                ],
                [
                    MetricSpec(
                        label="eGFR",
                        value_key="egfr",
                        delta_key="egfr_delta",
                    )
                ],
                [
                    MetricSpec(
                        label="LDL-C",
                        value_key="ldl",
                        delta_key="ldl_delta",
                        delta_color="inverse",
                    )
                ],
            ],
        ),
        TabsSpec(
            labels=["概要", "推移", "処方・検査", "カルテ"],
            tabs=[
                [
                    TableSpec(data_key="patient_summary"),
                    MultiselectSpec(
                        label="表示カテゴリ",
                        options_key="表示カテゴリ",
                        default_keys=["概要", "検査", "処方"],
                        key="category_filter",
                    ),
                    RadioSpec(
                        label="診察目的",
                        options_key="診察目的",
                        horizontal=True,
                        key="visit_purpose",
                    ),
                    SliderSpec(
                        label="確認対象期間（月）",
                        min_value=1,
                        max_value=12,
                        default_value=6,
                        step=1,
                        key="lookback_months",
                    ),
                    TextInputSpec(
                        label="カルテ内検索",
                        placeholder="例: 浮腫、低血糖、尿蛋白",
                        key="record_search",
                    ),
                ],
                [
                    ColumnsSpec(
                        columns=[
                            [
                                LineChartSpec(
                                    data_key="bp_trend",
                                    x="測定日",
                                    y=["収縮期血圧", "拡張期血圧"],
                                    y_label="mmHg",
                                )
                            ],
                            [
                                LineChartSpec(
                                    data_key="renal_trend",
                                    x="検査日",
                                    y=["eGFR", "Cr"],
                                )
                            ],
                        ],
                    ),
                    BarChartSpec(
                        data_key="lab_abnormal_counts",
                        x="分類",
                        y="件数",
                        y_label="件数",
                    ),
                ],
                [
                    DataframeSpec(
                        data_key="current_prescriptions",
                        column_order=["薬剤名", "用量", "用法", "日数", "オーダ日"],
                        height=240,
                    ),
                    DataframeSpec(
                        data_key="recent_labs",
                        column_order=[
                            "検査項目名",
                            "結果値",
                            "単位",
                            "基準範囲",
                            "検査日",
                        ],
                        height=280,
                    ),
                ],
                [
                    ExpanderSpec(
                        label="2026-04-20 外来記事",
                        expanded=True,
                        children=[
                            MarkdownSpec(
                                body=(
                                    "**S:** 食欲は保たれている。自宅血圧は"
                                    "140台が増加。低血糖症状なし。\n\n"
                                    "**O:** 下腿浮腫軽度。HbA1c 7.4%、"
                                    "eGFR 38.2、尿蛋白2+。\n\n"
                                    "**A/P:** CKD進行リスクを説明。塩分制限と"
                                    "家庭血圧記録を継続。次回尿アルブミン確認。"
                                )
                            )
                        ],
                    ),
                    ExpanderSpec(
                        label="2026-02-16 外来記事",
                        children=[
                            MarkdownSpec(
                                body=(
                                    "血圧は外来144/76。服薬アドヒアランス良好。"
                                    "腎機能は前回から軽度低下。処方は継続。"
                                )
                            )
                        ],
                    ),
                ],
            ],
        ),
        ExpanderSpec(
            label="チャート用メモ(JSON)",
            children=[
                JsonSpec(data_key="chart_notes", expanded=True),
            ],
        ),
    ]

    return widgets, context


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
            if key.endswith("_key") and isinstance(child, str):
                keys.append(child)
            else:
                keys.extend(_collect_reference_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_collect_reference_keys(child))
    return list(dict.fromkeys(keys))
