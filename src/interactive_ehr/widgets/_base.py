"""ウィジェットスキーマの基底クラスと型定義."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class WidgetType(str, Enum):
    """LLMが指定可能なウィジェット種別."""

    # データ表示系
    DATAFRAME = "dataframe"
    TABLE = "table"
    METRIC = "metric"
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"

    # チャート系
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"

    # 入力/フィルタ系
    SELECTBOX = "selectbox"
    MULTISELECT = "multiselect"
    DATE_INPUT = "date_input"
    TIME_INPUT = "time_input"
    TEXT_INPUT = "text_input"
    TEXT_AREA = "text_area"
    NUMBER_INPUT = "number_input"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SLIDER = "slider"

    # レイアウト系
    COLUMNS = "columns"
    TABS = "tabs"
    EXPANDER = "expander"


class WidgetSpec(BaseModel):
    """全ウィジェットスキーマの基底クラス.

    LLMがJSON出力するウィジェット仕様の共通インターフェース。
    widget_type で discriminated union としてパースする。
    """

    model_config = ConfigDict(frozen=True)

    widget_type: WidgetType
