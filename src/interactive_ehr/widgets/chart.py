"""チャート系ウィジェットのスキーマ定義.

対応するStreamlit関数:
- st.line_chart, st.bar_chart
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from interactive_ehr.widgets._base import WidgetSpec, WidgetType


class _ChartSpec(WidgetSpec):
    """チャート系ウィジェットの共通基底."""

    data_key: str = Field(description="チャートデータのキー")
    x: str | None = Field(None, description="X軸のカラム名。Noneでインデックス使用")
    y: str | list[str] | None = Field(
        None, description="Y軸のカラム名。Noneで全数値カラム使用"
    )
    x_label: str | None = Field(None, description="X軸のラベル")
    y_label: str | None = Field(None, description="Y軸のラベル")
    height: int | None = Field(None, gt=0, description="チャートの高さ（px）")


class LineChartSpec(_ChartSpec):
    """st.line_chart — 折れ線チャート.

    バイタル推移、検査値推移など時系列データの可視化に使用。
    """

    widget_type: Literal[WidgetType.LINE_CHART] = WidgetType.LINE_CHART


class BarChartSpec(_ChartSpec):
    """st.bar_chart — 棒チャート.

    検査項目ごとの集計、診療科別統計など集計データの可視化に使用。
    """

    widget_type: Literal[WidgetType.BAR_CHART] = WidgetType.BAR_CHART
    horizontal: bool = Field(False, description="横向き棒グラフにするか")
