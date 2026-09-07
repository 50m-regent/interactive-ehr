"""固定した検査器へSQLの別解と結果を変える候補を入力する追加評価。"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import re
import sqlite3
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlglot import exp, parse_one

from interactive_ehr.evaluation.ehrsql_feasibility import sha256_file, sha256_text
from interactive_ehr.evaluation.tracebench_ehr import (
    DataArtifact,
    MutationKind,
    TraceBenchError,
    TraceCandidate,
    TraceCase,
    TraceContract,
    TraceSplit,
    ValidationCondition,
    WidgetArtifact,
    _build_contract,
    _open_read_only_connection,
    execute_query_snapshot,
    is_answerable,
    load_trace_cases,
    load_tracebench_config,
    normalize_query,
    normalized_query_checksum,
    referenced_tables,
    verify_tracebench_inputs,
)

LOGGER = logging.getLogger(__name__)
TIMEOUT = 5.0
MAX_ROWS = 10_000
FROZEN_VALIDATOR = "dd70e0a38172cb625ac8f99d1b94fbe6ed817bb52187455a00dd996c517b1b3a"
TRANSFORMS = ("original", "whitespace", "wrapper", "invert_equality")


class QueryFailure(ValueError):
    """個票を出力せず実行失敗の理由を伝える。"""


@dataclass
class Observation:
    """SQL実行結果を比較中だけメモリへ保持する。"""

    columns: tuple[str, ...]
    rows: Counter[str]


@dataclass
class Record:
    """患者情報を含めず候補の状態と判定を記録する。"""

    case_checksum: str
    template_checksum: str
    transform: str
    status: str
    baseline_empty: bool | None = None
    transformed_empty: bool | None = None
    normalized_same: bool | None = None
    accepted: dict[str, bool] | None = None
    issues: dict[str, list[str]] | None = None


def observe(connection: sqlite3.Connection, query: str) -> Observation:
    """型と重複を保つ比較値を、既存のダイジェストを使わず作る。"""

    deadline = time.monotonic() + TIMEOUT

    def expired() -> int:
        """クエリの実行期限をSQLiteへ伝える。"""

        return int(time.monotonic() > deadline)

    connection.set_progress_handler(expired, 1_000)
    try:
        cursor = connection.execute(query)
        columns = tuple(str(column[0]) for column in cursor.description or ())
        rows = cursor.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error:
        reason = "timeout" if time.monotonic() > deadline else "sql_error"
        raise QueryFailure(reason) from None
    finally:
        connection.set_progress_handler(None, 0)
    if len(rows) > MAX_ROWS:
        raise QueryFailure("row_cap")
    if not columns:
        raise QueryFailure("no_columns")
    encoded = Counter(
        json.dumps([(type(cell).__name__, repr(cell)) for cell in row]) for row in rows
    )
    return Observation(columns=columns, rows=encoded)


def exclusion_reason(query: str) -> str | None:
    """実行前に固定した非決定性と構文の除外条件を確認する。"""

    try:
        normalized = normalize_query(query)
    except ValueError:
        return "not_read_only_or_parse_error"
    if re.search(
        r"\b(random|randomblob|changes|last_insert_rowid)\s*\("
        r"|\bcurrent_(date|time|timestamp)\b|['\"](now|localtime|utc)['\"]",
        normalized,
        re.IGNORECASE,
    ):
        return "nondeterministic_function"
    tree = parse_one(query, read="sqlite")
    if any(
        node.args.get("limit") is not None and node.args.get("order") is None
        for node in tree.find_all(exp.Select)
    ):
        return "limit_without_order"
    return None


def invert_equality(query: str) -> str | None:
    """WHERE内の最初の列と値の等号を、原文の他の部分を保ち反転する。"""

    tree = parse_one(query, read="sqlite")
    for node in tree.walk(bfs=False):
        if not isinstance(node, exp.EQ):
            continue
        parent = node.parent
        while parent is not None and not isinstance(parent, (exp.Where, exp.Select)):
            parent = parent.parent
        if not isinstance(parent, exp.Where):
            continue
        left, right = node.this, node.expression
        if not (
            isinstance(left, exp.Column)
            and isinstance(right, exp.Literal)
            or isinstance(left, exp.Literal)
            and isinstance(right, exp.Column)
        ):
            continue
        first = left.this if isinstance(left, exp.Column) else left
        second = right.this if isinstance(right, exp.Column) else right
        if "end" not in first.meta or "start" not in second.meta:
            continue
        start, stop = int(first.meta["end"]) + 1, int(second.meta["start"])
        gap = query[start:stop]
        if re.fullmatch(r"\s*=\s*", gap) is None:
            continue
        position = start + gap.index("=")
        transformed = query[:position] + "<>" + query[position + 1 :]
        before = Counter(item.sql() for item in tree.find_all(exp.Literal))
        after = Counter(
            item.sql()
            for item in parse_one(transformed, read="sqlite").find_all(exp.Literal)
        )
        if before != after:
            raise ValueError("literal preservation failed")
        return transformed
    return None


def transform_query(query: str, transform: str) -> str | None:
    """事前に固定した候補を一つだけ生成する。"""

    if transform == "original":
        return query
    if transform == "whitespace":
        return " \n" + query + "\n "
    if transform == "wrapper":
        return "SELECT * FROM (\n" + query.strip().removesuffix(";") + "\n) WHERE 1 = 1"
    if transform == "invert_equality":
        return invert_equality(query)
    raise ValueError("unknown transformation")


def baseline_candidate(
    case: TraceCase, connection: sqlite3.Connection
) -> tuple[TraceCandidate, TraceContract]:
    """既存の型と契約生成で基準を構成し、採用条件は追加しない。"""

    snapshot = execute_query_snapshot(
        connection, case.query, timeout_seconds=TIMEOUT, max_result_rows=MAX_ROWS
    )
    if snapshot.row_count_capped:
        raise QueryFailure("baseline_snapshot_row_cap")
    target = DataArtifact(
        node_id="target",
        query=case.query,
        provenance_tables=referenced_tables(case.query),
        result=snapshot,
    )
    source = target.model_copy(update={"node_id": "source"})
    widget = WidgetArtifact(
        widget_id="widget",
        data_node_id="target",
        field_checksums=snapshot.column_checksums,
        mapping=snapshot.widget_mapping,
    )
    pair_id = sha256_text(case.case_id)
    candidate = TraceCandidate(
        candidate_id=pair_id,
        pair_id=pair_id,
        template_checksum=sha256_text(case.template),
        # 型の必須項目。検査はこの注入種別とexpected_validを参照しない。
        mutation_kind=MutationKind.PATIENT,
        expected_valid=True,
        question_checksum=sha256_text(case.question),
        target_node_id="target",
        data_nodes={"source": source, "target": target},
        widget=widget,
    )
    contract = _build_contract(
        pair_id, target=case, source_node=source, target_node=target, widget=widget
    )
    return candidate, contract


def assess(
    candidate: TraceCandidate, contract: TraceContract
) -> tuple[dict[str, bool], dict[str, list[str]]]:
    """固定された4条件を実行し、3種類の診断除去を再構成する。"""

    from interactive_ehr.evaluation.tracebench_ehr import validate_candidate

    issues = {
        condition.value: [
            issue.code
            for issue in validate_candidate(candidate, contract, condition).issues
        ]
        for condition in ValidationCondition
    }
    graph = issues["graph_contract"]
    issues["without_query_equality"] = [
        c for c in graph if c != "target_query_mismatch"
    ]
    issues["without_annotations"] = [c for c in graph if not c.startswith("semantic_")]
    issues["without_query_and_annotations"] = [
        c
        for c in graph
        if c != "target_query_mismatch" and not c.startswith("semantic_")
    ]
    return {condition: not codes for condition, codes in issues.items()}, issues


def evaluate_case(case: TraceCase, connection: sqlite3.Connection) -> list[Record]:
    """一ケースの全変換を、失敗と除外を含めて記録する。"""

    records = [
        Record(sha256_text(case.case_id), sha256_text(case.template), t, "pending")
        for t in TRANSFORMS
    ]
    reason = exclusion_reason(case.query)
    if reason is not None:
        for record in records:
            record.status = "excluded_" + reason
        return records
    try:
        baseline = observe(connection, case.query)
        if baseline != observe(connection, case.query):
            raise QueryFailure("unstable_baseline")
        candidate, contract = baseline_candidate(case, connection)
    except (QueryFailure, TraceBenchError) as error:
        for record in records:
            record.status = "baseline_" + (
                str(error) if isinstance(error, QueryFailure) else "snapshot_failure"
            )
        return records
    accepted, _ = assess(candidate, contract)
    if not all(accepted.values()):
        raise ValueError("baseline rejected; investigate before resuming")
    for record in records:
        record.baseline_empty = not baseline.rows
        transformed = transform_query(case.query, record.transform)
        if transformed is None:
            record.status = "not_applicable"
            continue
        record.normalized_same = normalized_query_checksum(
            transformed
        ) == normalized_query_checksum(case.query)
        try:
            observed = observe(connection, transformed)
            snapshot = execute_query_snapshot(
                connection,
                transformed,
                timeout_seconds=TIMEOUT,
                max_result_rows=MAX_ROWS,
            )
            if snapshot.row_count_capped:
                raise QueryFailure("snapshot_row_cap")
        except (QueryFailure, TraceBenchError) as error:
            record.status = "transform_" + (
                str(error) if isinstance(error, QueryFailure) else "snapshot_failure"
            )
            continue
        record.transformed_empty = not observed.rows
        node = candidate.data_nodes["target"].model_copy(
            update={
                "query": transformed,
                "result": snapshot,
                "provenance_tables": referenced_tables(transformed),
            }
        )
        changed = candidate.model_copy(
            update={"data_nodes": {**candidate.data_nodes, "target": node}}
        )
        record.accepted, record.issues = assess(changed, contract)
        if baseline.columns != observed.columns:
            record.status = "schema_changed"
        elif record.transform == "invert_equality":
            record.status = (
                "unchanged_result"
                if baseline.rows == observed.rows
                else "changed_result"
            )
        else:
            record.status = (
                "equivalent_result"
                if baseline.rows == observed.rows
                else "unexpected_result_change"
            )
    return records


def summarize(records: list[Record]) -> dict[str, dict[str, object]]:
    """変換・正解判定・検査条件別に分母を保持して集計する。"""

    groups: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        groups[record.transform].append(record)
    summary: dict[str, dict[str, object]] = {}
    for transform, items in groups.items():
        evaluated = [
            r for r in items if r.status in ("equivalent_result", "changed_result")
        ]
        conditions = sorted({c for r in evaluated for c in r.accepted or {}})
        summary[transform] = {
            "attempted": len(items),
            "statuses": dict(sorted(Counter(r.status for r in items).items())),
            "evaluated": len(evaluated),
            "evaluated_templates": len({r.template_checksum for r in evaluated}),
            "baseline_empty": sum(r.baseline_empty is True for r in evaluated),
            "transformed_empty": sum(r.transformed_empty is True for r in evaluated),
            "normalized_same": sum(r.normalized_same is True for r in evaluated),
            "accepted": {
                c: sum(bool(r.accepted and r.accepted[c]) for r in evaluated)
                for c in conditions
            },
            "issues": {
                c: dict(
                    sorted(
                        Counter(
                            code
                            for r in evaluated
                            for code in (r.issues or {}).get(c, [])
                        ).items()
                    )
                )
                for c in conditions
            },
        }
    return summary


def main() -> None:
    """入力版を検証して一度実行し、原データを含まない結果を保存する。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repository = Path(__file__).resolve().parents[3]
    config_path = repository / "data/evaluation/tracebench_ehr.v1.json"
    config = load_tracebench_config(config_path)
    validator = Path(__file__).with_name("tracebench_ehr.py")
    if sha256_file(validator) != FROZEN_VALIDATOR:
        raise ValueError("frozen validator checksum mismatch")
    dataset: Path = args.dataset
    annotated = dataset / "test/annotated.json"
    data = dataset / "test/data.json"
    database = dataset / "mimic_iv.sqlite"
    verify_tracebench_inputs(
        config,
        split=TraceSplit.TEST,
        annotated_path=annotated,
        dataset_data_path=data,
        database_path=database,
    )
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    cases = [
        case
        for case in load_trace_cases(annotated, split=TraceSplit.TEST)
        if is_answerable(case)
    ]
    records: list[Record] = []
    connection = _open_read_only_connection(database)
    try:
        for index, case in enumerate(cases, 1):
            if time.monotonic() - started > 1800:
                raise TimeoutError("overall 30 minute limit exceeded")
            records.extend(evaluate_case(case, connection))
            if index % 100 == 0:
                LOGGER.info("Completed %d/%d cases", index, len(cases))
    finally:
        connection.close()
    summary = summarize(records)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "candidate_records.jsonl").write_text(
        "".join(json.dumps(asdict(record), sort_keys=True) + "\n" for record in records)
    )
    protocol = repository / "experiments/chi-additional-20260907/PROTOCOL.md"
    manifest = {
        "analysis": "exploratory_sql_stress",
        "version": "1.0.0",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": time.monotonic() - started,
        "dataset_commit": config.dataset_commit,
        "split": "test",
        "answerable_cases": len(cases),
        "timeout_seconds": TIMEOUT,
        "max_result_rows": MAX_ROWS,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip(),
        "input_checksums": {
            "annotated.json": sha256_file(annotated),
            "data.json": sha256_file(data),
            "database": sha256_file(database),
        },
        "implementation_checksums": {
            "validator": sha256_file(validator),
            "analysis": sha256_file(Path(__file__)),
            "protocol": sha256_file(protocol),
            "uv.lock": sha256_file(repository / "uv.lock"),
        },
        "output_checksums": {
            name: sha256_file(output / name)
            for name in ("summary.json", "candidate_records.jsonl")
        },
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    LOGGER.info("Saved %d records; %d answerable cases", len(records), len(cases))


if __name__ == "__main__":
    main()
