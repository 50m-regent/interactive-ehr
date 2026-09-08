"""Post-hoc diagnostic: test whether a simple time-filter check explains the pilot.

This analysis was designed after inspecting the 20 model outputs. It does not
replace the frozen evaluation or establish a general SQL validator.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import sqlglot
from sqlglot import exp

from interactive_ehr.evaluation.generated_update_pilot import (
    END,
    Case,
    Interface,
    save_json,
    sha256,
)


def conjuncts(expression: exp.Expression) -> list[exp.Expression]:
    """Collect required top-level conjuncts without treating OR branches as mandatory."""
    if isinstance(expression, exp.Paren):
        return conjuncts(expression.this)
    if isinstance(expression, exp.And):
        return conjuncts(expression.this) + conjuncts(expression.expression)
    return [expression]


def has_literal_time_bounds(sql: str, days: int) -> bool:
    """Recognize the literal inclusive time bounds used in this constrained pilot."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return False
    if not isinstance(tree, exp.Select) or not isinstance(
        tree.args.get("where"), exp.Where
    ):
        return False
    start = (datetime.fromisoformat(END) - timedelta(days=days)).isoformat(sep=" ")
    found: set[tuple[str, str]] = set()
    for term in conjuncts(tree.args["where"].this):
        if (
            isinstance(term, (exp.GTE, exp.LTE))
            and isinstance(term.this, exp.Column)
            and term.this.name == "observed_at"
            and isinstance(term.expression, exp.Literal)
        ):
            found.add((type(term).__name__, term.expression.this))
    return ("GTE", start) in found and ("LTE", END) in found


def main() -> None:
    """Save this post-hoc comparison separately from the frozen run results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output / "posthoc_time_filter_check.json"
    if destination.exists():
        raise FileExistsError(destination)
    cases = {
        item["id"]: Case.model_validate(item)
        for item in json.loads((args.inputs / "cases.json").read_text())
    }
    records = []
    for line in (args.output / "candidate_results.jsonl").read_text().splitlines():
        record = json.loads(line)
        case = cases[record["id"]]
        artifact = Interface.model_validate_json(
            (args.output / f"{case.id}.txt").read_text()
        )
        queries = {query.id: query.sql for query in artifact.queries}
        accepted = (
            record["accepted"]["structure"]
            and "main_data" in queries
            and "stable_data" in queries
            and has_literal_time_bounds(queries["main_data"], case.target.days)
            and has_literal_time_bounds(queries["stable_data"], 1)
        )
        records.append(
            {
                "id": case.id,
                "accepted": accepted,
                "audit_valid": record["audit_valid"],
                "matches_three_state_decision": accepted
                == record["accepted"]["three_states"],
            }
        )
    save_json(
        destination,
        {
            "status": "post_hoc_after_inspecting_outputs",
            "n": len(records),
            "accepted": sum(record["accepted"] for record in records),
            "invalid_accepted": sum(
                record["accepted"] and not record["audit_valid"] for record in records
            ),
            "valid_rejected": sum(
                not record["accepted"] and record["audit_valid"] for record in records
            ),
            "same_decisions_as_three_states": sum(
                record["matches_three_state_decision"] for record in records
            ),
            "records": records,
            "source_sha256": sha256(Path(__file__)),
        },
    )


if __name__ == "__main__":
    main()
