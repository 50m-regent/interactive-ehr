"""レイアウト系ウィジェットのスキーマ定義.

対応するStreamlit関数:
- st.columns, st.tabs, st.expander
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field

from interactive_ehr.widgets._base import WidgetSpec, WidgetType

if TYPE_CHECKING:
    from interactive_ehr.widgets import AnyWidget


class ColumnsSpec(WidgetSpec):
    """st.columns — カラムレイアウト.

    メトリクスの横並び表示、テーブルとチャートの並列表示などに使用。
    """

    widget_type: Literal[WidgetType.COLUMNS] = WidgetType.COLUMNS
    columns: list[Annotated[list["AnyWidget"], Field(description="カラム内のウィジェット")]] = (
        Field(description="各カラムに配置するウィジェットのリスト")
    )


class TabsSpec(WidgetSpec):
    """st.tabs — タブレイアウト.

    カテゴリ別データ表示（検査結果/処方/バイタル等）の切り替えに使用。
    """

    widget_type: Literal[WidgetType.TABS] = WidgetType.TABS
    labels: list[str] = Field(description="タブのラベルリスト")
    tabs: list[Annotated[list["AnyWidget"], Field(description="タブ内のウィジェット")]] = (
        Field(description="各タブに配置するウィジェットのリスト")
    )


class ExpanderSpec(WidgetSpec):
    """st.expander — 折りたたみセクション.

    詳細情報の表示/非表示切替に使用。
    """

    widget_type: Literal[WidgetType.EXPANDER] = WidgetType.EXPANDER
    label: str = Field(description="セクションのラベル")
    expanded: bool = Field(False, description="初期状態で展開するか")
    children: list["AnyWidget"] = Field(
        description="セクション内のウィジェットリスト"
    )
