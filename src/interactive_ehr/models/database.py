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
