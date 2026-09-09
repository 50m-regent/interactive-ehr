"""Checks of the limited post-hoc comparator and rendered-data verification."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from interactive_ehr.evaluation.generated_update_pilot import (
    Target,
    create_database,
    make_rows,
    reference_interface,
    reference_sql,
)


def load_script(name: str) -> ModuleType:
    """Load a local diagnostic script without running its command-line entry."""
    spec = importlib.util.spec_from_file_location(name, f"scripts/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_time_filter_checker_rejects_missing_upper_and_or_escape() -> None:
    """Do not confuse optional OR predicates with required temporal restrictions."""
    module = load_script("check_generated_update_time_filters")
    sql = reference_sql(Target())
    assert module.has_literal_time_bounds(sql, 1)
    assert not module.has_literal_time_bounds(
        sql.replace(" AND observed_at <= '2026-09-08 12:00:00'", ""), 1
    )
    assert not module.has_literal_time_bounds(
        sql.replace(" ORDER BY", " OR 1=1 ORDER BY"), 1
    )


def test_time_filter_checker_does_not_validate_patient() -> None:
    """Expose the comparator's deliberately limited coverage as a regression test."""
    module = load_script("check_generated_update_time_filters")
    assert module.has_literal_time_bounds(reference_sql(Target(patient="SYN_B")), 1)


def test_saved_render_comparison_checks_table_and_chart(tmp_path: Path) -> None:
    """Inspect the production renderer's datasets through the verification script."""
    module = load_script("verify_generated_update_pilot")
    database = tmp_path / "synthetic.sqlite"
    create_database(make_rows(0), database)
    for kind in ("dataframe", "line_chart"):
        result = module.inspect_render(
            reference_interface(Target(kind=kind)).model_dump_json(), database
        )
        assert result["matched"]
        assert result["table_count"] + result["chart_count"] == 2
