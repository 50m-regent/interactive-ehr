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
            loaded += _load_chronic_disease_sample_tables(connection)
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


def _load_chronic_disease_sample_tables(connection: sqlite3.Connection) -> int:
    """Load stable synthetic tables for the default chronic disease scenario."""

    sample_tables = {
        "慢性疾患外来_患者サマリ": pd.DataFrame(
            [
                {
                    "患者表示名": "80代男性 Aさん",
                    "年齢": 78,
                    "性別": "男性",
                    "主要疾患": "高血圧、2型糖尿病、CKD G3aA2、脂質異常症",
                    "収縮期血圧": 148,
                    "拡張期血圧": 84,
                    "家庭血圧": "朝平均 142/80 mmHg",
                    "eGFR": 45,
                    "UACR": 96,
                    "K": 4.9,
                    "HbA1c": 7.2,
                    "LDL": 108,
                    "BMI": 25.9,
                    "本日の論点": "血圧は目標未達でUACRが増加。K 4.9のためARB増量は慎重に検討。",
                    "次回ToDo": "家庭血圧を朝晩2週間記録、尿蛋白再検、立ちくらみと飲み忘れを確認",
                }
            ]
        ),
        "慢性疾患外来_検査推移": pd.DataFrame(
            [
                {"検査日": "2025-07-22", "HbA1c": 7.6, "eGFR": 53, "UACR": 58, "K": 4.5, "LDL": 122},
                {"検査日": "2025-10-21", "HbA1c": 7.4, "eGFR": 50, "UACR": 72, "K": 4.6, "LDL": 116},
                {"検査日": "2026-01-20", "HbA1c": 7.3, "eGFR": 48, "UACR": 88, "K": 4.8, "LDL": 111},
                {"検査日": "2026-04-21", "HbA1c": 7.2, "eGFR": 45, "UACR": 96, "K": 4.9, "LDL": 108},
            ]
        ),
        "慢性疾患外来_血圧推移": pd.DataFrame(
            [
                {"測定日": "2025-07-22", "外来収縮期": 154, "外来拡張期": 86, "家庭収縮期": 146},
                {"測定日": "2025-10-21", "外来収縮期": 150, "外来拡張期": 84, "家庭収縮期": 144},
                {"測定日": "2026-01-20", "外来収縮期": 146, "外来拡張期": 82, "家庭収縮期": 140},
                {"測定日": "2026-04-21", "外来収縮期": 148, "外来拡張期": 84, "家庭収縮期": 142},
            ]
        ),
        "慢性疾患外来_処方": pd.DataFrame(
            [
                {"カテゴリ": "降圧・腎保護", "薬剤名": "テルミサルタン", "用量": "40mg 朝", "注意点": "K上昇と腎機能を確認"},
                {"カテゴリ": "降圧・腎保護", "薬剤名": "アムロジピン", "用量": "5mg 夕", "注意点": "浮腫とふらつき確認"},
                {"カテゴリ": "糖尿病", "薬剤名": "エンパグリフロジン", "用量": "10mg 朝", "注意点": "脱水、尿路感染、eGFR確認"},
                {"カテゴリ": "糖尿病", "薬剤名": "シタグリプチン", "用量": "50mg 朝", "注意点": "低血糖症状確認"},
                {"カテゴリ": "脂質", "薬剤名": "ロスバスタチン", "用量": "2.5mg 夕", "注意点": "筋症状確認"},
            ]
        ),
        "慢性疾患外来_カルテ記載": pd.DataFrame(
            [
                {"種別": "副作用", "内容": "前回は立ちくらみなし。夜間頻尿が増え、SGLT2阻害薬との関連を確認予定。"},
                {"種別": "服薬", "内容": "朝薬は概ね内服。夕薬は週1回程度忘れるため一包化を相談。"},
                {"種別": "処方調整", "内容": "ARB増量はKとeGFRを再確認後。降圧不足ならCa拮抗薬増量も候補。"},
            ]
        ),
        "慢性疾患外来_生活指導": pd.DataFrame(
            [
                {"項目": "減塩 6g/日目標", "達成率": 55},
                {"項目": "家庭血圧記録", "達成率": 70},
                {"項目": "歩行 20分/日", "達成率": 45},
                {"項目": "夕薬の飲み忘れ対策", "達成率": 65},
                {"項目": "体重測定", "達成率": 60},
            ]
        ),
        "慢性疾患外来_患者向け資料": pd.DataFrame(
            [
                {
                    "資料要点": (
                        "腎臓を守るため、減塩、家庭血圧記録、脱水予防、薬の飲み忘れ対策を優先。"
                    )
                }
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
