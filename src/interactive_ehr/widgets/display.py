"""データ表示系ウィジェットのスキーマ定義.

対応するStreamlit関数:
- st.dataframe, st.table, st.metric, st.json, st.markdown, st.text
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from interactive_ehr.widgets._base import WidgetSpec, WidgetType


class DataframeSpec(WidgetSpec):
    """st.dataframe — インタラクティブなテーブル表示.

    検査結果一覧、処方一覧などテーブルデータの表示に使用。
    """

    widget_type: Literal[WidgetType.DATAFRAME] = WidgetType.DATAFRAME
    data_key: str = Field(description="表示するデータのキー（テーブル名やデータソースID）")
    column_order: list[str] | None = Field(
        None, description="表示するカラムの順序。Noneで全カラム表示"
    )
    hide_index: bool = Field(True, description="インデックス列を非表示にするか")
    height: int | None = Field(None, description="テーブルの高さ（px）。Noneで自動")


class TableSpec(WidgetSpec):
    """st.table — 静的テーブル表示.

    少量データの確認用。ソートやフィルタ不要な場合に使用。
    """

    widget_type: Literal[WidgetType.TABLE] = WidgetType.TABLE
    data_key: str = Field(description="表示するデータのキー")


class MetricSpec(WidgetSpec):
    """st.metric — メトリクス表示.

    バイタルサイン、検査値などの単一指標を大きく表示。差分表示も可能。
    """

    widget_type: Literal[WidgetType.METRIC] = WidgetType.METRIC
    label: str = Field(description="メトリクスのラベル（例: '体温', '血圧(最高)'）")
    value_key: str = Field(description="値を取得するデータフィールドのキー")
    delta_key: str | None = Field(None, description="差分値を取得するフィールドのキー")
    delta_color: Literal["normal", "inverse", "off"] = Field(
        "normal",
        description="差分の色。normalは正=緑/負=赤、inverseは逆、offは色なし",
    )


class JsonSpec(WidgetSpec):
    """st.json — JSON表示.

    構造化データの詳細確認用。デバッグやデータ構造の可視化に使用。
    """

    widget_type: Literal[WidgetType.JSON] = WidgetType.JSON
    data_key: str = Field(description="表示するデータのキー")
    expanded: bool = Field(True, description="JSONツリーを展開した状態で表示するか")


class MarkdownSpec(WidgetSpec):
    """st.markdown — マークダウンテキスト表示.

    カルテ記事、所見テキスト、説明文などリッチテキストの表示に使用。
    """

    widget_type: Literal[WidgetType.MARKDOWN] = WidgetType.MARKDOWN
    body: str = Field(description="表示するマークダウンテキスト")


class TextSpec(WidgetSpec):
    """st.text — プレインテキスト表示.

    等幅フォントでのテキスト表示。コードやフォーマット済みテキストに使用。
    """

    widget_type: Literal[WidgetType.TEXT] = WidgetType.TEXT
    body: str = Field(description="表示するプレインテキスト")
