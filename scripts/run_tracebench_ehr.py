"""TraceBench-EHRのvalidationパイロットまたはtest正式評価を実行する。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import cast

from interactive_ehr.evaluation.tracebench_analysis import (
    analyze_tracebench_run,
    write_tracebench_outputs,
)
from interactive_ehr.evaluation.tracebench_ehr import (
    TraceSplit,
    build_tracebench_run,
    load_trace_cases,
    load_tracebench_config,
    validate_pilot_gate,
    verify_tracebench_inputs,
)

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を読む。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=[item.value for item in TraceSplit], required=True
    )
    parser.add_argument("--annotated-data", type=Path, required=True)
    parser.add_argument("--dataset-data", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("data/evaluation/tracebench_ehr.v1.json"),
    )
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def read_dataset_version(path: Path) -> str:
    """EHRSQL data.jsonから分割固有の版を読む。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise ValueError("dataset data does not contain a version")
    return cast(str, payload["version"])


def main() -> int:
    """入力検証、候補生成、評価、統計集計、保存を順に実行する。"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    split = TraceSplit(args.split)
    config = load_tracebench_config(args.config)
    verify_tracebench_inputs(
        config,
        split=split,
        annotated_path=args.annotated_data,
        dataset_data_path=args.dataset_data,
        database_path=args.database,
    )
    cases = load_trace_cases(args.annotated_data, split=split)
    LOGGER.info("loaded %d cases for %s", len(cases), split.value)
    run = build_tracebench_run(
        cases,
        split=split,
        database_path=args.database,
        config=config,
    )
    summary = analyze_tracebench_run(run, config)
    implementation_paths = (
        Path("src/interactive_ehr/evaluation/tracebench_ehr.py"),
        Path("src/interactive_ehr/evaluation/tracebench_analysis.py"),
        Path("scripts/run_tracebench_ehr.py"),
    )
    write_tracebench_outputs(
        output_dir=args.output_dir,
        run=run,
        summary=summary,
        config=config,
        config_path=args.config,
        annotated_path=args.annotated_data,
        dataset_data_path=args.dataset_data,
        database_path=args.database,
        dataset_version=read_dataset_version(args.dataset_data),
        code_commit=args.code_commit,
        implementation_paths=implementation_paths,
    )
    LOGGER.info(
        "completed %d pairs and %d candidate runs",
        run.build_summary.pair_count,
        len(run.candidate_records),
    )
    if split is TraceSplit.VALIDATION:
        failures = validate_pilot_gate(run, config)
        if failures:
            for failure in failures:
                LOGGER.error("pilot gate: %s", failure)
            return 1
        LOGGER.info("validation pilot gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
