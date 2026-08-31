"""Deterministic UI update benchmark tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from interactive_ehr.evaluation.benchmark_analysis import (
    BenchmarkSummary,
    analyze_benchmark_run,
    render_markdown_report,
    write_benchmark_artifacts,
)
from interactive_ehr.evaluation.update_benchmark import (
    BenchmarkDefinition,
    BenchmarkRun,
    BenchmarkSplit,
    ChangeKind,
    FaultKind,
    PatchAction,
    PatchOperation,
    UpdateMethod,
    UpdatePatch,
    apply_artifact_patch,
    apply_graph_patch,
    artifact_to_graph,
    build_candidate_specs,
    build_paired_candidate,
    canonical_checksum,
    compile_graph_artifact,
    evaluate_candidate,
    load_update_benchmark,
    run_update_benchmark,
)


BENCHMARK_PATH = Path("data/evaluation/ui_update_benchmark.v0.4.json")


@pytest.fixture(scope="module")
def benchmark() -> BenchmarkDefinition:
    """Load the frozen benchmark once for this test module."""

    return load_update_benchmark(BENCHMARK_PATH)


@pytest.fixture(scope="module")
def benchmark_run(benchmark: BenchmarkDefinition) -> BenchmarkRun:
    """Run all deterministic conditions once for shared assertions."""

    return run_update_benchmark(benchmark)


@pytest.fixture(scope="module")
def benchmark_summary(
    benchmark: BenchmarkDefinition,
    benchmark_run: BenchmarkRun,
) -> BenchmarkSummary:
    """Analyze the shared benchmark run."""

    return analyze_benchmark_run(benchmark, benchmark_run)


def test_benchmark_has_frozen_case_and_sequence_shape(
    benchmark: BenchmarkDefinition,
) -> None:
    """Keep the development and held-out evaluation sizes fixed."""

    development_cases = [
        case for case in benchmark.cases if case.split is BenchmarkSplit.DEVELOPMENT
    ]
    evaluation_cases = [
        case for case in benchmark.cases if case.split is BenchmarkSplit.EVALUATION
    ]
    assert len(development_cases) == 8
    assert len(evaluation_cases) == 24
    assert (
        len(
            [
                sequence
                for sequence in benchmark.sequences
                if sequence.split is BenchmarkSplit.DEVELOPMENT
            ]
        )
        == 2
    )
    assert (
        len(
            [
                sequence
                for sequence in benchmark.sequences
                if sequence.split is BenchmarkSplit.EVALUATION
            ]
        )
        == 6
    )
    for change_kind in ChangeKind:
        assert (
            sum(case.intent.change_kind is change_kind for case in evaluation_cases)
            == 4
        )
    assert {canonical_checksum(case.intent) for case in development_cases}.isdisjoint(
        canonical_checksum(case.intent) for case in evaluation_cases
    )


def test_candidate_specs_have_one_valid_three_single_and_one_compound(
    benchmark: BenchmarkDefinition,
) -> None:
    """Expand every evaluation case into the pre-registered five candidates."""

    evaluation_cases = [
        case for case in benchmark.cases if case.split is BenchmarkSplit.EVALUATION
    ]
    specifications = [
        specification
        for specification in build_candidate_specs(benchmark)
        if specification.case_id.startswith("eval-")
    ]

    assert len(specifications) == 120
    for case in evaluation_cases:
        matching = [spec for spec in specifications if spec.case_id == case.id]
        assert len(matching) == 5
        assert sum(spec.expected_valid for spec in matching) == 1
        assert sum(len(spec.faults) == 1 for spec in matching) == 3
        assert sum(len(spec.faults) == 2 for spec in matching) == 1
        assert all(len(spec.checksum) == 64 for spec in matching)
        assert all(spec.version == benchmark.version for spec in matching)


def test_paired_patches_compile_to_the_same_semantics(
    benchmark: BenchmarkDefinition,
) -> None:
    """Require direct and graph candidates to produce identical UI artifacts."""

    cases_by_id = {case.id: case for case in benchmark.cases}
    for specification in build_candidate_specs(benchmark):
        case = cases_by_id[specification.case_id]
        paired = build_paired_candidate(benchmark, case, specification)
        assert paired.version == benchmark.version
        assert paired.direct_patch.version == benchmark.version
        assert paired.graph_patch.version == benchmark.version
        direct_candidate = apply_artifact_patch(
            benchmark.baseline,
            paired.direct_patch,
        )
        graph_candidate = apply_graph_patch(
            artifact_to_graph(benchmark.baseline),
            paired.graph_patch,
        )
        assert direct_candidate == compile_graph_artifact(graph_candidate)


@pytest.mark.parametrize(
    ("fault", "ablation_method", "check_id"),
    [
        (
            FaultKind.OUT_OF_SCOPE_MUTATION,
            UpdateMethod.GRAPH_NO_SCOPE,
            "scope",
        ),
        (
            FaultKind.SAFETY_VIOLATION,
            UpdateMethod.GRAPH_NO_SAFETY,
            "safety",
        ),
        (
            FaultKind.TRACEABILITY_BREAK,
            UpdateMethod.GRAPH_NO_TRACEABILITY,
            "traceability",
        ),
    ],
)
def test_each_single_fault_is_caught_by_its_control(
    benchmark: BenchmarkDefinition,
    fault: FaultKind,
    ablation_method: UpdateMethod,
    check_id: str,
) -> None:
    """Show that removing one graph control exposes its matching single fault."""

    cases_by_id = {case.id: case for case in benchmark.cases}
    specification = next(
        spec for spec in build_candidate_specs(benchmark) if spec.faults == [fault]
    )
    case = cases_by_id[specification.case_id]
    paired = build_paired_candidate(benchmark, case, specification)

    direct_record = evaluate_candidate(
        benchmark,
        case,
        paired,
        UpdateMethod.DIRECT,
    )
    full_graph_record = evaluate_candidate(
        benchmark,
        case,
        paired,
        UpdateMethod.GRAPH_FULL,
    )
    ablation_record = evaluate_candidate(
        benchmark,
        case,
        paired,
        ablation_method,
    )

    assert direct_record.accepted is False
    assert full_graph_record.accepted is False
    assert any(
        result.check_id == check_id and not result.passed
        for result in full_graph_record.validation_results
    )
    assert ablation_record.accepted is True
    assert ablation_record.unsafe_acceptance is True


def test_execution_failure_is_rejected_by_every_method(
    benchmark: BenchmarkDefinition,
) -> None:
    """Retain the representation-independent SQL execution gate."""

    cases_by_id = {case.id: case for case in benchmark.cases}
    specification = next(
        spec
        for spec in build_candidate_specs(benchmark)
        if spec.faults == [FaultKind.EXECUTION_FAILURE]
    )
    case = cases_by_id[specification.case_id]
    paired = build_paired_candidate(benchmark, case, specification)

    for method in UpdateMethod:
        record = evaluate_candidate(benchmark, case, paired, method)
        assert record.accepted is False
        assert record.runtime_failure is True


def test_graph_provenance_is_recorded_outside_the_main_fault_model(
    benchmark: BenchmarkDefinition,
) -> None:
    """Keep graph-only provenance testable without biasing the paired faults."""

    graph = artifact_to_graph(benchmark.baseline)
    first_data_node = graph.data_nodes[0]
    missing_information_id = first_data_node.information_ids[0]
    patch = UpdatePatch(
        version=benchmark.version,
        candidate_id="graph-provenance-break",
        representation="graph",
        operations=[
            PatchOperation(
                entity="data_node",
                entity_id=first_data_node.id,
                field="information_ids",
                action=PatchAction.REMOVE,
                value=missing_information_id,
            )
        ],
    )
    candidate = apply_graph_patch(graph, patch)

    from interactive_ehr.evaluation.update_benchmark import (
        _validate_graph_provenance,
    )

    result = _validate_graph_provenance(candidate)
    assert result.passed is False
    assert missing_information_id in result.detail


def test_full_run_matches_oracle_and_registered_counts(
    benchmark_run: BenchmarkRun,
) -> None:
    """Keep common labels, paired representations, and run counts aligned."""

    assert len(benchmark_run.paired_candidates) == 160
    assert len(benchmark_run.candidate_records) == 800
    assert len(benchmark_run.sequence_records) == 120
    assert all(
        record.expected_valid == record.oracle_valid
        for record in benchmark_run.candidate_records
    )
    assert all(
        record.representation_equivalent for record in benchmark_run.candidate_records
    )


def test_main_comparison_is_fair_and_ablation_effects_are_reported(
    benchmark_summary: BenchmarkSummary,
) -> None:
    """Verify the main comparison tie and isolated graph-control effects."""

    metrics = {metric.method: metric for metric in benchmark_summary.method_metrics}
    assert metrics[UpdateMethod.DIRECT].violation_escape_rate == 0.0
    assert metrics[UpdateMethod.GRAPH_FULL].violation_escape_rate == 0.0
    assert metrics[UpdateMethod.DIRECT].valid_acceptance_rate == 1.0
    assert metrics[UpdateMethod.GRAPH_FULL].valid_acceptance_rate == 1.0
    assert all(
        comparison.difference == 0.0
        for comparison in benchmark_summary.main_comparisons
    )
    assert all(
        comparison.violation_escape_difference < 0
        for comparison in benchmark_summary.ablation_comparisons
    )
    assert benchmark_summary.label_mismatch_count == 0
    assert benchmark_summary.representation_mismatch_count == 0
    report = render_markdown_report(benchmark_summary)
    assert "主比較だけでは、グラフによる違反抑制の優位性を説明できません" in report
    assert "E1_task_information_provenance" in report


def test_rejected_sequence_steps_preserve_committed_state(
    benchmark_summary: BenchmarkSummary,
) -> None:
    """Require transactional rollback for every rejected sequential update."""

    direct = next(
        metric
        for metric in benchmark_summary.sequence_metrics
        if metric.method is UpdateMethod.DIRECT
    )
    graph = next(
        metric
        for metric in benchmark_summary.sequence_metrics
        if metric.method is UpdateMethod.GRAPH_FULL
    )
    assert direct.valid_acceptance_count == direct.valid_step_count
    assert graph.valid_acceptance_count == graph.valid_step_count
    assert direct.violation_escape_count == 0
    assert graph.violation_escape_count == 0
    assert direct.preserved_rejection_count == direct.rejected_step_count
    assert graph.preserved_rejection_count == graph.rejected_step_count


def test_output_manifest_reproduces_checksums(
    benchmark: BenchmarkDefinition,
    benchmark_run: BenchmarkRun,
    benchmark_summary: BenchmarkSummary,
    tmp_path: Path,
) -> None:
    """Write every artifact and record stable checksums in the run manifest."""

    manifest = write_benchmark_artifacts(
        benchmark,
        benchmark_run,
        benchmark_summary,
        tmp_path,
    )

    assert manifest.benchmark_checksum == benchmark_run.benchmark_checksum
    assert manifest.candidate_spec_count == 160
    assert manifest.one_shot_run_count == 800
    assert manifest.sequence_step_run_count == 120
    assert set(manifest.output_checksums) == {
        "candidate_results.jsonl",
        "paired_candidates.jsonl",
        "report.md",
        "sequence_results.jsonl",
        "summary.json",
    }
    assert (tmp_path / "run_manifest.json").is_file()
