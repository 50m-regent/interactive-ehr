"""保存済みのTraceBench-EHR正式評価をTSVへ変換する。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from interactive_ehr.evaluation.tracebench_tsv import export_tracebench_tsv

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を読む。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    """元成果物を検証し、TSVと出力マニフェストを書く。"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    output_dir = args.output_dir or args.run_dir / "tsv"
    try:
        manifest = export_tracebench_tsv(args.run_dir, output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        LOGGER.error("TSV export failed: %s", error)
        return 1
    row_counts = manifest["row_counts"]
    LOGGER.info("wrote TSV files to %s: %s", output_dir, row_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
