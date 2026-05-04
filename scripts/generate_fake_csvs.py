"""Generate reproducible fake CSV files for all DWH models."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

from interactive_ehr.models import DwhBaseModel
from interactive_ehr.models.registry import (
    DEFAULT_DWH_CSV_DIR,
    DEFAULT_FAKE_ROWS,
    get_dwh_model,
    list_dwh_model_names,
)


def generate_fake_csvs(
    *,
    output_dir: Path = DEFAULT_DWH_CSV_DIR,
    n: int = DEFAULT_FAKE_ROWS,
    overwrite: bool = False,
) -> tuple[int, int]:
    """Generate fake DWH CSV files and return ``(created, skipped)`` counts."""

    random.seed(0)
    output_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    for model_name in list_dwh_model_names():
        csv_path = output_dir / f"{model_name}.csv"
        if csv_path.exists() and not overwrite:
            skipped += 1
            continue

        model = get_dwh_model(model_name)
        rows = model.fake(n=n)
        if isinstance(rows, DwhBaseModel):
            rows = [rows]
        dataframe = pd.DataFrame(
            [row.model_dump(mode="python", by_alias=True) for row in rows],
        )
        dataframe.to_csv(csv_path, index=False, encoding="utf-8-sig")
        created += 1

    return created, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate fake CSV files under data/dwh for all DWH models.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DWH_CSV_DIR,
        help="Output directory for generated CSV files.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_FAKE_ROWS,
        help="Number of fake rows per CSV.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing CSV files.",
    )
    args = parser.parse_args()

    created, skipped = generate_fake_csvs(
        output_dir=args.output_dir,
        n=args.rows,
        overwrite=args.overwrite,
    )
    print(f"created={created} skipped={skipped} output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
