"""SQLite helpers for loading DWH CSVs and executing display SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from interactive_ehr.models.registry import DEFAULT_DWH_CSV_DIR


DEFAULT_DWH_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "dwh.sqlite"


def build_dwh_database_from_csvs(
    *,
    csv_dir: str | Path = DEFAULT_DWH_CSV_DIR,
    db_path: str | Path = DEFAULT_DWH_DB_PATH,
    overwrite: bool = False,
    include_diabetes_sample: bool = True,
) -> tuple[int, int]:
    """Load DWH CSV files into a SQLite database.

    Returns ``(loaded, skipped)`` counts. Table names are CSV stems.
    """

    csv_root = Path(csv_dir)
    sqlite_path = Path(db_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if sqlite_path.exists() and overwrite:
        sqlite_path.unlink()

    loaded = 0
    skipped = 0
    with sqlite3.connect(sqlite_path) as connection:
        for csv_path in sorted(csv_root.glob("*.csv")):
            table_name = csv_path.stem
            if not overwrite and _table_exists(connection, table_name):
                skipped += 1
                continue
            try:
                dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
            except EmptyDataError:
                skipped += 1
                continue
            dataframe.to_sql(
                table_name,
                connection,
                if_exists="replace",
                index=False,
            )
            loaded += 1
        if include_diabetes_sample:
            loaded += _load_diabetes_sample_tables(connection)
    return loaded, skipped


def execute_read_sql(
    sql: str,
    *,
    db_path: str | Path = DEFAULT_DWH_DB_PATH,
) -> pd.DataFrame:
    """Execute a read-only SELECT SQL statement against the DWH SQLite DB."""

    _validate_read_sql(sql)
    sqlite_path = Path(db_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(
            f"DWH SQLite DB が存在しません: {sqlite_path}. "
            "uv run python scripts/build_dwh_database.py --overwrite を実行してください。"
        )

    uri = f"file:{sqlite_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return pd.read_sql_query(sql, connection)


def list_database_tables(
    *,
    db_path: str | Path = DEFAULT_DWH_DB_PATH,
) -> list[str]:
    """Return table names in the DWH SQLite DB."""

    sqlite_path = Path(db_path)
    if not sqlite_path.exists():
        return []
    uri = f"file:{sqlite_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return [str(row[0]) for row in rows]


def list_table_columns(
    table_name: str,
    *,
    db_path: str | Path = DEFAULT_DWH_DB_PATH,
) -> list[str]:
    """Return column names for a table in the DWH SQLite DB."""

    sqlite_path = Path(db_path)
    if not sqlite_path.exists():
        return []
    uri = f"file:{sqlite_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(f'PRAGMA table_info("{_escape_identifier(table_name)}")').fetchall()
    return [str(row[1]) for row in rows]


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _load_diabetes_sample_tables(connection: sqlite3.Connection) -> int:
    """Load stable synthetic tables for the default diabetes outpatient scenario."""

    sample_tables = {
        "糖尿病外来_患者サマリ": pd.DataFrame(
            [
                {
                    "患者表示名": "70代男性 Aさん",
                    "年齢": 72,
                    "性別": "男性",
                    "糖尿病罹病年数": 12,
                    "最新HbA1c": 7.4,
                    "目標HbA1c": 7.0,
                    "収縮期血圧": 138,
                    "拡張期血圧": 82,
                    "BMI": 27.8,
                    "eGFR": 58,
                    "UACR": 46,
                    "LDL": 118,
                    "最終眼科受診": "2025-09-12",
                    "最終足チェック": "2026-04-18",
                    "低血糖": "なし",
                    "本日の論点": "HbA1cは改善傾向だが目標未達。腎症リスクと体重増加を踏まえて治療継続を確認。",
                    "次回ToDo": "眼科予約確認、UACR再検、家庭血圧記録、食後高血糖の聞き取り",
                }
            ]
        ),
        "糖尿病外来_検査推移": pd.DataFrame(
            [
                {"検査日": "2025-07-15", "HbA1c": 8.2, "血糖": 186, "eGFR": 64, "UACR": 32, "LDL": 132},
                {"検査日": "2025-10-14", "HbA1c": 7.8, "血糖": 164, "eGFR": 62, "UACR": 38, "LDL": 126},
                {"検査日": "2026-01-16", "HbA1c": 7.5, "血糖": 152, "eGFR": 60, "UACR": 43, "LDL": 121},
                {"検査日": "2026-04-18", "HbA1c": 7.4, "血糖": 148, "eGFR": 58, "UACR": 46, "LDL": 118},
            ]
        ),
        "糖尿病外来_バイタル推移": pd.DataFrame(
            [
                {"測定日": "2025-07-15", "収縮期血圧": 146, "拡張期血圧": 86, "体重": 78.4, "BMI": 28.4},
                {"測定日": "2025-10-14", "収縮期血圧": 142, "拡張期血圧": 84, "体重": 77.6, "BMI": 28.1},
                {"測定日": "2026-01-16", "収縮期血圧": 136, "拡張期血圧": 80, "体重": 76.8, "BMI": 27.8},
                {"測定日": "2026-04-18", "収縮期血圧": 138, "拡張期血圧": 82, "体重": 76.9, "BMI": 27.8},
            ]
        ),
        "糖尿病外来_治療": pd.DataFrame(
            [
                {"カテゴリ": "血糖", "薬剤名": "メトホルミン", "用量": "500mg 2錠 分2", "継続状況": "継続"},
                {"カテゴリ": "血糖", "薬剤名": "エンパグリフロジン", "用量": "10mg 1錠 朝", "継続状況": "継続"},
                {"カテゴリ": "血糖", "薬剤名": "シタグリプチン", "用量": "50mg 1錠 朝", "継続状況": "継続"},
                {"カテゴリ": "血圧/腎保護", "薬剤名": "テルミサルタン", "用量": "40mg 1錠 朝", "継続状況": "継続"},
                {"カテゴリ": "脂質", "薬剤名": "ロスバスタチン", "用量": "2.5mg 1錠 夕", "継続状況": "継続"},
            ]
        ),
        "糖尿病外来_生活": pd.DataFrame(
            [
                {"項目": "服薬遵守", "達成率": 90},
                {"項目": "食事記録", "達成率": 65},
                {"項目": "運動 150分/週", "達成率": 55},
                {"項目": "家庭血圧記録", "達成率": 70},
                {"項目": "足のセルフチェック", "達成率": 80},
            ]
        ),
        "糖尿病外来_診察メモ": pd.DataFrame(
            [
                {"種別": "確認", "内容": "食後高血糖、夜間低血糖、飲み忘れ、尿路感染症状を確認"},
                {"種別": "合併症", "内容": "UACR軽度上昇、eGFR軽度低下。眼科予約と足チェックを確認"},
                {"種別": "方針", "内容": "体重と腎機能を見ながらSGLT2阻害薬継続。HbA1c目標は個別化して再確認"},
            ]
        ),
    }
    for table_name, dataframe in sample_tables.items():
        dataframe.to_sql(table_name, connection, if_exists="replace", index=False)
    return len(sample_tables)


def _validate_read_sql(sql: str) -> None:
    stripped = sql.strip()
    if not stripped:
        raise ValueError("SQLが空です。")
    if ";" in stripped.rstrip(";"):
        raise ValueError("SQLは単一のSELECT文だけを指定してください。")
    first_token = stripped.lstrip(" \n\t(").split(None, 1)[0].lower()
    if first_token != "select":
        raise ValueError("SQLはSELECT文だけを指定してください。")


def _escape_identifier(identifier: str) -> str:
    return identifier.replace('"', '""')
