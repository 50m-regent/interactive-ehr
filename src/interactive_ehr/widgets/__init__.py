"""ウィジェットスキーマ定義.

LLMが動的にUI構成を出力するためのPydanticモデル群。
AnyWidget 型を使ってdiscriminated unionとしてパース可能。
"""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field

from interactive_ehr.widgets._base import WidgetSpec, WidgetType
from interactive_ehr.widgets.chart import BarChartSpec, LineChartSpec
from interactive_ehr.widgets.display import (
    DataframeSpec,
    JsonSpec,
    MarkdownSpec,
    MetricSpec,
    TableSpec,
    TextSpec,
)
from interactive_ehr.widgets.input import (
    CheckboxSpec,
    DateInputSpec,
    MultiselectSpec,
    NumberInputSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TextAreaSpec,
    TextInputSpec,
    TimeInputSpec,
)
from interactive_ehr.widgets.layout import ColumnsSpec, ExpanderSpec, TabsSpec
from interactive_ehr.widgets.renderer import render_widget, render_widgets

AnyWidget = Annotated[
    Union[
        # データ表示系
        DataframeSpec,
        TableSpec,
        MetricSpec,
        JsonSpec,
        MarkdownSpec,
        TextSpec,
        # チャート系
        LineChartSpec,
        BarChartSpec,
        # 入力/フィルタ系
        SelectboxSpec,
        MultiselectSpec,
        DateInputSpec,
        TimeInputSpec,
        TextInputSpec,
        TextAreaSpec,
        NumberInputSpec,
        CheckboxSpec,
        RadioSpec,
        SliderSpec,
        # レイアウト系
        ColumnsSpec,
        TabsSpec,
        ExpanderSpec,
    ],
    Field(discriminator="widget_type"),
]
"""全ウィジェットのdiscriminated union型.

LLMのJSON出力を `TypeAdapter(list[AnyWidget]).validate_json(...)` でパース可能。
"""

# レイアウト系のforward reference (AnyWidget) を解決
if not ColumnsSpec.__pydantic_complete__:
    ColumnsSpec.model_rebuild()
if not TabsSpec.__pydantic_complete__:
    TabsSpec.model_rebuild()
if not ExpanderSpec.__pydantic_complete__:
    ExpanderSpec.model_rebuild()

__all__ = [
    "AnyWidget",
    "BarChartSpec",
    "CheckboxSpec",
    "ColumnsSpec",
    "DataframeSpec",
    "DateInputSpec",
    "ExpanderSpec",
    "JsonSpec",
    "LineChartSpec",
    "MarkdownSpec",
    "MetricSpec",
    "MultiselectSpec",
    "NumberInputSpec",
    "RadioSpec",
    "SelectboxSpec",
    "SliderSpec",
    "TableSpec",
    "TabsSpec",
    "TextAreaSpec",
    "TextInputSpec",
    "TextSpec",
    "TimeInputSpec",
    "WidgetSpec",
    "WidgetType",
    "render_widget",
    "render_widgets",
]
