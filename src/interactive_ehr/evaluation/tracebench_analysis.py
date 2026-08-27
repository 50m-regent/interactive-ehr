"""TraceBench-EHR正式評価の統計集計と成果物出力。"""

from __future__ import annotations

import platform
import random
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.evaluation.ehrsql_feasibility import sha256_file, sha256_text
from interactive_ehr.evaluation.tracebench_ehr import (
    CandidateRunRecord,
    MutationKind,
    TraceBenchmarkRun,
    TraceBenchConfig,
    ValidationCondition,
)


class ConditionMetrics(BaseModel):
    """一つの検査条件における主要評価と副次評価。"""

    model_config = ConfigDict(frozen=True)

    condition: ValidationCondition
    invalid_candidate_count: int = Field(ge=0)
    unsafe_acceptance_count: int = Field(ge=0)
    unsafe_acceptance_rate: float = Field(ge=0.0, le=1.0)
    valid_candidate_count: int = Field(ge=0)
    valid_acceptance_count: int = Field(ge=0)
    valid_acceptance_rate: float = Field(ge=0.0, le=1.0)
    localized_candidate_count: int = Field(ge=0)
    localization_correct_count: int = Field(ge=0)
    localization_accuracy: float = Field(ge=0.0, le=1.0)
    repair_attempt_count: int = Field(ge=0)
    repair_success_count: int = Field(ge=0)
    repair_success_rate: float = Field(ge=0.0, le=1.0)
    mean_validation_milliseconds: float = Field(ge=0.0)


class MutationMetrics(BaseModel):
    """変異種類と検査条件ごとの不整合流出。"""

    model_config = ConfigDict(frozen=True)

    mutation_kind: MutationKind
    condition: ValidationCondition
    candidate_count: int = Field(ge=0)
    template_count: int = Field(ge=0)
    unsafe_acceptance_count: int = Field(ge=0)
    unsafe_acceptance_rate: float = Field(ge=0.0, le=1.0)
    safe_rejection_count: int = Field(ge=0)
    localization_correct_count: int = Field(ge=0)
    repair_success_count: int = Field(ge=0)


class PairedDifference(BaseModel):
    """テンプレートでクラスタ化した条件間の対応差。"""

    model_config = ConfigDict(frozen=True)

    metric: str
    first_condition: ValidationCondition
    second_condition: ValidationCondition
    difference: float
    confidence_interval_95: tuple[float, float]
    template_count: int = Field(ge=0)
    bootstrap_iterations: int = Field(gt=0)


class TraceBenchSummary(BaseModel):
    """CHI原稿へ使う正式評価の集計。"""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    split: str
    interpretation_limit: str
    build_summary: dict[str, object]
    condition_metrics: list[ConditionMetrics]
    mutation_metrics: list[MutationMetrics]
    paired_differences: list[PairedDifference]
    label_mismatch_count: int = Field(ge=0)
    graph_sidecar_decision_mismatch_count: int = Field(ge=0)


class TraceBenchRunManifest(BaseModel):
    """入力、コード、設定、出力の再現条件。"""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    executed_at: str
    split: str
    dataset_repository: str
    dataset_commit: str
    dataset_version: str
    code_commit: str
    random_seed: int
    bootstrap_iterations: int
    query_timeout_seconds: float
    max_result_rows: int
    python_version: str
    platform: str
    pair_count: int
    candidate_run_count: int
    input_checksums: dict[str, str]
    implementation_checksums: dict[str, str]
    output_checksums: dict[str, str]


def analyze_tracebench_run(
    run: TraceBenchmarkRun,
    config: TraceBenchConfig,
) -> TraceBenchSummary:
    """候補単位の記録から主要評価、種類別結果、対応差を計算する。"""

    records = run.candidate_records
    condition_metrics = [
        _condition_metrics(records, condition) for condition in ValidationCondition
    ]
    mutation_metrics = [
        _mutation_metrics(records, mutation, condition)
        for mutation in MutationKind
        for condition in ValidationCondition
    ]
    comparisons = [
        (ValidationCondition.GRAPH_CONTRACT, ValidationCondition.LOCAL_CHECKS),
        (
            ValidationCondition.GRAPH_CONTRACT,
            ValidationCondition.ARTIFACT_CONTRACTS,
        ),
        (
            ValidationCondition.GRAPH_CONTRACT,
            ValidationCondition.SIDECAR_CONTRACT,
        ),
    ]
    paired_differences = [
        _paired_difference(
            records,
            first,
            second,
            metric=metric,
            seed=config.sample_seed + index,
            iterations=config.bootstrap_iterations,
        )
        for index, (first, second, metric) in enumerate(
            (
                (first, second, metric)
                for first, second in comparisons
                for metric in ("unsafe_acceptance_rate", "valid_acceptance_rate")
            )
        )
    ]
    graph_by_candidate = {
        record.candidate_id: record
        for record in records
        if record.condition is ValidationCondition.GRAPH_CONTRACT
    }
    sidecar_by_candidate = {
        record.candidate_id: record
        for record in records
        if record.condition is ValidationCondition.SIDECAR_CONTRACT
    }
    return TraceBenchSummary(
        benchmark_id=config.benchmark_id,
        benchmark_version=config.benchmark_version,
        split=run.build_summary.split.value,
        interpretation_limit=config.interpretation_limit,
        build_summary=run.build_summary.model_dump(mode="json"),
        condition_metrics=condition_metrics,
        mutation_metrics=mutation_metrics,
        paired_differences=paired_differences,
        label_mismatch_count=sum(
            record.expected_valid != record.oracle_valid for record in records
        ),
        graph_sidecar_decision_mismatch_count=sum(
            graph_by_candidate[candidate_id].accepted
            != sidecar_by_candidate[candidate_id].accepted
            for candidate_id in graph_by_candidate.keys() & sidecar_by_candidate.keys()
        ),
    )


def write_tracebench_outputs(
    *,
    output_dir: Path,
    run: TraceBenchmarkRun,
    summary: TraceBenchSummary,
    config: TraceBenchConfig,
    config_path: Path,
    annotated_path: Path,
    dataset_data_path: Path,
    database_path: Path,
    dataset_version: str,
    code_commit: str,
    implementation_paths: Sequence[Path],
) -> TraceBenchRunManifest:
    """機微情報を除いた実行結果と再現マニフェストを書く。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "pair_manifest.jsonl": _json_lines(run.pair_manifest),
        "candidate_results.jsonl": _json_lines(run.candidate_records),
        "build_summary.json": run.build_summary.model_dump_json(indent=2) + "\n",
        "summary.json": summary.model_dump_json(indent=2) + "\n",
        "report.md": render_tracebench_report(summary),
    }
    for filename, payload in payloads.items():
        (output_dir / filename).write_text(payload, encoding="utf-8")
    output_checksums = {
        filename: sha256_text(payload) for filename, payload in payloads.items()
    }
    manifest = TraceBenchRunManifest(
        benchmark_id=config.benchmark_id,
        benchmark_version=config.benchmark_version,
        executed_at=datetime.now(timezone.utc).isoformat(),
        split=run.build_summary.split.value,
        dataset_repository=config.dataset_repository,
        dataset_commit=config.dataset_commit,
        dataset_version=dataset_version,
        code_commit=code_commit,
        random_seed=config.sample_seed,
        bootstrap_iterations=config.bootstrap_iterations,
        query_timeout_seconds=config.query_timeout_seconds,
        max_result_rows=config.max_result_rows,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        pair_count=run.build_summary.pair_count,
        candidate_run_count=len(run.candidate_records),
        input_checksums={
            "annotated.json": sha256_file(annotated_path),
            "data.json": sha256_file(dataset_data_path),
            "mimic_iv.sqlite": sha256_file(database_path),
            "tracebench_ehr.v1.json": sha256_file(config_path),
        },
        implementation_checksums={
            path.name: sha256_file(path) for path in implementation_paths
        },
        output_checksums=output_checksums,
    )
    (output_dir / "run_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def render_tracebench_report(summary: TraceBenchSummary) -> str:
    """CHI原稿用の短い日本語レポートを生成する。"""

    condition_rows = "\n".join(
        "| "
        + " | ".join(
            (
                metric.condition.value,
                _format_rate(metric.unsafe_acceptance_rate),
                f"{metric.unsafe_acceptance_count}/{metric.invalid_candidate_count}",
                _format_rate(metric.valid_acceptance_rate),
                f"{metric.valid_acceptance_count}/{metric.valid_candidate_count}",
                _format_rate(metric.localization_accuracy),
                _format_rate(metric.repair_success_rate),
            )
        )
        + " |"
        for metric in summary.condition_metrics
    )
    comparison_rows = "\n".join(
        "| "
        + " | ".join(
            (
                comparison.metric,
                (
                    f"{comparison.first_condition.value} − "
                    f"{comparison.second_condition.value}"
                ),
                f"{comparison.difference:.4f}",
                (
                    f"[{comparison.confidence_interval_95[0]:.4f}, "
                    f"{comparison.confidence_interval_95[1]:.4f}]"
                ),
            )
        )
        + " |"
        for comparison in summary.paired_differences
    )
    return (
        f"# TraceBench-EHR正式評価 v{summary.benchmark_version}\n\n"
        "## 解釈の範囲\n\n"
        f"{summary.interpretation_limit}\n\n"
        "## データと候補\n\n"
        f"- 分割: {summary.split}\n"
        f"- 回答可能ケース: {summary.build_summary['answerable_case_count']}件\n"
        f"- 質問テンプレート: {summary.build_summary['answerable_template_count']}件\n"
        f"- 更新ペア: {summary.build_summary['pair_count']}件\n\n"
        "## 主要結果\n\n"
        "| 条件 | 不整合流出率 | 件数 | 妥当更新受理率 | 件数 | 特定率 | 修復成功率 |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        f"{condition_rows}\n\n"
        "## 条件間の対応差\n\n"
        "| 指標 | 比較 | 差 | 95%区間 |\n"
        "|---|---|---:|---:|\n"
        f"{comparison_rows}\n\n"
        "## 整合性確認\n\n"
        f"- 正解ラベルとの不一致: {summary.label_mismatch_count}件\n"
        "- グラフ契約と同じ内容を持つサイドカー契約の判定不一致: "
        f"{summary.graph_sidecar_decision_mismatch_count}件\n\n"
        "## データ管理\n\n"
        "質問文、正解SQL、患者ID、患者単位の結果値は保存していません。"
        "ケースID、チェックサム、変異種類、判定結果、集計だけを記録しています。\n"
    )


def _condition_metrics(
    records: Sequence[CandidateRunRecord],
    condition: ValidationCondition,
) -> ConditionMetrics:
    """条件別の主要評価と副次評価を集計する。"""

    selected = [record for record in records if record.condition is condition]
    invalid = [record for record in selected if not record.oracle_valid]
    valid = [record for record in selected if record.oracle_valid]
    localized = [
        record for record in invalid if record.localization_correct is not None
    ]
    repair_attempts = [record for record in invalid if record.repair_attempted]
    return ConditionMetrics(
        condition=condition,
        invalid_candidate_count=len(invalid),
        unsafe_acceptance_count=sum(record.unsafe_acceptance for record in invalid),
        unsafe_acceptance_rate=_rate(
            sum(record.unsafe_acceptance for record in invalid), len(invalid)
        ),
        valid_candidate_count=len(valid),
        valid_acceptance_count=sum(record.accepted for record in valid),
        valid_acceptance_rate=_rate(sum(record.accepted for record in valid), len(valid)),
        localized_candidate_count=len(localized),
        localization_correct_count=sum(
            record.localization_correct is True for record in localized
        ),
        localization_accuracy=_rate(
            sum(record.localization_correct is True for record in localized),
            len(localized),
        ),
        repair_attempt_count=len(repair_attempts),
        repair_success_count=sum(
            record.repair_success is True for record in repair_attempts
        ),
        repair_success_rate=_rate(
            sum(record.repair_success is True for record in repair_attempts),
            len(repair_attempts),
        ),
        mean_validation_milliseconds=(
            sum(record.validation_seconds for record in selected)
            / len(selected)
            * 1000.0
            if selected
            else 0.0
        ),
    )


def _mutation_metrics(
    records: Sequence[CandidateRunRecord],
    mutation: MutationKind,
    condition: ValidationCondition,
) -> MutationMetrics:
    """変異種類と条件の組合せを集計する。"""

    selected = [
        record
        for record in records
        if record.condition is condition
        and record.mutation_kind is mutation
        and not record.oracle_valid
    ]
    return MutationMetrics(
        mutation_kind=mutation,
        condition=condition,
        candidate_count=len(selected),
        template_count=len({record.template_checksum for record in selected}),
        unsafe_acceptance_count=sum(record.unsafe_acceptance for record in selected),
        unsafe_acceptance_rate=_rate(
            sum(record.unsafe_acceptance for record in selected), len(selected)
        ),
        safe_rejection_count=sum(record.safe_rejection for record in selected),
        localization_correct_count=sum(
            record.localization_correct is True for record in selected
        ),
        repair_success_count=sum(record.repair_success is True for record in selected),
    )


def _paired_difference(
    records: Sequence[CandidateRunRecord],
    first: ValidationCondition,
    second: ValidationCondition,
    *,
    metric: str,
    seed: int,
    iterations: int,
) -> PairedDifference:
    """テンプレートクラスターブートストラップで条件間の率差を求める。"""

    selector = _metric_selector(metric)
    relevant = [
        record
        for record in records
        if record.condition in (first, second)
        and (
            not record.oracle_valid
            if metric == "unsafe_acceptance_rate"
            else record.oracle_valid
        )
    ]
    by_condition = {
        condition: {
            record.candidate_id: record
            for record in relevant
            if record.condition is condition
        }
        for condition in (first, second)
    }
    candidate_ids = sorted(
        by_condition[first].keys() & by_condition[second].keys()
    )
    templates = sorted(
        {by_condition[first][candidate_id].template_checksum for candidate_id in candidate_ids}
    )
    observed = _rate_difference_for_candidates(
        candidate_ids,
        by_condition[first],
        by_condition[second],
        selector,
    )
    candidate_ids_by_template = {
        template: [
            candidate_id
            for candidate_id in candidate_ids
            if by_condition[first][candidate_id].template_checksum == template
        ]
        for template in templates
    }
    random_generator = random.Random(seed)
    bootstrap_values: list[float] = []
    for _ in range(iterations):
        sampled_ids = [
            candidate_id
            for _sampled_template in (
                random_generator.choice(templates) for _ in templates
            )
            for candidate_id in candidate_ids_by_template[_sampled_template]
        ]
        bootstrap_values.append(
            _rate_difference_for_candidates(
                sampled_ids,
                by_condition[first],
                by_condition[second],
                selector,
            )
        )
    bootstrap_values.sort()
    return PairedDifference(
        metric=metric,
        first_condition=first,
        second_condition=second,
        difference=observed,
        confidence_interval_95=(
            _percentile(bootstrap_values, 0.025),
            _percentile(bootstrap_values, 0.975),
        ),
        template_count=len(templates),
        bootstrap_iterations=iterations,
    )


def _metric_selector(metric: str) -> Callable[[CandidateRunRecord], bool]:
    """率差で数える二値結果を返す関数を選ぶ。"""

    if metric == "unsafe_acceptance_rate":
        return lambda record: record.unsafe_acceptance
    if metric == "valid_acceptance_rate":
        return lambda record: record.accepted
    raise ValueError(f"unknown metric: {metric}")


def _rate_difference_for_candidates(
    candidate_ids: Sequence[str],
    first_records: dict[str, CandidateRunRecord],
    second_records: dict[str, CandidateRunRecord],
    selector: Callable[[CandidateRunRecord], bool],
) -> float:
    """同じ候補集合で第一条件と第二条件の率差を求める。"""

    if not candidate_ids:
        return 0.0
    first_rate = sum(selector(first_records[item]) for item in candidate_ids) / len(
        candidate_ids
    )
    second_rate = sum(selector(second_records[item]) for item in candidate_ids) / len(
        candidate_ids
    )
    return first_rate - second_rate


def _percentile(values: Sequence[float], probability: float) -> float:
    """線形補間を用いたパーセンタイルを返す。"""

    if not values:
        return 0.0
    position = (len(values) - 1) * probability
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    return values[lower_index] * (1.0 - fraction) + values[upper_index] * fraction


def _json_lines(models: Sequence[BaseModel]) -> str:
    """Pydanticモデルを安定したJSON Linesへ変換する。"""

    return "".join(model.model_dump_json() + "\n" for model in models)


def _rate(numerator: int, denominator: int) -> float:
    """分母が0なら0を返す割合計算を行う。"""

    return numerator / denominator if denominator else 0.0


def _format_rate(value: float) -> str:
    """割合を小数点1桁の百分率へ変換する。"""

    return f"{value * 100:.1f}%"
