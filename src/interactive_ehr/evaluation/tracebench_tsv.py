"""TraceBench-EHRの保存済み結果を検証してTSVへ変換する。"""

from __future__ import annotations

import csv
import io
import json
import math
import random
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from interactive_ehr.evaluation.ehrsql_feasibility import sha256_file, sha256_text

EXPORT_VERSION = "1.0.0"

PAIR_FIELDS = (
    "pair_id",
    "mutation_kind",
    "template_checksum",
    "source_case_id",
    "target_case_id",
    "valid_candidate_checksum",
    "invalid_candidate_checksum",
    "contract_checksum",
)

CANDIDATE_FIELDS = (
    "pair_id",
    "candidate_id",
    "template_checksum",
    "mutation_kind",
    "condition",
    "expected_valid",
    "oracle_valid",
    "accepted",
    "unsafe_acceptance",
    "safe_rejection",
    "over_rejection",
    "localization_correct",
    "repair_attempted",
    "repair_success",
    "issue_codes",
    "validation_seconds",
)

CONDITION_FIELDS = (
    "condition",
    "invalid_candidate_count",
    "unsafe_acceptance_count",
    "unsafe_acceptance_rate",
    "valid_candidate_count",
    "valid_acceptance_count",
    "valid_acceptance_rate",
    "localized_candidate_count",
    "localization_correct_count",
    "localization_accuracy",
    "repair_attempt_count",
    "repair_success_count",
    "repair_success_rate",
    "mean_validation_milliseconds",
)

MUTATION_FIELDS = (
    "mutation_kind",
    "condition",
    "candidate_count",
    "template_count",
    "unsafe_acceptance_count",
    "unsafe_acceptance_rate",
    "safe_rejection_count",
    "localization_correct_count",
    "repair_success_count",
)

PAIRED_DIFFERENCE_FIELDS = (
    "metric",
    "first_condition",
    "second_condition",
    "difference",
    "confidence_interval_95_lower",
    "confidence_interval_95_upper",
    "template_count",
    "bootstrap_iterations",
)

BUILD_SCALAR_FIELDS = (
    "split",
    "total_case_count",
    "answerable_case_count",
    "answerable_template_count",
    "baseline_success_count",
    "baseline_success_rate",
    "baseline_failure_count",
    "row_count_capped_count",
    "empty_result_count",
    "pair_count",
)

MUTATION_KINDS = (
    "patient",
    "clinical_item",
    "time_constraint",
    "aggregation_operation",
    "information_source",
    "widget_mapping",
    "data_widget_connection",
    "stale_result",
)

SOURCE_FILENAMES = (
    "run_manifest.json",
    "build_summary.json",
    "summary.json",
    "pair_manifest.jsonl",
    "candidate_results.jsonl",
)

HEX_24_PATTERN = re.compile(r"^[0-9a-f]{24}$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def export_tracebench_tsv(run_dir: Path, output_dir: Path) -> dict[str, object]:
    """保存済みの正式評価を検証し、表形式のTSVとマニフェストを書く。"""

    resolved_run_dir = run_dir.resolve()
    resolved_output_dir = output_dir.resolve()
    if resolved_run_dir == resolved_output_dir:
        raise ValueError("output directory must differ from the source run directory")

    run_manifest = _read_json_object(run_dir / "run_manifest.json")
    build_summary = _read_json_object(run_dir / "build_summary.json")
    summary = _read_json_object(run_dir / "summary.json")
    pair_records = _read_json_lines(run_dir / "pair_manifest.jsonl")
    candidate_records = _read_json_lines(run_dir / "candidate_results.jsonl")

    _validate_exact_fields(pair_records, PAIR_FIELDS, "pair_manifest.jsonl")
    _validate_exact_fields(
        candidate_records,
        CANDIDATE_FIELDS,
        "candidate_results.jsonl",
    )
    _validate_hashed_identifiers(pair_records, candidate_records)
    _verify_source_checksums(run_dir, run_manifest)
    _verify_summary(
        run_manifest=run_manifest,
        build_summary=build_summary,
        summary=summary,
        pair_records=pair_records,
        candidate_records=candidate_records,
    )

    condition_rows = _object_list(summary, "condition_metrics")
    mutation_rows = _object_list(summary, "mutation_metrics")
    difference_rows = [
        _flatten_paired_difference(item)
        for item in _object_list(summary, "paired_differences")
    ]
    build_row, build_fields = _flatten_build_summary(build_summary)
    export_rows: dict[str, tuple[Sequence[str], Sequence[Mapping[str, object]]]] = {
        "build_summary.tsv": (build_fields, [build_row]),
        "condition_metrics.tsv": (CONDITION_FIELDS, condition_rows),
        "mutation_metrics.tsv": (MUTATION_FIELDS, mutation_rows),
        "paired_differences.tsv": (
            PAIRED_DIFFERENCE_FIELDS,
            difference_rows,
        ),
        "pair_manifest.tsv": (PAIR_FIELDS, pair_records),
        "candidate_results.tsv": (CANDIDATE_FIELDS, candidate_records),
    }
    payloads = {
        filename: _tsv_payload(fieldnames, rows)
        for filename, (fieldnames, rows) in export_rows.items()
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in payloads.items():
        (output_dir / filename).write_text(payload, encoding="utf-8")

    manifest: dict[str, object] = {
        "export_version": EXPORT_VERSION,
        "implementation_files": {
            "tracebench_tsv.py": sha256_file(Path(__file__)),
        },
        "source_files": {
            filename: sha256_file(run_dir / filename) for filename in SOURCE_FILENAMES
        },
        "output_files": {
            filename: sha256_text(payload) for filename, payload in payloads.items()
        },
        "row_counts": {
            filename: len(rows) for filename, (_, rows) in export_rows.items()
        },
        "verification": {
            "source_checksums_match_run_manifest": True,
            "summary_matches_candidate_results": True,
            "paired_confidence_intervals_recomputed": True,
            "export_fields_are_allowlisted": True,
        },
    }
    (output_dir / "export_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_json_object(path: Path) -> dict[str, object]:
    """JSONファイルをオブジェクトとして読む。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return cast(dict[str, object], payload)


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    """JSON Linesをオブジェクトの一覧として読む。"""

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}:{line_number} must contain an object")
        records.append(cast(dict[str, object], payload))
    return records


def _validate_exact_fields(
    records: Sequence[Mapping[str, object]],
    expected_fields: Sequence[str],
    source_name: str,
) -> None:
    """行に許可した列だけが含まれることを確認する。"""

    expected = set(expected_fields)
    for row_number, record in enumerate(records, start=1):
        observed = set(record)
        if observed != expected:
            missing = sorted(expected - observed)
            unexpected = sorted(observed - expected)
            raise ValueError(
                f"{source_name}:{row_number} has unexpected schema; "
                f"missing={missing}, unexpected={unexpected}"
            )


def _validate_hashed_identifiers(
    pair_records: Sequence[Mapping[str, object]],
    candidate_records: Sequence[Mapping[str, object]],
) -> None:
    """識別子が生の患者番号ではなく固定長のハッシュであることを確認する。"""

    for row_number, record in enumerate(pair_records, start=1):
        for field in ("pair_id", "source_case_id", "target_case_id"):
            value = _string(record, field)
            if HEX_24_PATTERN.fullmatch(value) is None:
                raise ValueError(
                    f"pair_manifest.jsonl:{row_number} has invalid {field}"
                )
        for field in (
            "template_checksum",
            "valid_candidate_checksum",
            "invalid_candidate_checksum",
            "contract_checksum",
        ):
            value = _string(record, field)
            if HEX_64_PATTERN.fullmatch(value) is None:
                raise ValueError(
                    f"pair_manifest.jsonl:{row_number} has invalid {field}"
                )

    for row_number, record in enumerate(candidate_records, start=1):
        pair_id = _string(record, "pair_id")
        candidate_id = _string(record, "candidate_id")
        if HEX_24_PATTERN.fullmatch(pair_id) is None:
            raise ValueError(
                f"candidate_results.jsonl:{row_number} has invalid pair_id"
            )
        if candidate_id not in (f"{pair_id}-valid", f"{pair_id}-invalid"):
            raise ValueError(
                f"candidate_results.jsonl:{row_number} has invalid candidate_id"
            )
        if HEX_64_PATTERN.fullmatch(_string(record, "template_checksum")) is None:
            raise ValueError(
                f"candidate_results.jsonl:{row_number} has invalid template_checksum"
            )


def _verify_source_checksums(
    run_dir: Path,
    run_manifest: Mapping[str, object],
) -> None:
    """正式実行マニフェストと元成果物のチェックサムを照合する。"""

    output_checksums = _object(run_manifest, "output_checksums")
    for filename in (
        "build_summary.json",
        "summary.json",
        "pair_manifest.jsonl",
        "candidate_results.jsonl",
    ):
        expected = _string(output_checksums, filename)
        observed = sha256_file(run_dir / filename)
        if observed != expected:
            raise ValueError(f"source checksum mismatch: {filename}")


def _verify_summary(
    *,
    run_manifest: Mapping[str, object],
    build_summary: Mapping[str, object],
    summary: Mapping[str, object],
    pair_records: Sequence[Mapping[str, object]],
    candidate_records: Sequence[Mapping[str, object]],
) -> None:
    """候補単位の記録から主要集計と95%区間を再計算して照合する。"""

    summary_build = _object(summary, "build_summary")
    if summary_build != build_summary:
        raise ValueError("summary build data differs from build_summary.json")
    if len(pair_records) != _integer(build_summary, "pair_count"):
        raise ValueError("pair manifest row count differs from build summary")
    if len(candidate_records) != _integer(run_manifest, "candidate_run_count"):
        raise ValueError("candidate row count differs from run manifest")

    for expected in _object_list(summary, "condition_metrics"):
        observed = _condition_metrics(candidate_records, _string(expected, "condition"))
        _assert_metric_mapping(expected, observed, CONDITION_FIELDS)
    for expected in _object_list(summary, "mutation_metrics"):
        observed = _mutation_metrics(
            candidate_records,
            mutation_kind=_string(expected, "mutation_kind"),
            condition=_string(expected, "condition"),
        )
        _assert_metric_mapping(expected, observed, MUTATION_FIELDS)

    label_mismatch_count = sum(
        _boolean(record, "expected_valid") != _boolean(record, "oracle_valid")
        for record in candidate_records
    )
    if label_mismatch_count != _integer(summary, "label_mismatch_count"):
        raise ValueError("label mismatch count differs from summary")
    graph_sidecar_mismatch_count = _graph_sidecar_mismatch_count(candidate_records)
    if graph_sidecar_mismatch_count != _integer(
        summary, "graph_sidecar_decision_mismatch_count"
    ):
        raise ValueError("graph and sidecar mismatch count differs from summary")

    seed = _integer(run_manifest, "random_seed")
    for index, expected in enumerate(_object_list(summary, "paired_differences")):
        observed = _paired_difference(candidate_records, expected, seed + index)
        _assert_float(
            _number(expected, "difference"),
            cast(float, observed["difference"]),
            "paired difference",
        )
        expected_interval = _number_list(expected, "confidence_interval_95", length=2)
        observed_interval = cast(
            tuple[float, float], observed["confidence_interval_95"]
        )
        _assert_float(
            expected_interval[0], observed_interval[0], "lower confidence bound"
        )
        _assert_float(
            expected_interval[1], observed_interval[1], "upper confidence bound"
        )


def _condition_metrics(
    records: Sequence[Mapping[str, object]],
    condition: str,
) -> dict[str, object]:
    """候補行から一条件の主要指標を独立に集計する。"""

    selected = [
        record for record in records if _string(record, "condition") == condition
    ]
    invalid = [record for record in selected if not _boolean(record, "oracle_valid")]
    valid = [record for record in selected if _boolean(record, "oracle_valid")]
    localized = [
        record for record in invalid if record.get("localization_correct") is not None
    ]
    repair_attempts = [
        record for record in invalid if _boolean(record, "repair_attempted")
    ]
    return {
        "condition": condition,
        "invalid_candidate_count": len(invalid),
        "unsafe_acceptance_count": sum(
            _boolean(record, "unsafe_acceptance") for record in invalid
        ),
        "unsafe_acceptance_rate": _rate(
            sum(_boolean(record, "unsafe_acceptance") for record in invalid),
            len(invalid),
        ),
        "valid_candidate_count": len(valid),
        "valid_acceptance_count": sum(_boolean(record, "accepted") for record in valid),
        "valid_acceptance_rate": _rate(
            sum(_boolean(record, "accepted") for record in valid), len(valid)
        ),
        "localized_candidate_count": len(localized),
        "localization_correct_count": sum(
            record.get("localization_correct") is True for record in localized
        ),
        "localization_accuracy": _rate(
            sum(record.get("localization_correct") is True for record in localized),
            len(localized),
        ),
        "repair_attempt_count": len(repair_attempts),
        "repair_success_count": sum(
            record.get("repair_success") is True for record in repair_attempts
        ),
        "repair_success_rate": _rate(
            sum(record.get("repair_success") is True for record in repair_attempts),
            len(repair_attempts),
        ),
        "mean_validation_milliseconds": (
            sum(_number(record, "validation_seconds") for record in selected)
            / len(selected)
            * 1000.0
            if selected
            else 0.0
        ),
    }


def _mutation_metrics(
    records: Sequence[Mapping[str, object]],
    *,
    mutation_kind: str,
    condition: str,
) -> dict[str, object]:
    """候補行から変異種類と条件の指標を独立に集計する。"""

    selected = [
        record
        for record in records
        if _string(record, "mutation_kind") == mutation_kind
        and _string(record, "condition") == condition
        and not _boolean(record, "oracle_valid")
    ]
    unsafe_acceptance_count = sum(
        _boolean(record, "unsafe_acceptance") for record in selected
    )
    return {
        "mutation_kind": mutation_kind,
        "condition": condition,
        "candidate_count": len(selected),
        "template_count": len(
            {_string(record, "template_checksum") for record in selected}
        ),
        "unsafe_acceptance_count": unsafe_acceptance_count,
        "unsafe_acceptance_rate": _rate(unsafe_acceptance_count, len(selected)),
        "safe_rejection_count": sum(
            _boolean(record, "safe_rejection") for record in selected
        ),
        "localization_correct_count": sum(
            record.get("localization_correct") is True for record in selected
        ),
        "repair_success_count": sum(
            record.get("repair_success") is True for record in selected
        ),
    }


def _paired_difference(
    records: Sequence[Mapping[str, object]],
    expected: Mapping[str, object],
    seed: int,
) -> dict[str, object]:
    """候補行から条件間の率差とテンプレートブートストラップ区間を求める。"""

    metric = _string(expected, "metric")
    first = _string(expected, "first_condition")
    second = _string(expected, "second_condition")
    relevant = [
        record
        for record in records
        if _string(record, "condition") in (first, second)
        and (
            not _boolean(record, "oracle_valid")
            if metric == "unsafe_acceptance_rate"
            else _boolean(record, "oracle_valid")
        )
    ]
    by_condition = {
        condition: {
            _string(record, "candidate_id"): record
            for record in relevant
            if _string(record, "condition") == condition
        }
        for condition in (first, second)
    }
    candidate_ids = sorted(set(by_condition[first]) & set(by_condition[second]))
    templates = sorted(
        {
            _string(by_condition[first][candidate_id], "template_checksum")
            for candidate_id in candidate_ids
        }
    )
    by_template = {
        template: [
            candidate_id
            for candidate_id in candidate_ids
            if _string(by_condition[first][candidate_id], "template_checksum")
            == template
        ]
        for template in templates
    }
    observed = _rate_difference(
        candidate_ids,
        by_condition[first],
        by_condition[second],
        metric,
    )
    iterations = _integer(expected, "bootstrap_iterations")
    random_generator = random.Random(seed)
    bootstrap_values: list[float] = []
    for _ in range(iterations):
        sampled_ids = [
            candidate_id
            for sampled_template in (
                random_generator.choice(templates) for _ in templates
            )
            for candidate_id in by_template[sampled_template]
        ]
        bootstrap_values.append(
            _rate_difference(
                sampled_ids,
                by_condition[first],
                by_condition[second],
                metric,
            )
        )
    bootstrap_values.sort()
    return {
        "difference": observed,
        "confidence_interval_95": (
            _percentile(bootstrap_values, 0.025),
            _percentile(bootstrap_values, 0.975),
        ),
    }


def _rate_difference(
    candidate_ids: Sequence[str],
    first_records: Mapping[str, Mapping[str, object]],
    second_records: Mapping[str, Mapping[str, object]],
    metric: str,
) -> float:
    """同じ候補に対する二条件の率差を求める。"""

    if not candidate_ids:
        return 0.0
    key = "unsafe_acceptance" if metric == "unsafe_acceptance_rate" else "accepted"
    first_rate = sum(
        _boolean(first_records[candidate_id], key) for candidate_id in candidate_ids
    ) / len(candidate_ids)
    second_rate = sum(
        _boolean(second_records[candidate_id], key) for candidate_id in candidate_ids
    ) / len(candidate_ids)
    return first_rate - second_rate


def _graph_sidecar_mismatch_count(
    records: Sequence[Mapping[str, object]],
) -> int:
    """グラフ契約とサイドカー契約の判定不一致を数える。"""

    graph = {
        _string(record, "candidate_id"): _boolean(record, "accepted")
        for record in records
        if _string(record, "condition") == "graph_contract"
    }
    sidecar = {
        _string(record, "candidate_id"): _boolean(record, "accepted")
        for record in records
        if _string(record, "condition") == "sidecar_contract"
    }
    return sum(graph[item] != sidecar[item] for item in set(graph) & set(sidecar))


def _flatten_build_summary(
    build_summary: Mapping[str, object],
) -> tuple[dict[str, object], tuple[str, ...]]:
    """変異別の辞書を列へ展開した1行の集計を返す。"""

    row = {field: build_summary[field] for field in BUILD_SCALAR_FIELDS}
    dynamic_fields: list[str] = []
    for source_field, prefix in (
        ("pair_counts_by_mutation", "pair_count"),
        ("template_counts_by_mutation", "template_count"),
        ("construction_failure_counts", "construction_failure_count"),
    ):
        source = _object(build_summary, source_field)
        for mutation_kind in MUTATION_KINDS:
            field = f"{prefix}_{mutation_kind}"
            dynamic_fields.append(field)
            row[field] = _integer(source, mutation_kind)
    return row, (*BUILD_SCALAR_FIELDS, *dynamic_fields)


def _flatten_paired_difference(item: Mapping[str, object]) -> dict[str, object]:
    """95%区間を下限と上限の列へ分ける。"""

    interval = _number_list(item, "confidence_interval_95", length=2)
    return {
        "metric": _string(item, "metric"),
        "first_condition": _string(item, "first_condition"),
        "second_condition": _string(item, "second_condition"),
        "difference": _number(item, "difference"),
        "confidence_interval_95_lower": interval[0],
        "confidence_interval_95_upper": interval[1],
        "template_count": _integer(item, "template_count"),
        "bootstrap_iterations": _integer(item, "bootstrap_iterations"),
    }


def _tsv_payload(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> str:
    """行を安定したUTF-8 TSV文字列へ変換する。"""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _tsv_value(row[field]) for field in fieldnames})
    return stream.getvalue()


def _tsv_value(value: object) -> str:
    """JSON値を一つのTSVセルへ変換する。"""

    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, (str, int, float)):
        return str(value)
    raise ValueError(f"unsupported TSV value: {type(value).__name__}")


def _assert_metric_mapping(
    expected: Mapping[str, object],
    observed: Mapping[str, object],
    fields: Sequence[str],
) -> None:
    """集計行の整数、文字列、浮動小数点を照合する。"""

    for field in fields:
        expected_value = expected[field]
        observed_value = observed[field]
        if isinstance(expected_value, float):
            _assert_float(expected_value, cast(float, observed_value), field)
        elif expected_value != observed_value:
            raise ValueError(
                f"summary mismatch for {field}: "
                f"expected={expected_value}, observed={observed_value}"
            )


def _assert_float(expected: float, observed: float, label: str) -> None:
    """決定的な再集計結果を十分小さい誤差で照合する。"""

    if not math.isclose(expected, observed, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            f"summary mismatch for {label}: expected={expected}, observed={observed}"
        )


def _object(mapping: Mapping[str, object], key: str) -> dict[str, object]:
    """指定キーをJSONオブジェクトとして返す。"""

    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return cast(dict[str, object], value)


def _object_list(mapping: Mapping[str, object], key: str) -> list[dict[str, object]]:
    """指定キーをJSONオブジェクトの一覧として返す。"""

    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return cast(list[dict[str, object]], value)


def _number_list(
    mapping: Mapping[str, object],
    key: str,
    *,
    length: int,
) -> list[float]:
    """指定キーを固定長の数値一覧として返す。"""

    value = mapping.get(key)
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{key} must be a numeric list of length {length}")
    return [_number({key: item}, key) for item in value]


def _string(mapping: Mapping[str, object], key: str) -> str:
    """指定キーを文字列として返す。"""

    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _integer(mapping: Mapping[str, object], key: str) -> int:
    """指定キーを整数として返す。"""

    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _number(mapping: Mapping[str, object], key: str) -> float:
    """指定キーを数値として返す。"""

    value = mapping.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _boolean(mapping: Mapping[str, object], key: str) -> bool:
    """指定キーを真偽値として返す。"""

    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _percentile(values: Sequence[float], probability: float) -> float:
    """線形補間によるパーセンタイルを返す。"""

    if not values:
        return 0.0
    position = (len(values) - 1) * probability
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    return values[lower_index] * (1.0 - fraction) + values[upper_index] * fraction


def _rate(numerator: int, denominator: int) -> float:
    """分母が0なら0を返す割合を計算する。"""

    return numerator / denominator if denominator else 0.0
