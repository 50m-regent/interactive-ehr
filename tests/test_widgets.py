"""ウィジェットスキーマのテスト."""

from __future__ import annotations

import json
from datetime import date, time

import pytest
from pydantic import TypeAdapter, ValidationError

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
    NumberInputSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TableSpec,
    TabsSpec,
    TextAreaSpec,
    TextInputSpec,
    TextSpec,
    TimeInputSpec,
    WidgetType,
)

AnyWidgetAdapter = TypeAdapter(AnyWidget)
WidgetListAdapter = TypeAdapter(list[AnyWidget])


class TestDisplayWidgets:
    """データ表示系ウィジェットのテスト."""

    def test_dataframe_spec(self) -> None:
        spec = DataframeSpec(data_key="検体検査結果")
        assert spec.widget_type == WidgetType.DATAFRAME
        assert spec.data_key == "検体検査結果"
        assert spec.hide_index is True
        assert spec.column_order is None

    def test_dataframe_with_columns(self) -> None:
        spec = DataframeSpec(
            data_key="検体検査結果",
            column_order=["匿名ID", "検査項目名", "結果値"],
            hide_index=False,
            height=400,
        )
        assert spec.column_order == ["匿名ID", "検査項目名", "結果値"]
        assert spec.height == 400

    def test_table_spec(self) -> None:
        spec = TableSpec(data_key="患者基本")
        assert spec.widget_type == WidgetType.TABLE

    def test_metric_spec(self) -> None:
        spec = MetricSpec(label="体温", value_key="体温")
        assert spec.widget_type == WidgetType.METRIC
        assert spec.delta_color == "normal"

    def test_metric_with_delta(self) -> None:
        spec = MetricSpec(
            label="血圧(最高)",
            value_key="血圧_最高",
            delta_key="血圧_最高_変化",
            delta_color="inverse",
        )
        assert spec.delta_key == "血圧_最高_変化"
        assert spec.delta_color == "inverse"

    def test_json_spec(self) -> None:
        spec = JsonSpec(data_key="raw_data")
        assert spec.expanded is True

    def test_markdown_spec(self) -> None:
        spec = MarkdownSpec(body="# 所見\n正常範囲内")
        assert spec.widget_type == WidgetType.MARKDOWN

    def test_text_spec(self) -> None:
        spec = TextSpec(body="プレインテキスト")
        assert spec.widget_type == WidgetType.TEXT


class TestChartWidgets:
    """チャート系ウィジェットのテスト."""

    def test_line_chart_spec(self) -> None:
        spec = LineChartSpec(data_key="バイタル推移")
        assert spec.widget_type == WidgetType.LINE_CHART
        assert spec.x is None
        assert spec.y is None

    def test_line_chart_with_axes(self) -> None:
        spec = LineChartSpec(
            data_key="バイタル推移",
            x="測定日",
            y=["体温", "脈拍"],
            x_label="日付",
            y_label="値",
        )
        assert spec.y == ["体温", "脈拍"]

    def test_bar_chart_spec(self) -> None:
        spec = BarChartSpec(data_key="診療科別統計", horizontal=True)
        assert spec.horizontal is True


class TestInputWidgets:
    """入力/フィルタ系ウィジェットのテスト."""

    def test_selectbox_spec(self) -> None:
        spec = SelectboxSpec(label="患者選択", options_key="患者リスト")
        assert spec.widget_type == WidgetType.SELECTBOX
        assert spec.default_index == 0

    def test_multiselect_spec(self) -> None:
        spec = MultiselectSpec(
            label="表示カラム",
            options_key="カラムリスト",
            max_selections=5,
        )
        assert spec.max_selections == 5

    def test_date_input_spec(self) -> None:
        spec = DateInputSpec(
            label="検査日",
            default_value=date(2025, 1, 1),
            min_value=date(2020, 1, 1),
        )
        assert spec.default_value == date(2025, 1, 1)

    def test_time_input_spec(self) -> None:
        spec = TimeInputSpec(label="投薬時刻", default_value=time(9, 0))
        assert spec.step_seconds == 900

    def test_text_input_spec(self) -> None:
        spec = TextInputSpec(label="患者ID", placeholder="IDを入力")
        assert spec.default_value == ""

    def test_text_area_spec(self) -> None:
        spec = TextAreaSpec(label="メモ", height=200)
        assert spec.widget_type == WidgetType.TEXT_AREA

    def test_number_input_spec(self) -> None:
        spec = NumberInputSpec(
            label="閾値",
            min_value=0.0,
            max_value=100.0,
            default_value=50.0,
            step=0.1,
        )
        assert spec.step == 0.1

    def test_checkbox_spec(self) -> None:
        spec = CheckboxSpec(label="詳細表示", default_value=True)
        assert spec.default_value is True

    def test_radio_spec(self) -> None:
        spec = RadioSpec(
            label="ソート順", options_key="ソート選択肢", horizontal=True
        )
        assert spec.horizontal is True

    def test_slider_spec(self) -> None:
        spec = SliderSpec(label="年齢範囲", min_value=0, max_value=120)
        assert spec.default_value is None

    def test_slider_range(self) -> None:
        spec = SliderSpec(
            label="年齢範囲",
            min_value=0,
            max_value=120,
            default_value=(20, 80),
        )
        assert spec.default_value == (20, 80)


class TestLayoutWidgets:
    """レイアウト系ウィジェットのテスト."""

    def test_columns_spec(self) -> None:
        spec = ColumnsSpec(
            columns=[
                [MetricSpec(label="体温", value_key="体温")],
                [MetricSpec(label="脈拍", value_key="脈拍")],
            ]
        )
        assert len(spec.columns) == 2
        assert spec.columns[0][0].widget_type == WidgetType.METRIC

    def test_tabs_spec(self) -> None:
        spec = TabsSpec(
            labels=["検査結果", "処方"],
            tabs=[
                [DataframeSpec(data_key="検体検査結果")],
                [DataframeSpec(data_key="処方")],
            ],
        )
        assert spec.labels == ["検査結果", "処方"]
        assert len(spec.tabs) == 2

    def test_expander_spec(self) -> None:
        spec = ExpanderSpec(
            label="詳細情報",
            expanded=True,
            children=[TextSpec(body="詳細テキスト")],
        )
        assert spec.expanded is True
        assert len(spec.children) == 1

    def test_nested_layout(self) -> None:
        """ネストしたレイアウトのテスト."""
        spec = TabsSpec(
            labels=["概要", "詳細"],
            tabs=[
                [
                    ColumnsSpec(
                        columns=[
                            [MetricSpec(label="体温", value_key="体温")],
                            [MetricSpec(label="脈拍", value_key="脈拍")],
                        ]
                    )
                ],
                [
                    ExpanderSpec(
                        label="検査結果",
                        children=[DataframeSpec(data_key="検体検査結果")],
                    )
                ],
            ],
        )
        assert spec.tabs[0][0].widget_type == WidgetType.COLUMNS


class TestValidation:
    """バリデーションのテスト."""

    def test_tabs_labels_tabs_mismatch(self) -> None:
        with pytest.raises(ValidationError, match="labels length"):
            TabsSpec(
                labels=["a", "b", "c"],
                tabs=[[TextSpec(body="x")], [TextSpec(body="y")]],
            )

    def test_tabs_empty_labels(self) -> None:
        with pytest.raises(ValidationError):
            TabsSpec(labels=[], tabs=[])

    def test_columns_empty(self) -> None:
        with pytest.raises(ValidationError):
            ColumnsSpec(columns=[])

    def test_columns_widths_mismatch(self) -> None:
        with pytest.raises(ValidationError, match="widths length"):
            ColumnsSpec(
                columns=[[TextSpec(body="a")], [TextSpec(body="b")]],
                widths=[1.0],
            )

    def test_slider_min_ge_max(self) -> None:
        with pytest.raises(ValidationError, match="min_value"):
            SliderSpec(label="x", min_value=100, max_value=0)

    def test_slider_default_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="default_value"):
            SliderSpec(label="x", min_value=0, max_value=10, default_value=20)

    def test_slider_range_default_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="range default"):
            SliderSpec(
                label="x", min_value=0, max_value=10, default_value=(5, 20)
            )

    def test_date_input_min_gt_max(self) -> None:
        with pytest.raises(ValidationError, match="min_value"):
            DateInputSpec(
                label="x",
                min_value=date(2025, 12, 31),
                max_value=date(2025, 1, 1),
            )

    def test_number_input_min_gt_max(self) -> None:
        with pytest.raises(ValidationError, match="min_value"):
            NumberInputSpec(label="x", min_value=100, max_value=0)

    def test_selectbox_negative_index(self) -> None:
        with pytest.raises(ValidationError):
            SelectboxSpec(label="x", options_key="k", default_index=-1)

    def test_multiselect_negative_max_selections(self) -> None:
        with pytest.raises(ValidationError):
            MultiselectSpec(label="x", options_key="k", max_selections=-1)

    def test_negative_height_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataframeSpec(data_key="x", height=-100)

    def test_key_field_on_all_widgets(self) -> None:
        spec = SelectboxSpec(
            label="x", options_key="k", key="unique_selectbox_1"
        )
        assert spec.key == "unique_selectbox_1"


class TestDiscriminatedUnion:
    """discriminated unionによるパーステスト."""

    def test_parse_single_widget(self) -> None:
        data = {"widget_type": "dataframe", "data_key": "患者基本"}
        widget = AnyWidgetAdapter.validate_python(data)
        assert isinstance(widget, DataframeSpec)
        assert widget.data_key == "患者基本"

    def test_parse_widget_list(self) -> None:
        data = [
            {"widget_type": "metric", "label": "体温", "value_key": "体温"},
            {"widget_type": "markdown", "body": "# 所見"},
            {
                "widget_type": "selectbox",
                "label": "患者",
                "options_key": "患者リスト",
            },
        ]
        widgets = WidgetListAdapter.validate_python(data)
        assert len(widgets) == 3
        assert isinstance(widgets[0], MetricSpec)
        assert isinstance(widgets[1], MarkdownSpec)
        assert isinstance(widgets[2], SelectboxSpec)

    def test_parse_from_json(self) -> None:
        json_str = json.dumps(
            {"widget_type": "line_chart", "data_key": "バイタル", "x": "日付"}
        )
        widget = AnyWidgetAdapter.validate_json(json_str)
        assert isinstance(widget, LineChartSpec)
        assert widget.x == "日付"

    def test_parse_nested_layout_from_json(self) -> None:
        data = {
            "widget_type": "columns",
            "columns": [
                [{"widget_type": "metric", "label": "体温", "value_key": "t"}],
                [{"widget_type": "text", "body": "正常"}],
            ],
        }
        widget = AnyWidgetAdapter.validate_python(data)
        assert isinstance(widget, ColumnsSpec)
        assert isinstance(widget.columns[0][0], MetricSpec)
        assert isinstance(widget.columns[1][0], TextSpec)

    def test_invalid_widget_type(self) -> None:
        with pytest.raises(ValidationError):
            AnyWidgetAdapter.validate_python(
                {"widget_type": "invalid_widget", "data": "test"}
            )


class TestFrozen:
    """不変性のテスト."""

    def test_widget_is_frozen(self) -> None:
        spec = DataframeSpec(data_key="test")
        with pytest.raises(ValidationError):
            spec.data_key = "modified"  # type: ignore[misc]

    def test_nested_widget_is_frozen(self) -> None:
        spec = ColumnsSpec(
            columns=[[MetricSpec(label="a", value_key="b")]]
        )
        with pytest.raises(ValidationError):
            spec.columns = []  # type: ignore[misc]
