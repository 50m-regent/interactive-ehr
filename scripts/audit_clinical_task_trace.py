"""Audit a clinical task reference against a runtime ScenarioGraph."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from interactive_ehr.evaluation import (
    audit_information_trace,
    load_clinical_task_graph,
)
from interactive_ehr.scenario_graph import parse_scenario_graph_json


LOGGER = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="診療タスクの必要情報をScenarioGraphのノードと照合します。"
    )
    parser.add_argument("reference", type=Path, help="臨床タスクモデルJSON")
    parser.add_argument("scenario", type=Path, help="ScenarioGraph JSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the trace audit and log its JSON result."""

    args = parse_args(argv)
    reference = load_clinical_task_graph(args.reference)
    scenario = parse_scenario_graph_json(args.scenario.read_text(encoding="utf-8"))
    audit = audit_information_trace(
        reference,
        known_data_node_ids={node.id for node in scenario.data_nodes},
        known_widget_ids={node.id for node in scenario.widget_nodes},
    )
    LOGGER.info("%s", audit.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
