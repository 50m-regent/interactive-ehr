"""Statistics and reproducible artifacts for the UI update benchmark."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
import random
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from interactive_ehr.evaluation import update_benchmark as benchmark_module
from interactive_ehr.evaluation.update_benchmark import (
    BenchmarkDefinition,
    BenchmarkRun,
    BenchmarkSplit,
    CandidateRunRecord,
    RequirementDefinition,
    SequenceRunRecord,
    UpdateMethod,
    canonical_checksum,
)


class MethodMetrics(BaseModel):
    """Primary error and acceptance rates for one comparison method."""

    model_config = ConfigDict(frozen=True)

    method: UpdateMethod
    invalid_candidate_count: int
    violation_escape_count: int
    violation_escape_rate: float
    valid_candidate_count: int
    valid_acceptance_count: int
    valid_acceptance_rate: float
    safe_rejection_count: int
    unsafe_acceptance_count: int
    runtime_failure_count: int


class PairedDifference(BaseModel):
    """Case-clustered paired rate difference and percentile interval."""

    model_config = ConfigDict(frozen=True)

    metric: str
    first_method: UpdateMethod
    second_method: UpdateMethod
    difference: float
    confidence_interval_95: tuple[float, float]
    cluster_count: int
    bootstrap_iterations: int


class AblationComparison(BaseModel):
    """Graph-full comparison with one ablated graph condition."""

    model_config = ConfigDict(frozen=True)

    ablation_method: UpdateMethod
    violation_escape_difference: float
    raw_p_value: float
    holm_adjusted_p_value: float


class SequenceMetrics(BaseModel):
    """Sequential-update acceptance and rollback checks for one method."""

    model_config = ConfigDict(frozen=True)

    method: UpdateMethod
    step_count: int
    valid_step_count: int
    valid_acceptance_count: int
    invalid_step_count: int
    violation_escape_count: int
    rejected_step_count: int
    preserved_rejection_count: int


class RequirementInventory(BaseModel):
    """Implementation and maintenance evidence for one requirement."""

    model_config = ConfigDict(frozen=True)

    id: str
    runtime_comparable: bool
    direct_expression: str
    graph_expression: str
    direct_implementation: list[str]
    graph_implementation: list[str]
    direct_lines_of_code: int | None
    graph_lines_of_code: int | None
    referenced_artifacts: list[str]
    maintenance_touchpoints: list[str]
    test_count: int


class BenchmarkSummary(BaseModel):
    """Analysis result written alongside raw candidate-level observations."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    interpretation_limit: str
    evaluation_case_count: int
    evaluation_candidate_spec_count: int
    method_metrics: list[MethodMetrics]
    main_comparisons: list[PairedDifference]
    ablation_comparisons: list[AblationComparison]
    sequence_metrics: list[SequenceMetrics]
    requirement_inventory: list[RequirementInventory]
    label_mismatch_count: int
    representation_mismatch_count: int


class RunManifest(BaseModel):
    """Inputs, software identity, and checksums for generated result artifacts."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    benchmark_checksum: str
    implementation_checksum: str
    random_seed: int
    bootstrap_iterations: int
    python_version: str
    platform: str
    candidate_spec_count: int
    one_shot_run_count: int
    sequence_step_run_count: int
    output_checksums: dict[str, str]


def analyze_benchmark_run(
    benchmark: BenchmarkDefinition,
    run: BenchmarkRun,
) -> BenchmarkSummary:
    """Compute pre-registered primary, ablation, and sequence analyses."""

    evaluation_records = [
        record
        for record in run.candidate_records
        if record.split is BenchmarkSplit.EVALUATION
    ]
    method_metrics = [
        _method_metrics(evaluation_records, method) for method in UpdateMethod
    ]
    main_comparisons = [
        _paired_rate_difference(
            evaluation_records,
            UpdateMethod.GRAPH_FULL,
            UpdateMethod.DIRECT,
            metric="violation_escape_rate",
            seed=benchmark.random_seed,
            iterations=benchmark.bootstrap_iterations,
        ),
        _paired_rate_difference(
            evaluation_records,
            UpdateMethod.GRAPH_FULL,
            UpdateMethod.DIRECT,
            metric="valid_acceptance_rate",
            seed=benchmark.random_seed + 1,
            iterations=benchmark.bootstrap_iterations,
        ),
    ]
    ablation_comparisons = _ablation_comparisons(
        evaluation_records,
        seed=benchmark.random_seed + 2,
        iterations=benchmark.bootstrap_iterations,
    )
    sequence_records = [
        record
        for record in run.sequence_records
        if record.split is BenchmarkSplit.EVALUATION
    ]
    evaluation_case_count = len(
        {
            record.case_id
            for record in evaluation_records
            if record.method is UpdateMethod.DIRECT
        }
    )
    evaluation_spec_count = len(
        {
            record.candidate_id
            for record in evaluation_records
            if record.method is UpdateMethod.DIRECT
        }
    )
    return BenchmarkSummary(
        benchmark_id=benchmark.id,
        benchmark_version=benchmark.version,
        interpretation_limit=benchmark.interpretation_limit,
        evaluation_case_count=evaluation_case_count,
        evaluation_candidate_spec_count=evaluation_spec_count,
        method_metrics=method_metrics,
        main_comparisons=main_comparisons,
        ablation_comparisons=ablation_comparisons,
        sequence_metrics=[
            _sequence_metrics(sequence_records, method) for method in UpdateMethod
        ],
        requirement_inventory=[
            _requirement_inventory(requirement)
            for requirement in benchmark.requirements
        ],
        label_mismatch_count=sum(
            record.expected_valid != record.oracle_valid
            for record in run.candidate_records
        ),
        representation_mismatch_count=sum(
            not record.representation_equivalent
            for record in run.candidate_records
        ),
    )


def write_benchmark_artifacts(
    benchmark: BenchmarkDefinition,
    run: BenchmarkRun,
    summary: BenchmarkSummary,
    output_dir: Path,
) -> RunManifest:
    """Write raw observations, analysis, report, and a checksum manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "paired_candidates.jsonl": _json_lines(run.paired_candidates),
        "candidate_results.jsonl": _json_lines(run.candidate_records),
        "sequence_results.jsonl": _json_lines(run.sequence_records),
        "summary.json": summary.model_dump_json(indent=2) + "\n",
        "report.md": render_markdown_report(summary),
    }
    for filename, content in payloads.items():
        (output_dir / filename).write_text(content, encoding="utf-8")
    output_checksums = {
        filename: _text_checksum(content) for filename, content in payloads.items()
    }
    manifest = RunManifest(
        benchmark_id=benchmark.id,
        benchmark_version=benchmark.version,
        benchmark_checksum=run.benchmark_checksum,
        implementation_checksum=_implementation_checksum(),
        random_seed=benchmark.random_seed,
        bootstrap_iterations=benchmark.bootstrap_iterations,
        python_version=platform.python_version(),
        platform=sys.platform,
        candidate_spec_count=len(run.paired_candidates),
        one_shot_run_count=len(run.candidate_records),
        sequence_step_run_count=len(run.sequence_records),
        output_checksums=output_checksums,
    )
    (output_dir / "run_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def render_markdown_report(summary: BenchmarkSummary) -> str:
    """Render a concise, paper-oriented report from the computed summary."""

    main_difference_by_metric = {
        comparison.metric: comparison.difference
        for comparison in summary.main_comparisons
    }
    if all(value == 0.0 for value in main_difference_by_metric.values()):
        main_interpretation = (
            "この固定評価では、同じ要件を実装した直接差分方式と完全なグラフ方式に"
            "性能差はありませんでした。主比較だけでは、グラフによる違反抑制の"
            "優位性を説明できません。"
        )
    else:
        main_interpretation = (
            "主比較の差は固定した共通要件の範囲に限って解釈し、"
            "グラフ固有の表現可能性とは分けて扱います。"
        )
    metric_rows = "\n".join(
        "| "
        + " | ".join(
            [
                metric.method.value,
                _format_rate(metric.violation_escape_rate),
                f"{metric.violation_escape_count}/{metric.invalid_candidate_count}",
                _format_rate(metric.valid_acceptance_rate),
                f"{metric.valid_acceptance_count}/{metric.valid_candidate_count}",
            ]
        )
        + " |"
        for metric in summary.method_metrics
    )
    comparison_rows = "\n".join(
        "| "
        + " | ".join(
            [
                comparison.metric,
                f"{comparison.first_method.value} − {comparison.second_method.value}",
                f"{comparison.difference:.4f}",
                (
                    f"[{comparison.confidence_interval_95[0]:.4f}, "
                    f"{comparison.confidence_interval_95[1]:.4f}]"
                ),
            ]
        )
        + " |"
        for comparison in summary.main_comparisons
    )
    ablation_rows = "\n".join(
        "| "
        + " | ".join(
            [
                comparison.ablation_method.value,
                f"{comparison.violation_escape_difference:.4f}",
                f"{comparison.raw_p_value:.4f}",
                f"{comparison.holm_adjusted_p_value:.4f}",
            ]
        )
        + " |"
        for comparison in summary.ablation_comparisons
    )
    requirement_rows = "\n".join(
        "| "
        + " | ".join(
            [
                requirement.id,
                "対象" if requirement.runtime_comparable else "表現可能性のみ",
                requirement.direct_expression,
                requirement.graph_expression,
                (
                    str(requirement.direct_lines_of_code)
                    if requirement.direct_lines_of_code is not None
                    else "対象外"
                ),
                (
                    str(requirement.graph_lines_of_code)
                    if requirement.graph_lines_of_code is not None
                    else "対象外"
                ),
            ]
        )
        + " |"
        for requirement in summary.requirement_inventory
    )
    return (
        "# UI更新ベンチマークv0.4 技術評価\n\n"
        "## 解釈の範囲\n\n"
        f"{summary.interpretation_limit}\n\n"
        "## データ\n\n"
        f"評価セットは{summary.evaluation_case_count}件、"
        f"共通変更仕様は{summary.evaluation_candidate_spec_count}件です。"
        "各入力は決定的に1回だけ実行しています。\n\n"
        "## 主な指標\n\n"
        "| 方式 | 違反通過率 | 通過数 | 妥当更新受理率 | 受理数 |\n"
        "| --- | ---: | ---: | ---: | ---: |\n"
        f"{metric_rows}\n\n"
        "## 主比較\n\n"
        "差はグラフ方式から直接差分方式を引いた値です。"
        "95%区間はケース単位のクラスターブートストラップです。\n\n"
        "| 指標 | 比較 | 差 | 95%区間 |\n"
        "| --- | --- | ---: | ---: |\n"
        f"{comparison_rows}\n\n"
        f"{main_interpretation}\n\n"
        "## グラフ方式の除去比較\n\n"
        "p値はケース単位の符号反転検定で求め、Holm法で補正しています。"
        "差は完全なグラフ方式から各除去条件を引いた値です。\n\n"
        "| 除去条件 | 違反通過率の差 | 未補正p値 | Holm補正p値 |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"{ablation_rows}\n\n"
        "## 要件の表現可能性と実装量\n\n"
        "行数は登録した検査関数のソース行数です。実装量の代理指標であり、"
        "理解しやすさや保守性そのものは示しません。\n\n"
        "| 要件 | 主比較 | 直接差分での表現 | グラフでの表現 | 直接差分の行数 | グラフの行数 |\n"
        "| --- | --- | --- | --- | ---: | ---: |\n"
        f"{requirement_rows}\n\n"
        "## 整合性確認\n\n"
        f"独立オラクルとのラベル不一致は{summary.label_mismatch_count}件、"
        f"二方式の意味上の対応不一致は{summary.representation_mismatch_count}件でした。\n\n"
        "## 論文での扱い\n\n"
        "この結果は合成スキーマ上の構造的な依存関係保護を測っています。"
        "専門家確認前の安全条件を臨床的安全性の根拠には使いません。"
        "直接差分方式とグラフ方式へ同じ要件を実装した主比較と、"
        "グラフの各制御を外した除去比較は分けて報告します。\n"
    )


def _method_metrics(
    records: Sequence[CandidateRunRecord],
    method: UpdateMethod,
) -> MethodMetrics:
    """Compute primary rates for one method on the evaluation split."""

    matching = [record for record in records if record.method is method]
    invalid = [record for record in matching if not record.oracle_valid]
    valid = [record for record in matching if record.oracle_valid]
    violation_escapes = sum(record.accepted for record in invalid)
    valid_acceptances = sum(record.accepted and not record.runtime_failure for record in valid)
    return MethodMetrics(
        method=method,
        invalid_candidate_count=len(invalid),
        violation_escape_count=violation_escapes,
        violation_escape_rate=_safe_rate(violation_escapes, len(invalid)),
        valid_candidate_count=len(valid),
        valid_acceptance_count=valid_acceptances,
        valid_acceptance_rate=_safe_rate(valid_acceptances, len(valid)),
        safe_rejection_count=sum(record.safe_rejection for record in matching),
        unsafe_acceptance_count=sum(record.unsafe_acceptance for record in matching),
        runtime_failure_count=sum(record.runtime_failure for record in matching),
    )


def _paired_rate_difference(
    records: Sequence[CandidateRunRecord],
    first_method: UpdateMethod,
    second_method: UpdateMethod,
    *,
    metric: str,
    seed: int,
    iterations: int,
) -> PairedDifference:
    """Estimate a case-clustered paired rate difference and percentile interval."""

    case_ids = sorted({record.case_id for record in records})
    first_by_case = _case_rates(records, first_method, metric, case_ids)
    second_by_case = _case_rates(records, second_method, metric, case_ids)
    differences = [
        first_by_case[case_id] - second_by_case[case_id] for case_id in case_ids
    ]
    observed = sum(differences) / len(differences)
    random_generator = random.Random(seed)
    bootstrap_values = []
    for _ in range(iterations):
        sample = [random_generator.choice(differences) for _ in differences]
        bootstrap_values.append(sum(sample) / len(sample))
    lower, upper = _percentile_interval(bootstrap_values)
    return PairedDifference(
        metric=metric,
        first_method=first_method,
        second_method=second_method,
        difference=observed,
        confidence_interval_95=(lower, upper),
        cluster_count=len(case_ids),
        bootstrap_iterations=iterations,
    )


def _case_rates(
    records: Sequence[CandidateRunRecord],
    method: UpdateMethod,
    metric: str,
    case_ids: Sequence[str],
) -> dict[str, float]:
    """Compute the selected candidate-level rate within each case cluster."""

    rates: dict[str, float] = {}
    for case_id in case_ids:
        matching = [
            record
            for record in records
            if record.method is method and record.case_id == case_id
        ]
        if metric == "violation_escape_rate":
            denominator = [record for record in matching if not record.oracle_valid]
            numerator = [record for record in denominator if record.accepted]
        elif metric == "valid_acceptance_rate":
            denominator = [record for record in matching if record.oracle_valid]
            numerator = [
                record
                for record in denominator
                if record.accepted and not record.runtime_failure
            ]
        else:
            raise ValueError(f"unknown paired metric: {metric}")
        rates[case_id] = _safe_rate(len(numerator), len(denominator))
    return rates


def _ablation_comparisons(
    records: Sequence[CandidateRunRecord],
    *,
    seed: int,
    iterations: int,
) -> list[AblationComparison]:
    """Compare full graph control with each ablation and apply Holm correction."""

    case_ids = sorted({record.case_id for record in records})
    full_rates = _case_rates(
        records,
        UpdateMethod.GRAPH_FULL,
        "violation_escape_rate",
        case_ids,
    )
    ablation_methods = [
        UpdateMethod.GRAPH_NO_SCOPE,
        UpdateMethod.GRAPH_NO_SAFETY,
        UpdateMethod.GRAPH_NO_TRACEABILITY,
    ]
    raw_results: list[tuple[UpdateMethod, float, float]] = []
    for offset, ablation_method in enumerate(ablation_methods):
        ablation_rates = _case_rates(
            records,
            ablation_method,
            "violation_escape_rate",
            case_ids,
        )
        differences = [
            full_rates[case_id] - ablation_rates[case_id]
            for case_id in case_ids
        ]
        difference = sum(differences) / len(differences)
        raw_p_value = _paired_sign_flip_p_value(
            differences,
            seed=seed + offset,
            iterations=iterations,
        )
        raw_results.append((ablation_method, difference, raw_p_value))
    adjusted = _holm_adjust([result[2] for result in raw_results])
    return [
        AblationComparison(
            ablation_method=method,
            violation_escape_difference=difference,
            raw_p_value=raw_p_value,
            holm_adjusted_p_value=adjusted[index],
        )
        for index, (method, difference, raw_p_value) in enumerate(raw_results)
    ]


def _paired_sign_flip_p_value(
    differences: Sequence[float],
    *,
    seed: int,
    iterations: int,
) -> float:
    """Return a two-sided cluster-level randomization p-value."""

    observed = abs(sum(differences) / len(differences))
    if observed == 0:
        return 1.0
    random_generator = random.Random(seed)
    as_extreme = 0
    for _ in range(iterations):
        randomized = [
            difference * random_generator.choice((-1, 1))
            for difference in differences
        ]
        if abs(sum(randomized) / len(randomized)) >= observed - 1e-12:
            as_extreme += 1
    return (as_extreme + 1) / (iterations + 1)


def _holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Apply the step-down Holm family-wise error correction."""

    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running_maximum = 0.0
    comparison_count = len(p_values)
    for rank, (original_index, p_value) in enumerate(ordered):
        candidate = min(1.0, (comparison_count - rank) * p_value)
        running_maximum = max(running_maximum, candidate)
        adjusted[original_index] = running_maximum
    return adjusted


def _sequence_metrics(
    records: Sequence[SequenceRunRecord],
    method: UpdateMethod,
) -> SequenceMetrics:
    """Summarize sequential acceptance and transactional rejection behavior."""

    matching = [record for record in records if record.method is method]
    valid = [record for record in matching if record.oracle_valid]
    invalid = [record for record in matching if not record.oracle_valid]
    rejected = [record for record in matching if not record.accepted]
    return SequenceMetrics(
        method=method,
        step_count=len(matching),
        valid_step_count=len(valid),
        valid_acceptance_count=sum(record.accepted for record in valid),
        invalid_step_count=len(invalid),
        violation_escape_count=sum(record.accepted for record in invalid),
        rejected_step_count=len(rejected),
        preserved_rejection_count=sum(
            record.state_preserved_after_rejection for record in rejected
        ),
    )


def _requirement_inventory(
    requirement: RequirementDefinition,
) -> RequirementInventory:
    """Resolve registered function names into implementation line counts."""

    return RequirementInventory(
        id=requirement.id,
        runtime_comparable=requirement.runtime_comparable,
        direct_expression=requirement.direct_expression,
        graph_expression=requirement.graph_expression,
        direct_implementation=requirement.direct_implementation,
        graph_implementation=requirement.graph_implementation,
        direct_lines_of_code=_implementation_lines(requirement.direct_implementation),
        graph_lines_of_code=_implementation_lines(requirement.graph_implementation),
        referenced_artifacts=requirement.referenced_artifacts,
        maintenance_touchpoints=requirement.maintenance_touchpoints,
        test_count=len(requirement.tests),
    )


def _implementation_lines(function_names: Sequence[str]) -> int | None:
    """Count source lines for named benchmark validator functions."""

    if not function_names:
        return None
    functions: list[Callable[..., Any]] = []
    for function_name in function_names:
        function = getattr(benchmark_module, function_name, None)
        if function is None or not callable(function):
            raise ValueError(f"unknown implementation function: {function_name}")
        functions.append(function)
    return sum(len(inspect.getsourcelines(function)[0]) for function in functions)


def _implementation_checksum() -> str:
    """Checksum the benchmark implementation modules used in this run."""

    module_paths = [
        Path(benchmark_module.__file__ or ""),
        Path(__file__),
    ]
    payload = {
        path.name: path.read_text(encoding="utf-8") for path in module_paths
    }
    return canonical_checksum(payload)


def _percentile_interval(values: Sequence[float]) -> tuple[float, float]:
    """Return the nearest-rank 2.5th and 97.5th percentiles."""

    ordered = sorted(values)
    lower_index = int(0.025 * (len(ordered) - 1))
    upper_index = int(0.975 * (len(ordered) - 1))
    return ordered[lower_index], ordered[upper_index]


def _safe_rate(numerator: int, denominator: int) -> float:
    """Divide counts while rejecting an undefined rate."""

    if denominator == 0:
        raise ValueError("rate denominator must be positive")
    return numerator / denominator


def _format_rate(value: float) -> str:
    """Format a proportion as a one-decimal percentage."""

    return f"{value * 100:.1f}%"


def _json_lines(models: Sequence[BaseModel]) -> str:
    """Serialize models as stable, one-record-per-line JSON Lines."""

    return "".join(
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for model in models
    )


def _text_checksum(content: str) -> str:
    """Return the SHA-256 checksum of UTF-8 text."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()
