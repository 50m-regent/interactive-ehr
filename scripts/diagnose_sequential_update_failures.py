"""Post-hoc diagnosis of schema mismatches in the recorded sequential pilot."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from interactive_ehr.evaluation.generated_update_pilot import save_json, sha256
from interactive_ehr.scenario_graph import WidgetNodeSqlGeneration


def diagnose(output: Path) -> dict[str, Any]:
    """Compare every widget response with its actual SDK schema and application model."""
    records = []
    for request_path in sorted(output.glob("call_*.request.json")):
        request = json.loads(request_path.read_text())
        schema = request["config"]["response_json_schema"]
        if schema.get("title") != "WidgetNodeSqlGeneration":
            continue
        name = request_path.name.replace(".request.json", "")
        response_path = output / f"{name}.response.txt"
        raw = json.loads(response_path.read_text())
        errors = list(Draft202012Validator(schema).iter_errors(raw))
        application_errors = []
        try:
            WidgetNodeSqlGeneration.model_validate(raw)
        except ValidationError as exc:
            application_errors = [
                {
                    "location": list(item["loc"]),
                    "type": item["type"],
                    "message": item["msg"],
                }
                for item in exc.errors()
            ]
        plan_text = (
            request["contents"]
            .split("生成する node_plan:\n", 1)[1]
            .split("\n\nユーザー要望:", 1)[0]
        )
        plan = json.loads(plan_text)
        metadata = json.loads((output / f"{name}.metadata.json").read_text())
        events = json.loads((output / f"{metadata['step']}.events.json").read_text())
        final = events["events"][-1]
        records.append(
            {
                "call": name,
                "step": metadata["step"],
                "json_schema_errors": [error.message for error in errors],
                "application_errors": application_errors,
                "schema_allows_application_invalid_output": not errors
                and bool(application_errors),
                "planned_widget_kind": plan["widget_type"],
                "generated_widget": raw["widget_node"]["widget"],
                "terminal_graph_unchanged": final["graph"] == events["before"]["graph"],
                "terminal_context_unchanged": final["context"]
                == events["before"]["context"],
                "response_sha256": sha256(response_path),
                "request_sha256": sha256(request_path),
            }
        )
    return {
        "status": "post_hoc_after_observing_pipeline_failures",
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "records": records,
        "widget_responses": len(records),
        "schema_application_mismatches": sum(
            record["schema_allows_application_invalid_output"] for record in records
        ),
        "source_sha256": sha256(Path(__file__)),
    }


def main() -> None:
    """Save the diagnosis separately, preserving frozen generation and scoring."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.output / "posthoc_schema_diagnosis.json"
    if path.exists():
        raise FileExistsError(path)
    save_json(path, diagnose(args.output))


if __name__ == "__main__":
    main()
