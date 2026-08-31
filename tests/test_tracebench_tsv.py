"""TraceBench-EHRのTSV出力テスト。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from interactive_ehr.evaluation.ehrsql_feasibility import sha256_file
from interactive_ehr.evaluation.tracebench_tsv import export_tracebench_tsv

FORMAL_RUN_DIR = Path("results/evaluation/tracebench_ehr_v1.1/test")


def test_export_formal_results_to_tsv(tmp_path: Path) -> None:
    """正式評価の件数と集計を照合して6種類のTSVを出力する。"""

    source_files = (
        "run_manifest.json",
        "build_summary.json",
        "summary.json",
        "pair_manifest.jsonl",
        "candidate_results.jsonl",
    )
    checksums_before = {
        filename: sha256_file(FORMAL_RUN_DIR / filename) for filename in source_files
    }

    output_dir = tmp_path / "tsv"
    manifest = export_tracebench_tsv(FORMAL_RUN_DIR, output_dir)

    assert manifest["row_counts"] == {
        "build_summary.tsv": 1,
        "condition_metrics.tsv": 4,
        "mutation_metrics.tsv": 32,
        "paired_differences.tsv": 6,
        "pair_manifest.tsv": 763,
        "candidate_results.tsv": 6104,
    }
    assert manifest["verification"] == {
        "source_checksums_match_run_manifest": True,
        "summary_matches_candidate_results": True,
        "paired_confidence_intervals_recomputed": True,
        "export_fields_are_allowlisted": True,
    }
    assert {
        filename: sha256_file(FORMAL_RUN_DIR / filename) for filename in source_files
    } == checksums_before

    candidate_rows = _read_tsv(output_dir / "candidate_results.tsv")
    assert len(candidate_rows) == 6104
    assert "question" not in candidate_rows[0]
    assert "sql" not in candidate_rows[0]
    assert "patient_id" not in candidate_rows[0]
    assert candidate_rows[0]["issue_codes"] == ""

    condition_rows = _read_tsv(output_dir / "condition_metrics.tsv")
    graph_row = next(
        row for row in condition_rows if row["condition"] == "graph_contract"
    )
    assert graph_row["unsafe_acceptance_rate"] == "0.0"
    assert graph_row["valid_acceptance_rate"] == "1.0"
    assert graph_row["localization_accuracy"] == "1.0"
    assert graph_row["repair_success_rate"] == "1.0"

    saved_manifest = json.loads(
        (output_dir / "export_manifest.json").read_text(encoding="utf-8")
    )
    assert saved_manifest == manifest


def _read_tsv(path: Path) -> list[dict[str, str]]:
    """テスト対象のTSVを辞書の一覧として読む。"""

    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))
