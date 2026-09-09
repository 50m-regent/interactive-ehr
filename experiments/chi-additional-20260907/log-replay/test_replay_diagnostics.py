"""再集計が参照条件を取り違えたり、不正な入力を受理しないことを確認する。"""

import json
from pathlib import Path

import pytest

from replay_diagnostics import checksum, replay_conditions, run_analysis, verify_run


def test_query_ablation_keeps_annotation_failure() -> None:
    """SQLの完全一致を外しても独立に記録された注釈違反は残す。"""
    graph = frozenset({"target_query_mismatch", "semantic_patient_mismatch"})
    result = replay_conditions(graph, frozenset())
    assert result["without_query_equality"] == {"semantic_patient_mismatch"}
    assert result["without_annotations"] == {"target_query_mismatch"}
    assert not result["without_query_and_annotations"]


def test_reduced_condition_preserves_binding_check() -> None:
    """SQLが変わらない誤接続も、接続先を含む条件では拒否する。"""
    graph = frozenset({"target_widget_connection_mismatch"})
    result = replay_conditions(graph, frozenset())
    assert not result["artifact_and_query"]
    assert result["artifact_query_binding"] == graph


def test_artifact_issue_is_not_removed_with_query_equality() -> None:
    """SQLと結果の版ずれは、目標SQLの照合とは別の検査として残す。"""
    artifact = frozenset({"query_result_mismatch"})
    result = replay_conditions(artifact, artifact)
    assert not result["query_only"]
    assert result["without_query_equality"] == artifact


def test_inconsistent_log_stops_replay() -> None:
    """含まれるはずの下位検査が欠落した記録では再構成を中止する。"""
    with pytest.raises(ValueError, match="not contained"):
        replay_conditions(frozenset(), frozenset({"query_result_mismatch"}))


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    """既存の結果ディレクトリを入力検査より先に拒否する。"""
    output = tmp_path / "results"
    output.mkdir()
    sentinel = output / "original.txt"
    sentinel.write_text("original")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_analysis(tmp_path / "missing", output)
    assert sentinel.read_text() == "original"


def test_changed_source_fails_checksum_verification(tmp_path: Path) -> None:
    """記録後に元データが変わっていれば再集計を許可しない。"""
    implementation = tmp_path / "tracebench_ehr.py"
    implementation.write_text("frozen")
    source = tmp_path / "candidate_results.jsonl"
    source.write_text("original")
    manifest = {
        "output_checksums": {source.name: checksum(source)},
        "implementation_checksums": {implementation.name: checksum(implementation)},
    }
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest))
    source.write_text("changed")
    with pytest.raises(ValueError, match="source checksum mismatch"):
        verify_run(tmp_path, implementation)
