"""Independently recount frozen sequential results and inspect actual renderer data."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from streamlit.dataframe_util import convert_arrow_bytes_to_pandas_df
from streamlit.testing.v1 import AppTest

from interactive_ehr.evaluation.generated_update_pilot import save_json, sha256
from interactive_ehr.evaluation.sequential_update_pilot import unpack_context
from interactive_ehr.scenario_graph import ScenarioGraph

LOGGER = logging.getLogger(__name__)


def graph_app(graph_json: str, context_json: str) -> None:
    """Render the recorded whole graph without rebuilding or repairing its context."""
    import json
    from interactive_ehr.scenario_graph import ScenarioGraph, render_scenario_graph
    from interactive_ehr.evaluation.sequential_update_pilot import unpack_context

    render_scenario_graph(
        ScenarioGraph.model_validate_json(graph_json),
        unpack_context(json.loads(context_json)),
    )


def widget_app(widget_json: str, context_json: str) -> None:
    """Render one recorded widget for direct access to its Streamlit data element."""
    import json
    from interactive_ehr.scenario_graph import WidgetNode
    from interactive_ehr.widgets.renderer import render_widget
    from interactive_ehr.evaluation.sequential_update_pilot import unpack_context

    render_widget(
        WidgetNode.model_validate_json(widget_json).widget,
        unpack_context(json.loads(context_json)),
    )


def inspect_render(event: dict[str, Any]) -> dict[str, Any]:
    """Check whole-graph exceptions and each table/chart against the actual cached data."""
    graph = ScenarioGraph.model_validate(event["graph"])
    context = unpack_context(event["context"])
    context_json = json.dumps(event["context"], ensure_ascii=False)
    at = AppTest.from_function(
        graph_app, args=(graph.model_dump_json(), context_json)
    ).run(timeout=20)
    result: dict[str, Any] = {
        "exceptions": [str(item.message) for item in at.exception],
        "warnings": [str(item.value) for item in at.warning],
        "widgets": [],
    }
    for node in graph.widget_nodes:
        spec = node.widget.model_dump(mode="json")
        single = AppTest.from_function(
            widget_app, args=(node.model_dump_json(), context_json)
        ).run(timeout=20)
        record: dict[str, Any] = {
            "id": node.id,
            "kind": spec["widget_type"],
            "exceptions": len(single.exception),
            "warnings": len(single.warning),
            "matched": False,
        }
        value = context.get(spec.get("data_key"))
        try:
            if single.exception or single.warning:
                raise ValueError("renderer emitted an exception or warning")
            if not isinstance(value, pd.DataFrame):
                raise ValueError("expected a dataframe-backed widget")
            if spec["widget_type"] == "dataframe":
                assert len(single.dataframe) == 1
                pd.testing.assert_frame_equal(
                    single.dataframe[0].value, value, check_dtype=False
                )
                assert list(single.dataframe[0].proto.column_order) == (
                    spec.get("column_order") or []
                )
            elif spec["widget_type"] == "line_chart":
                charts = single.get("vega_lite_chart")
                assert len(charts) == 1
                chart = charts[0]
                actual = convert_arrow_bytes_to_pandas_df(
                    chart.proto.datasets[0].data.data
                )
                expected = value.copy()
                x = spec.get("x")
                y = spec.get("y")
                if not isinstance(x, str) or not isinstance(y, (str, list)):
                    raise ValueError("unsupported axes for independent comparison")
                expected[x] = pd.to_datetime(expected[x])
                expected = expected.melt(
                    id_vars=[x],
                    value_vars=[y] if isinstance(y, str) else y,
                    var_name="系列",
                    value_name="値",
                )
                pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
                chart_spec = json.loads(chart.proto.spec)
                assert all(
                    layer["encoding"]["x"]["field"] == x
                    for layer in chart_spec["layer"]
                )
                assert all(
                    layer["encoding"]["y"]["field"] == "値"
                    for layer in chart_spec["layer"]
                )
            else:
                raise ValueError(
                    "no independent display-data checker for this widget kind"
                )
            record["matched"] = True
            record["rows"] = len(value)
            record["columns"] = list(value.columns)
        except (AssertionError, ValueError, KeyError, IndexError, TypeError) as exc:
            record["mismatch_type"] = type(exc).__name__
            record["detail"] = str(exc)
        result["widgets"].append(record)
    result["all_data_match"] = (
        not result["exceptions"]
        and not result["warnings"]
        and all(item["matched"] for item in result["widgets"])
    )
    return result


def verify(inputs: Path, output: Path, replay: Path) -> dict[str, Any]:
    """Verify provenance, independent counts, chain continuity and renderer outputs."""
    destination = output / "verification.json"
    if destination.exists():
        raise FileExistsError(destination)
    manifest = json.loads((output / "run_manifest.json").read_text())
    for name, checksum in manifest["source_sha256"].items():
        assert sha256(Path(name)) == checksum, name
    for name, checksum in manifest["outputs_sha256"].items():
        assert sha256(output / name) == checksum, name
    for name, checksum in json.loads(
        (inputs / "input_manifest.json").read_text()
    ).items():
        assert sha256(inputs / name) == checksum, name
    assert sha256(inputs / "input_manifest.json") == manifest["input_manifest_sha256"]
    replay_manifest = json.loads((replay / "run_manifest.json").read_text())
    assert replay_manifest["all_events_match"]
    assert replay_manifest["mode"] == "replay"
    rows = [
        json.loads(line)
        for line in (output / "candidate_results.jsonl").read_text().splitlines()
    ]
    summary = json.loads((output / "summary.json").read_text())
    assert len(rows) == len({row["id"] for row in rows}) == summary["n"]
    assert len(rows) + len(summary["unattempted"]) == summary["planned_steps"] == 18
    counts: Counter[str] = Counter()
    renderings = []
    preceding: dict[str, Any] = {}
    for row in rows:
        counts["audit_valid" if row["audit_valid"] else "audit_invalid"] += 1
        counts["pipeline_completed"] += int(row["pipeline_completed"])
        for condition, accepted in row["accepted"].items():
            counts[f"{condition}:accepted"] += int(accepted)
            counts[f"{condition}:invalid_accepted"] += int(
                accepted and not row["audit_valid"]
            )
            counts[f"{condition}:valid_rejected"] += int(
                not accepted and row["audit_valid"]
            )
        events = json.loads((output / f"{row['id']}.events.json").read_text())
        if row["index"] > 1:
            prior = preceding[row["sequence"]]
            assert events["before"] == {
                "graph": prior["graph"],
                "context": prior["context"],
            }
        final = events["events"][-1]
        preceding[row["sequence"]] = final
        assert events == json.loads((replay / f"{row['id']}.events.json").read_text())
        renderings.append({"id": row["id"], **inspect_render(final)})
    for key in ("audit_valid", "audit_invalid", "pipeline_completed"):
        assert counts[key] == summary[key]
    for condition, values in summary["conditions"].items():
        for key, value in values.items():
            assert counts[f"{condition}:{key}"] == value
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "hashes_match": True,
        "independent_recount": dict(counts),
        "all_events_replayed": True,
        "sequence_state_continuity": True,
        "renderings": renderings,
        "all_rendered_data_match": all(item["all_data_match"] for item in renderings),
        "summary_sha256": sha256(output / "summary.json"),
        "candidate_results_sha256": sha256(output / "candidate_results.jsonl"),
        "verifier_sha256": sha256(Path(__file__)),
    }
    save_json(destination, result)
    return result


def main() -> None:
    """Validate one saved experiment without a model connection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replay", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = verify(args.inputs, args.output, args.replay)
    LOGGER.info(
        "Verified %s records; rendered data match=%s",
        result["records"],
        result["all_rendered_data_match"],
    )


if __name__ == "__main__":
    main()
