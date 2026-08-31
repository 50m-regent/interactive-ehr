"""EHRSQL-2024の50件実行可能性確認を実行するCLI。"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from interactive_ehr.evaluation.ehrsql_feasibility import (
    DEFAULT_MAX_RESULT_ROWS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    DEFAULT_SAMPLE_SEED,
    DEFAULT_SAMPLE_SIZE,
    load_ehrsql_cases,
    read_dataset_version,
    run_ehrsql_feasibility,
    select_ehrsql_cases,
    summarize_feasibility,
    write_feasibility_outputs,
)

LOGGER = logging.getLogger(__name__)
DATASET_REPOSITORY = "https://github.com/glee4810/ehrsql-2024"


def parse_args() -> argparse.Namespace:
    """CLI引数を解析する。"""

    parser = argparse.ArgumentParser(
        description="Run the TraceBench-EHR EHRSQL feasibility check."
    )
    parser.add_argument("--annotated-data", type=Path, required=True)
    parser.add_argument("--dataset-data", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--dataset-commit", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SAMPLE_SEED)
    parser.add_argument(
        "--query-timeout-seconds",
        type=float,
        default=DEFAULT_QUERY_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-result-rows",
        type=int,
        default=DEFAULT_MAX_RESULT_ROWS,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/evaluation/ehrsql_feasibility_v0.1"),
    )
    return parser.parse_args()


def main() -> int:
    """選定、読み取り専用実行、グラフ検証、成果物保存を行う。"""

    args = parse_args()
    cases = load_ehrsql_cases(args.annotated_data, split=args.split)
    selected_cases = select_ehrsql_cases(
        cases,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    LOGGER.info(
        "selected %d answerable cases from %d cases",
        len(selected_cases),
        len(cases),
    )
    results = run_ehrsql_feasibility(
        selected_cases,
        database_path=args.database,
        query_timeout_seconds=args.query_timeout_seconds,
        max_result_rows=args.max_result_rows,
    )
    summary = summarize_feasibility(selected_cases, results)
    implementation_paths = [
        Path(__file__),
        Path(__file__).parents[1]
        / "src/interactive_ehr/evaluation/ehrsql_feasibility.py",
    ]
    write_feasibility_outputs(
        output_dir=args.output_dir,
        cases=selected_cases,
        results=results,
        annotated_path=args.annotated_data,
        dataset_data_path=args.dataset_data,
        database_path=args.database,
        dataset_repository=DATASET_REPOSITORY,
        dataset_commit=args.dataset_commit,
        dataset_version=read_dataset_version(args.dataset_data),
        code_commit=args.code_commit,
        sample_seed=args.seed,
        query_timeout_seconds=args.query_timeout_seconds,
        max_result_rows=args.max_result_rows,
        implementation_paths=implementation_paths,
    )
    LOGGER.info(
        "execution=%d/%d non_empty=%d/%d graph=%d/%d output=%s",
        summary.execution_success_count,
        summary.selected_case_count,
        summary.non_empty_result_count,
        summary.selected_case_count,
        summary.graph_valid_count,
        summary.selected_case_count,
        args.output_dir,
    )
    return 0 if summary.execution_success_count == summary.selected_case_count else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
