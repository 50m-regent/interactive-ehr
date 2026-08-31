"""臨床UIに表示するデータの来歴要約を構築する。"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

import pandas as pd


_SOURCE_TABLE_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+"((?:""|[^"])*)"',
    flags=re.IGNORECASE,
)
_DATE_COLUMN_MARKERS = (
    "date",
    "time",
    "日時",
    "年月日",
    "報告日",
    "検査日",
    "測定日",
    "予定日",
    "実施日",
    "開始日",
    "終了日",
    "入力日",
    "更新日",
)
_AGGREGATION_MARKERS = (
    " group by ",
    " count(",
    " max(",
    " min(",
    " avg(",
    " sum(",
    " group_concat(",
    " row_number(",
)


class DataNodeView(Protocol):
    """来歴要約に必要なDataNodeの属性。"""

    id: str
    context_key: str
    model_name: str | None
    description: str
    sql: str | None


@dataclass(frozen=True)
class DataProvenanceSummary:
    """一つのデータノードについて画面へ表示する来歴要約。"""

    node_id: str
    description: str
    sources: tuple[str, ...]
    latest_recorded_at: datetime | None
    row_count: int
    status: str
    transformation: str
    sql: str | None

    def as_row(self) -> dict[str, str]:
        """Streamlitの表で表示できる文字列辞書へ変換する。"""

        return {
            "表示内容": self.description,
            "情報源": "、".join(self.sources),
            "最終データ日時": format_timestamp(self.latest_recorded_at),
            "件数": f"{self.row_count}件",
            "状態": self.status,
            "取得処理": self.transformation,
        }


def summarize_data_nodes(
    data_nodes: Iterable[DataNodeView],
    context: Mapping[str, object],
) -> list[DataProvenanceSummary]:
    """データノードと表示コンテキストから来歴要約を作る。"""

    summaries: list[DataProvenanceSummary] = []
    seen_node_ids: set[str] = set()
    for data_node in data_nodes:
        if data_node.id in seen_node_ids:
            continue
        seen_node_ids.add(data_node.id)
        value = context.get(data_node.context_key)
        summaries.append(
            DataProvenanceSummary(
                node_id=data_node.id,
                description=data_node.description,
                sources=source_names_for_node(data_node),
                latest_recorded_at=latest_datetime_from_value(value),
                row_count=row_count_for_value(value),
                status=data_status_for_value(value),
                transformation=transformation_label(data_node),
                sql=data_node.sql,
            )
        )
    return summaries


def source_overview(
    summaries: Sequence[DataProvenanceSummary],
) -> tuple[str, str]:
    """タスク見出しに置く情報源一覧と最終日時を返す。"""

    source_names = list(
        dict.fromkeys(source for summary in summaries for source in summary.sources)
    )
    if len(source_names) > 3:
        source_text = "、".join(source_names[:3]) + f" ほか{len(source_names) - 3}件"
    else:
        source_text = "、".join(source_names) or "未設定"

    recorded_times = [
        summary.latest_recorded_at
        for summary in summaries
        if summary.latest_recorded_at is not None
    ]
    latest_text = (
        format_timestamp(max(recorded_times)) if recorded_times else "確認できません"
    )
    return source_text, latest_text


def source_names_for_node(data_node: DataNodeView) -> tuple[str, ...]:
    """SQLまたはモデル名から情報源名を抽出する。"""

    if data_node.sql is not None:
        tables = [
            table_name.replace('""', '"')
            for table_name in _SOURCE_TABLE_PATTERN.findall(data_node.sql)
        ]
        if tables:
            return tuple(dict.fromkeys(tables))
    if data_node.model_name is not None:
        return (data_node.model_name,)
    return ("表示コンテキスト",)


def latest_datetime_from_value(value: object) -> datetime | None:
    """表形式データに含まれる日付列から最新日時を求める。"""

    if not isinstance(value, pd.DataFrame) or value.empty:
        return None

    latest_timestamp: pd.Timestamp | None = None
    for column in value.columns:
        column_name = str(column).lower()
        if not any(marker in column_name for marker in _DATE_COLUMN_MARKERS):
            continue
        series = value[column]
        if pd.api.types.is_numeric_dtype(series):
            continue
        parsed = pd.to_datetime(series, errors="coerce", format="mixed").dropna()
        if parsed.empty:
            continue
        column_latest = cast(pd.Timestamp, pd.Timestamp(parsed.max()))
        if latest_timestamp is None or column_latest > latest_timestamp:
            latest_timestamp = column_latest
    return None if latest_timestamp is None else latest_timestamp.to_pydatetime()


def row_count_for_value(value: object) -> int:
    """表示値の件数を返す。"""

    if value is None:
        return 0
    if isinstance(value, pd.DataFrame):
        return len(value.index)
    if isinstance(value, Mapping):
        return 1 if value else 0
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return len(value)
    return 1


def data_status_for_value(value: object) -> str:
    """表示値の取得状態と欠損状態を短い文言で返す。"""

    if value is None:
        return "未取得"
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return "0件"
        return "一部欠損" if value.isna().any(axis=None) else "取得済み"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        if not value:
            return "0件"
        return "一部欠損" if any(item is None for item in value) else "取得済み"
    return "取得済み"


def transformation_label(data_node: DataNodeView) -> str:
    """データノードの取得処理を利用者向けの文言へ変換する。"""

    if data_node.sql is None:
        return "直接参照"
    normalized_sql = " " + " ".join(data_node.sql.lower().split()) + " "
    if normalized_sql.lstrip().startswith("with ") or any(
        marker in normalized_sql for marker in _AGGREGATION_MARKERS
    ):
        return "集約・抽出"
    return "抽出"


def format_timestamp(value: datetime | None) -> str:
    """来歴表示用に日時を整形する。"""

    if value is None:
        return "確認できません"
    if value.hour == 0 and value.minute == 0 and value.second == 0:
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M")
