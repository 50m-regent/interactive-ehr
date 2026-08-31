"""Audit whether matched synthetic cases are ready for a participant pilot."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from interactive_ehr.evaluation import (
    audit_case_manifest,
    load_clinical_task_graph,
    load_evaluation_case_manifest,
)


LOGGER = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="合成症例ペアがパイロット実験に利用可能か監査します。"
    )
    parser.add_argument("manifest", type=Path, help="合成症例マニフェストJSON")
    parser.add_argument("clinical_tasks", type=Path, help="臨床タスクモデルJSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the readiness audit and log its JSON result."""

    args = parse_args(argv)
    manifest = load_evaluation_case_manifest(args.manifest)
    clinical_tasks = load_clinical_task_graph(args.clinical_tasks)
    audit = audit_case_manifest(manifest, clinical_tasks)
    LOGGER.info("%s", audit.model_dump_json(indent=2))
    return 0 if audit.ready_for_pilot else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
