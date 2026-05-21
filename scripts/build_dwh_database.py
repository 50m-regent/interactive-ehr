"""Build a local SQLite database from DWH CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

from interactive_ehr.models.database import (
    DEFAULT_DWH_DB_PATH,
    build_dwh_database_from_csvs,
)
from interactive_ehr.models.registry import DEFAULT_DWH_CSV_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load data/dwh CSV files into a local SQLite database.",
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=DEFAULT_DWH_CSV_DIR,
        help="Directory containing DWH CSV files.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DWH_DB_PATH,
        help="SQLite database path to create or update.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recreate the database and replace existing tables.",
    )
    args = parser.parse_args()

    loaded, skipped = build_dwh_database_from_csvs(
        csv_dir=args.csv_dir,
        db_path=args.db_path,
        overwrite=args.overwrite,
    )
    print(f"loaded={loaded} skipped={skipped} db_path={args.db_path}")


if __name__ == "__main__":
    main()
