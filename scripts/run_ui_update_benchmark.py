"""Run the deterministic RQ1 UI update benchmark and write its artifacts."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from interactive_ehr.evaluation.benchmark_analysis import (
    analyze_benchmark_run,
    write_benchmark_artifacts,
)
from interactive_ehr.evaluation.update_benchmark import (
    load_update_benchmark,
    run_update_benchmark,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_BENCHMARK_PATH = Path("data/evaluation/ui_update_benchmark.v0.4.json")
DEFAULT_OUTPUT_DIR = Path("results/evaluation/ui_update_benchmark_v0.4")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse benchmark input and output paths."""

    parser = argparse.ArgumentParser(
        description="RQ1のUI更新ベンチマークを決定的に実行します。"
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=DEFAULT_BENCHMARK_PATH,
        help="ベンチマーク定義JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="評価結果の保存先",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Load, run, analyze, and persist the benchmark once per input."""

    args = parse_args(argv)
    benchmark = load_update_benchmark(args.benchmark)
    run = run_update_benchmark(benchmark)
    summary = analyze_benchmark_run(benchmark, run)
    manifest = write_benchmark_artifacts(
        benchmark,
        run,
        summary,
        args.output_dir,
    )
    LOGGER.info(
        "評価を完了しました: cases=%d, specs=%d, runs=%d, output=%s",
        summary.evaluation_case_count,
        summary.evaluation_candidate_spec_count,
        manifest.one_shot_run_count,
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
