"""Independently recount generated-pilot decisions and inspect real rendered data."""

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

from interactive_ehr.evaluation.generated_update_pilot import (
    Interface,
    execute,
    save_json,
    sha256,
)

LOGGER = logging.getLogger(__name__)


def render_app(raw: str, database: str) -> None:
    """Run the frozen renderer in Streamlit with only a synthetic artifact and database."""
    from pathlib import Path
    from interactive_ehr.evaluation.generated_update_pilot import (
        Interface,
        render_interface,
    )

    render_interface(Interface.model_validate_json(raw), Path(database))


def inspect_render(raw: str, database: Path) -> dict[str, Any]:
    """Compare Streamlit's actual table and chart datasets with executed SQL results."""
    artifact = Interface.model_validate_json(raw)
    at = AppTest.from_function(render_app, args=(raw, str(database))).run(timeout=15)
    result: dict[str, Any] = {
        "exceptions": len(at.exception),
        "warnings": len(at.warning),
        "table_count": len(at.dataframe),
        "chart_count": len(at.get("vega_lite_chart")),
        "widgets": [],
    }
    if at.exception or at.warning:
        result["matched"] = False
        return result
    queries = {query.id: query.sql for query in artifact.queries}
    table_index, chart_index = 0, 0
    for widget in artifact.widgets:
        columns, rows = execute(queries[widget.data_key], database)
        frame = pd.DataFrame(rows, columns=columns)
        if widget.kind == "dataframe":
            element = at.dataframe[table_index]
            table_index += 1
            pd.testing.assert_frame_equal(element.value, frame, check_dtype=False)
            assert list(element.proto.column_order) == widget.columns
        else:
            element = at.get("vega_lite_chart")[chart_index]
            chart_index += 1
            spec = json.loads(element.proto.spec)
            chart_frame = convert_arrow_bytes_to_pandas_df(
                element.proto.datasets[0].data.data
            )
            assert widget.x is not None and widget.y is not None
            expected = frame.copy()
            expected[widget.x] = pd.to_datetime(expected[widget.x])
            expected = expected.melt(
                id_vars=[widget.x],
                value_vars=[widget.y],
                var_name="系列",
                value_name="値",
            )
            pd.testing.assert_frame_equal(chart_frame, expected, check_dtype=False)
            assert all(
                layer["encoding"]["x"]["field"] == widget.x for layer in spec["layer"]
            )
            assert all(
                layer["encoding"]["y"]["field"] == "値" for layer in spec["layer"]
            )
        result["widgets"].append(
            {
                "id": widget.id,
                "data_key": widget.data_key,
                "kind": widget.kind,
                "rows": len(rows),
                "columns": columns,
            }
        )
    result["matched"] = True
    return result


def verify(inputs: Path, output: Path) -> None:
    """Verify raw hashes, frozen implementation, counts and all parseable rendered outputs."""
    if (output / "verification.json").exists():
        raise FileExistsError("verification already exists")
    manifest = json.loads((output / "run_manifest.json").read_text())
    for name, checksum in manifest["source_sha256"].items():
        assert sha256(Path(name)) == checksum, name
    for name, checksum in manifest["outputs_sha256"].items():
        assert sha256(output / name) == checksum, name
    for name, checksum in json.loads(
        (inputs / "input_manifest.json").read_text()
    ).items():
        assert sha256(inputs / name) == checksum, name
    records = [
        json.loads(line)
        for line in (output / "candidate_results.jsonl").read_text().splitlines()
    ]
    summary = json.loads((output / "summary.json").read_text())
    assert len({record["id"] for record in records}) == len(records) == summary["n"]
    counts: Counter[str] = Counter()
    renders = []
    usage: Counter[str] = Counter()
    for record in records:
        case_id = record["id"]
        assert sha256(output / f"{case_id}.txt") == record["response_sha256"]
        counts["audit_valid" if record["audit_valid"] else "audit_invalid"] += 1
        for condition, accepted in record["accepted"].items():
            counts[f"{condition}:accepted"] += int(accepted)
            counts[f"{condition}:invalid_accepted"] += int(
                accepted and not record["audit_valid"]
            )
            counts[f"{condition}:valid_rejected"] += int(
                not accepted and record["audit_valid"]
            )
        metadata = json.loads((output / f"{case_id}.metadata.json").read_text())
        for key, value in (metadata.get("usage") or {}).items():
            if isinstance(value, int):
                usage[key] += value
        if record["parse_ok"]:
            render = inspect_render(
                (output / f"{case_id}.txt").read_text(), inputs / "state_0.sqlite"
            )
            renders.append({"id": case_id, **render})
    assert counts["audit_valid"] == summary["audit_valid"]
    assert counts["audit_invalid"] == summary["audit_invalid"]
    for condition, values in summary["conditions"].items():
        for key, value in values.items():
            assert counts[f"{condition}:{key}"] == value
    save_json(
        output / "verification.json",
        {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verified_records": len(records),
            "hashes_match": True,
            "independent_recount": dict(counts),
            "usage_totals": dict(usage),
            "render_checks": renders,
            "all_rendered_data_match": all(item["matched"] for item in renders),
            "verification_source_sha256": sha256(Path(__file__)),
        },
    )
    LOGGER.info(
        "Verified %s records and %s rendered interfaces", len(records), len(renders)
    )


def main() -> None:
    """Verify one saved run without calling an external model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(
        "streamlit.runtime.scriptrunner_utils.script_run_context"
    ).setLevel(logging.ERROR)
    verify(args.inputs, args.output)


if __name__ == "__main__":
    main()
