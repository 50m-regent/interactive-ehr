"""Check independent rendering verification without changing frozen pilot code."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd

from interactive_ehr.evaluation.generated_update_pilot import execute
from interactive_ehr.evaluation.sequential_update_pilot import (
    initial_graph,
    pack_context,
    prepare,
)
from interactive_ehr.widgets.chart import LineChartSpec
from interactive_ehr.llm.schema_utils import to_gemini_response_json_schema
from interactive_ehr.scenario_graph import WidgetNodeSqlGeneration


def verifier_module() -> ModuleType:
    """Import only the local verification entry point."""
    spec = importlib.util.spec_from_file_location(
        "sequential_verifier",
        Path(__file__).parents[1] / "scripts/verify_sequential_update_pilot.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_table_chart_data_and_visible_warning(tmp_path: Path) -> None:
    """Verify rendered data and retain warnings caused by a missing display column."""
    module = verifier_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    graph = initial_graph().model_dump(mode="json")
    context = {}
    for node in initial_graph().data_nodes:
        columns, rows = execute(node.sql or "", inputs / "state_0.sqlite")
        context[node.context_key] = pd.DataFrame(rows, columns=columns)
    event = {"graph": graph, "context": pack_context(context)}
    assert module.inspect_render(event)["all_data_match"]
    graph["tasks"][0]["widgets"][0]["widget"] = LineChartSpec(
        data_key="main_data", x="observed_at", y="value"
    ).model_dump(mode="json")
    result = module.inspect_render(event)
    assert result["all_data_match"], result
    graph["tasks"][0]["widgets"][1]["widget"]["column_order"] = ["missing_column"]
    result = module.inspect_render(event)
    assert not result["all_data_match"]
    assert result["warnings"]


def test_diagnosis_distinguishes_sdk_schema_and_application_validation(
    tmp_path: Path,
) -> None:
    """Reproduce the schema gap with a controlled fixture, then check a valid response."""
    spec = importlib.util.spec_from_file_location(
        "sequential_diagnosis",
        Path(__file__).parents[1] / "scripts/diagnose_sequential_update_failures.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = {
        "contents": '生成する node_plan:\n{"widget_type":"dataframe"}\n\nユーザー要望:\n集約',
        "config": {
            "response_json_schema": to_gemini_response_json_schema(
                WidgetNodeSqlGeneration.model_json_schema()
            )
        },
    }
    (tmp_path / "call_001.request.json").write_text(json.dumps(request))
    (tmp_path / "call_001.metadata.json").write_text(json.dumps({"step": "sample"}))
    (tmp_path / "sample.events.json").write_text(
        json.dumps(
            {
                "before": {"graph": {}, "context": {}},
                "events": [{"graph": {}, "context": {}}],
            }
        )
    )
    response = {
        "widget_node": {"id": "main", "widget": {"widget_type": "markdown"}},
        "sql": "SELECT 1",
    }
    (tmp_path / "call_001.response.txt").write_text(json.dumps(response))
    result = module.diagnose(tmp_path)
    assert result["schema_application_mismatches"] == 1
    assert result["records"][0]["json_schema_errors"] == []
    response["widget_node"] = initial_graph().widget_nodes[0].model_dump(mode="json")
    (tmp_path / "call_001.response.txt").write_text(json.dumps(response))
    assert module.diagnose(tmp_path)["schema_application_mismatches"] == 0
