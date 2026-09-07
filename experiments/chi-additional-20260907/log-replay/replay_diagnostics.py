"""保存済みの診断ログから受理・拒否だけを再構成する。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from interactive_ehr.evaluation.tracebench_ehr import (
    CandidateRunRecord,
    MutationKind,
    ValidationCondition,
)

LOGGER = logging.getLogger(__name__)
QUERY_CODE = "target_query_mismatch"
BINDING_CODE = "target_widget_connection_mismatch"
MetricRow = dict[str, str | int | float]


def checksum(path: Path) -> str:
    """入力全体のSHA-256を計算する。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict[str, object]:
    """JSONオブジェクトだけを読む。"""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path.name}")
    return cast(dict[str, object], value)


def string_mapping(value: object) -> dict[str, str]:
    """チェックサムの対応表に文字列以外がないことを確認する。"""
    if not isinstance(value, dict):
        raise ValueError("missing checksum object")
    result: dict[str, str] = {}
    for key, digest in cast(Mapping[object, object], value).items():
        if not isinstance(key, str) or not isinstance(digest, str):
            raise ValueError("invalid checksum entry")
        result[key] = digest
    return result


def verify_run(run_dir: Path, implementation_path: Path) -> dict[str, str]:
    """固定マニフェストと結果・検査実装を照合する。"""
    manifest = read_object(run_dir / "run_manifest.json")
    outputs = string_mapping(manifest["output_checksums"])
    implementations = string_mapping(manifest["implementation_checksums"])
    observed: dict[str, str] = {
        "run_manifest.json": checksum(run_dir / "run_manifest.json")
    }
    for filename, expected in outputs.items():
        if Path(filename).name != filename:
            raise ValueError("invalid source filename")
        actual = checksum(run_dir / filename)
        if actual != expected:
            raise ValueError(f"source checksum mismatch: {filename}")
        observed[filename] = actual
    if implementations.get("tracebench_ehr.py") != checksum(implementation_path):
        raise ValueError("validator implementation differs from the recorded version")
    return observed


def replay_conditions(
    graph_codes: frozenset[str], artifact_codes: frozenset[str]
) -> dict[str, frozenset[str]]:
    """事前に決めた九つの集合操作で、拒否の根拠を再構成する。"""
    if not artifact_codes.issubset(graph_codes):
        raise ValueError("artifact checks are not contained in graph checks")
    query = graph_codes & {QUERY_CODE}
    binding = graph_codes & {BINDING_CODE}
    annotations = frozenset(
        code for code in graph_codes if code.startswith("semantic_")
    )
    return {
        "full_graph": graph_codes,
        "query_only": query,
        "artifact_and_query": artifact_codes | query,
        "artifact_query_binding": artifact_codes | query | binding,
        "artifact_and_binding": artifact_codes | binding,
        "without_query_equality": graph_codes - query,
        "without_annotations": graph_codes - annotations,
        "without_query_and_annotations": graph_codes - query - annotations,
        "artifact_and_annotations": artifact_codes | annotations,
    }


def group_records(
    records: Sequence[CandidateRunRecord],
) -> list[dict[ValidationCondition, CandidateRunRecord]]:
    """欠落、重複、ラベルや判定の矛盾を拒否して同じ候補をまとめる。"""
    groups: dict[str, dict[ValidationCondition, CandidateRunRecord]] = defaultdict(dict)
    for record in records:
        group = groups[record.candidate_id]
        if record.condition in group:
            raise ValueError("duplicate candidate condition")
        if record.accepted != (not record.issue_codes):
            raise ValueError("acceptance and issue codes disagree")
        if record.expected_valid != record.oracle_valid:
            raise ValueError("candidate and reference labels disagree")
        group[record.condition] = record
    for group in groups.values():
        if set(group) != set(ValidationCondition):
            raise ValueError("missing candidate condition")
        identities = {
            (
                record.pair_id,
                record.template_checksum,
                record.mutation_kind,
                record.expected_valid,
            )
            for record in group.values()
        }
        if len(identities) != 1:
            raise ValueError("candidate identity differs across conditions")
    return [groups[key] for key in sorted(groups)]


def summarize(
    groups: Sequence[Mapping[ValidationCondition, CandidateRunRecord]], split: str
) -> list[MetricRow]:
    """条件と不整合の種類ごとに件数を集計する。"""
    rows: list[MetricRow] = []
    for mutation in ("all", *(kind.value for kind in MutationKind)):
        counts: dict[str, dict[str, int]] = {}
        for group in groups:
            graph = group[ValidationCondition.GRAPH_CONTRACT]
            if mutation != "all" and graph.mutation_kind.value != mutation:
                continue
            artifact = group[ValidationCondition.ARTIFACT_CONTRACTS]
            conditions = replay_conditions(
                frozenset(graph.issue_codes), frozenset(artifact.issue_codes)
            )
            for condition, issues in conditions.items():
                count = counts.setdefault(
                    condition,
                    {
                        "invalid_count": 0,
                        "leaked_count": 0,
                        "valid_count": 0,
                        "valid_accepted_count": 0,
                        "disagreement_with_full": 0,
                    },
                )
                accepted = not issues
                if graph.expected_valid:
                    count["valid_count"] += 1
                    count["valid_accepted_count"] += int(accepted)
                else:
                    count["invalid_count"] += 1
                    count["leaked_count"] += int(accepted)
                count["disagreement_with_full"] += int(accepted != graph.accepted)
        for condition, count in counts.items():
            if not count["invalid_count"] or not count["valid_count"]:
                raise ValueError("missing valid or invalid candidates")
            rows.append(
                {
                    "split": split,
                    "mutation_kind": mutation,
                    "condition": condition,
                    **count,
                    "leakage_rate": count["leaked_count"] / count["invalid_count"],
                    "valid_acceptance_rate": count["valid_accepted_count"]
                    / count["valid_count"],
                }
            )
    return rows


def write_json(path: Path, payload: object) -> None:
    """解析用JSONを人が読める形式で保存する。"""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_analysis(repository: Path, output: Path) -> None:
    """元結果を検証し、ローカルの新しい保存先へ再集計を書く。"""
    if output.exists():
        raise FileExistsError("output exists; refusing to overwrite")
    implementation = repository / "src/interactive_ehr/evaluation/tracebench_ehr.py"
    all_rows: list[MetricRow] = []
    input_checksums: dict[str, dict[str, str]] = {}
    for split in ("test", "validation"):
        run_dir = repository / "results/evaluation/tracebench_ehr_v1.1" / split
        input_checksums[split] = verify_run(run_dir, implementation)
        records = [
            CandidateRunRecord.model_validate_json(line)
            for line in (run_dir / "candidate_results.jsonl").read_text().splitlines()
        ]
        groups = group_records(records)
        manifest = read_object(run_dir / "run_manifest.json")
        if len(records) != manifest["candidate_run_count"]:
            raise ValueError("record count differs from manifest")
        if len(groups) != 2 * int(cast(int, manifest["pair_count"])):
            raise ValueError("candidate count differs from manifest")
        all_rows.extend(summarize(groups, split))
        LOGGER.info(
            "validated %s: %d records, %d candidates", split, len(records), len(groups)
        )
    output.mkdir(parents=True)
    write_json(output / "summary.json", all_rows)
    with (output / "diagnostic_replay.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(all_rows)
    write_json(
        output / "run_manifest.json",
        {
            "analysis": "posthoc_diagnostic_replay",
            "version": "1.0.0",
            "executed_at": datetime.now(UTC).isoformat(),
            "deterministic": True,
            "source_checksums": input_checksums,
            "validator_checksum": checksum(implementation),
            "analysis_checksum": checksum(Path(__file__)),
            "protocol_checksum": checksum(Path(__file__).with_name("PROTOCOL.md")),
            "output_checksums": {
                name: checksum(output / name)
                for name in ("summary.json", "diagnostic_replay.tsv")
            },
            "interpretation": "Acceptance-only replay; no validator rerun, repair, latency, or human outcome estimate.",
        },
    )


def main() -> int:
    """引数を確認して保存済みログの再集計を実行する。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run_analysis(args.repository.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
