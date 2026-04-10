"""入力/フィルタ系ウィジェットのスキーマ定義.

対応するStreamlit関数:
- st.selectbox, st.multiselect, st.date_input, st.time_input,
  st.text_input, st.text_area, st.number_input, st.checkbox,
  st.radio, st.slider
"""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import Field, model_validator

from interactive_ehr.widgets._base import WidgetSpec, WidgetType


class SelectboxSpec(WidgetSpec):
    """st.selectbox — ドロップダウン単一選択.

    患者選択、テーブル選択、診療科選択などに使用。
    """

    widget_type: Literal[WidgetType.SELECTBOX] = WidgetType.SELECTBOX
    label: str = Field(description="ラベル")
    options_key: str = Field(description="選択肢リストのデータキー")
    default_index: int = Field(
        0, ge=0, description="デフォルトで選択されるインデックス"
    )
    placeholder: str | None = Field(None, description="未選択時のプレースホルダー")


class MultiselectSpec(WidgetSpec):
    """st.multiselect — 複数選択ドロップダウン.

    表示カラム選択、フィルタ条件の複数指定などに使用。
    """

    widget_type: Literal[WidgetType.MULTISELECT] = WidgetType.MULTISELECT
    label: str = Field(description="ラベル")
    options_key: str = Field(description="選択肢リストのデータキー")
    default_keys: list[str] | None = Field(
        None, description="デフォルトで選択される値のリスト"
    )
    max_selections: int | None = Field(
        None, gt=0, description="最大選択数。Noneで無制限"
    )
    placeholder: str | None = Field(None, description="未選択時のプレースホルダー")


class DateInputSpec(WidgetSpec):
    """st.date_input — 日付ピッカー.

    期間フィルタ、検査日指定などに使用。
    """

    widget_type: Literal[WidgetType.DATE_INPUT] = WidgetType.DATE_INPUT
    label: str = Field(description="ラベル")
    default_value: date | None = Field(
        None, description="デフォルト値。Noneで今日の日付"
    )
    min_value: date | None = Field(None, description="選択可能な最小日付")
    max_value: date | None = Field(None, description="選択可能な最大日付")

    @model_validator(mode="after")
    def _validate_date_range(self) -> DateInputSpec:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError(
                f"min_value ({self.min_value}) must be <= max_value ({self.max_value})"
            )
        return self


class TimeInputSpec(WidgetSpec):
    """st.time_input — 時刻ピッカー.

    時刻フィルタ、投薬時刻指定などに使用。
    """

    widget_type: Literal[WidgetType.TIME_INPUT] = WidgetType.TIME_INPUT
    label: str = Field(description="ラベル")
    default_value: time | None = Field(
        None, description="デフォルト値。Noneで現在時刻"
    )
    step_seconds: int = Field(
        900, gt=0, description="時刻のステップ（秒）。デフォルト15分"
    )


class TextInputSpec(WidgetSpec):
    """st.text_input — 単一行テキスト入力.

    テキスト検索、患者ID入力などに使用。
    """

    widget_type: Literal[WidgetType.TEXT_INPUT] = WidgetType.TEXT_INPUT
    label: str = Field(description="ラベル")
    default_value: str = Field("", description="デフォルト値")
    max_chars: int | None = Field(None, gt=0, description="最大入力文字数")
    placeholder: str | None = Field(None, description="プレースホルダー")


class TextAreaSpec(WidgetSpec):
    """st.text_area — 複数行テキスト入力.

    所見テキストの入力、メモ記入などに使用。
    """

    widget_type: Literal[WidgetType.TEXT_AREA] = WidgetType.TEXT_AREA
    label: str = Field(description="ラベル")
    default_value: str = Field("", description="デフォルト値")
    max_chars: int | None = Field(None, gt=0, description="最大入力文字数")
    height: int | None = Field(None, gt=0, description="テキストエリアの高さ（px）")
    placeholder: str | None = Field(None, description="プレースホルダー")


class NumberInputSpec(WidgetSpec):
    """st.number_input — 数値入力.

    検査値の閾値設定、数量指定などに使用。
    """

    widget_type: Literal[WidgetType.NUMBER_INPUT] = WidgetType.NUMBER_INPUT
    label: str = Field(description="ラベル")
    min_value: float | None = Field(None, description="最小値")
    max_value: float | None = Field(None, description="最大値")
    default_value: float | None = Field(None, description="デフォルト値")
    step: float | None = Field(None, gt=0, description="増減ステップ")
    format_str: str | None = Field(
        None, description="表示フォーマット（例: '%.2f'）"
    )

    @model_validator(mode="after")
    def _validate_number_range(self) -> NumberInputSpec:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError(
                f"min_value ({self.min_value}) must be <= max_value ({self.max_value})"
            )
        return self


class CheckboxSpec(WidgetSpec):
    """st.checkbox — チェックボックス.

    表示/非表示の切り替え、オプション有効化に使用。
    """

    widget_type: Literal[WidgetType.CHECKBOX] = WidgetType.CHECKBOX
    label: str = Field(description="ラベル")
    default_value: bool = Field(False, description="デフォルト値")


class RadioSpec(WidgetSpec):
    """st.radio — ラジオボタン.

    排他的な選択肢（表示モード切替、ソート順選択など）に使用。
    """

    widget_type: Literal[WidgetType.RADIO] = WidgetType.RADIO
    label: str = Field(description="ラベル")
    options_key: str = Field(description="選択肢リストのデータキー")
    default_index: int = Field(
        0, ge=0, description="デフォルトで選択されるインデックス"
    )
    horizontal: bool = Field(False, description="選択肢を横並びにするか")


class SliderSpec(WidgetSpec):
    """st.slider — スライダー.

    数値範囲フィルタ、日付範囲選択などに使用。
    """

    widget_type: Literal[WidgetType.SLIDER] = WidgetType.SLIDER
    label: str = Field(description="ラベル")
    min_value: float = Field(description="最小値")
    max_value: float = Field(description="最大値")
    default_value: float | tuple[float, float] | None = Field(
        None,
        description="デフォルト値。タプルで範囲スライダー。Noneで最小値",
    )
    step: float | None = Field(None, gt=0, description="ステップ")

    @model_validator(mode="after")
    def _validate_slider_range(self) -> SliderSpec:
        if self.min_value >= self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) must be < max_value ({self.max_value})"
            )
        if self.default_value is not None:
            if isinstance(self.default_value, tuple):
                low, high = self.default_value
                if low > high:
                    raise ValueError(
                        f"range default low ({low}) must be <= high ({high})"
                    )
                if low < self.min_value or high > self.max_value:
                    raise ValueError(
                        f"range default ({low}, {high}) must be within "
                        f"[{self.min_value}, {self.max_value}]"
                    )
            elif (
                self.default_value < self.min_value
                or self.default_value > self.max_value
            ):
                raise ValueError(
                    f"default_value ({self.default_value}) must be within "
                    f"[{self.min_value}, {self.max_value}]"
                )
        return self
