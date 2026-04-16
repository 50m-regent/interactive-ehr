"""レイアウト系ウィジェットのスキーマ定義.

対応するStreamlit関数:
- st.columns, st.tabs, st.expander
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from interactive_ehr.widgets._base import WidgetSpec, WidgetType

if TYPE_CHECKING:
    from interactive_ehr.widgets import AnyWidget


class ColumnsSpec(WidgetSpec):
    """st.columns — カラムレイアウト.

    メトリクスの横並び表示、テーブルとチャートの並列表示などに使用。
    """

    widget_type: Literal[WidgetType.COLUMNS] = WidgetType.COLUMNS
    columns: list[
        Annotated[list["AnyWidget"], Field(description="カラム内のウィジェット")]
    ] = Field(min_length=1, description="各カラムに配置するウィジェットのリスト")
    widths: list[float] | None = Field(
        None, description="各カラムの相対幅。Noneで均等分割"
    )
    gap: Literal["small", "medium", "large"] = Field(
        "small", description="カラム間のギャップ"
    )

    @model_validator(mode="after")
    def _validate_widths_length(self) -> ColumnsSpec:
        if self.widths is not None and len(self.widths) != len(self.columns):
            raise ValueError(
                f"widths length ({len(self.widths)}) must equal "
                f"columns length ({len(self.columns)})"
            )
        return self


class TabsSpec(WidgetSpec):
    """st.tabs — タブレイアウト.

    カテゴリ別データ表示（検査結果/処方/バイタル等）の切り替えに使用。
    """

    widget_type: Literal[WidgetType.TABS] = WidgetType.TABS
    labels: list[str] = Field(min_length=1, description="タブのラベルリスト")
    tabs: list[
        Annotated[list["AnyWidget"], Field(description="タブ内のウィジェット")]
    ] = Field(min_length=1, description="各タブに配置するウィジェットのリスト")

    @model_validator(mode="after")
    def _validate_labels_tabs_match(self) -> TabsSpec:
        if len(self.labels) != len(self.tabs):
            raise ValueError(
                f"labels length ({len(self.labels)}) must equal "
                f"tabs length ({len(self.tabs)})"
            )
        return self


class ExpanderSpec(WidgetSpec):
    """st.expander — 折りたたみセクション.

    詳細情報の表示/非表示切替に使用。
    """

    widget_type: Literal[WidgetType.EXPANDER] = WidgetType.EXPANDER
    label: str = Field(description="セクションのラベル")
    expanded: bool = Field(False, description="初期状態で展開するか")
    children: list["AnyWidget"] = Field(
        min_length=1, description="セクション内のウィジェットリスト"
    )
