"""EHRSQL-2024を用いたTraceBench-EHR実行可能性確認。"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sqlite3
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.scenario_graph import (
    DataNode,
    ScenarioGraph,
    TaskNode,
    WidgetNode,
)
from interactive_ehr.widgets import DataframeSpec, MetricSpec

DEFAULT_SAMPLE_SEED = 20260827
DEFAULT_SAMPLE_SIZE = 50
DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_RESULT_ROWS = 10_000

_READ_QUERY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_SQLITE_WRITE_ACTION_NAMES = (
    "SQLITE_ALTER_TABLE",
    "SQLITE_ANALYZE",
    "SQLITE_ATTACH",
    "SQLITE_CREATE_INDEX",
    "SQLITE_CREATE_TABLE",
    "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER",
    "SQLITE_CREATE_TEMP_VIEW",
    "SQLITE_CREATE_TRIGGER",
    "SQLITE_CREATE_VIEW",
    "SQLITE_CREATE_VTABLE",
    "SQLITE_DELETE",
    "SQLITE_DETACH",
    "SQLITE_DROP_INDEX",
    "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX",
    "SQLITE_DROP_TEMP_TABLE",
    "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER",
    "SQLITE_DROP_VIEW",
    "SQLITE_DROP_VTABLE",
    "SQLITE_INSERT",
    "SQLITE_PRAGMA",
    "SQLITE_REINDEX",
    "SQLITE_SAVEPOINT",
    "SQLITE_TRANSACTION",
    "SQLITE_UPDATE",
)
_SQLITE_WRITE_ACTIONS = frozenset(
    getattr(sqlite3, name)
    for name in _SQLITE_WRITE_ACTION_NAMES
    if hasattr(sqlite3, name)
)


class EhrsqlFeasibilityError(ValueError):
    """EHRSQL実行可能性確認の入力または実行条件が不正であることを示す。"""


class QueryOutcome(str, Enum):
    """正解SQLの実行結果。"""

    SUCCESS = "success"
    REJECTED_NOT_READ_ONLY = "rejected_not_read_only"
    TIMEOUT = "timeout"
    SQL_ERROR = "sql_error"
    GRAPH_ERROR = "graph_error"


class WidgetMapping(str, Enum):
    """SQL結果から決定的に選ぶWidget種別。"""

    METRIC = "metric"
    DATAFRAME = "dataframe"


class EhrsqlCase(BaseModel):
    """EHRSQL-2024の質問、正解SQL、テンプレートを保持する。"""

    model_config = ConfigDict(frozen=True)

    case_id: str
    split: str
    question: str
    query: str
    template: str

    @property
    def is_answerable(self) -> bool:
        """正解SQLを持つ回答可能ケースか返す。"""

        return self.query.strip().lower() != "null"


class SelectedCaseRecord(BaseModel):
    """個票の内容を含めずに選定ケースを記録する。"""

    model_config = ConfigDict(frozen=True)

    case_id: str
    split: str
    query_checksum: str
    template_checksum: str


class EhrsqlCaseResult(BaseModel):
    """患者単位の値を含まないケース別実行結果。"""

    model_config = ConfigDict(frozen=True)

    case_id: str
    split: str
    query_checksum: str
    template_checksum: str
    outcome: QueryOutcome
    execution_seconds: float = Field(ge=0.0)
    column_names: list[str] = Field(default_factory=list)
    observed_row_count: int | None = Field(default=None, ge=0)
    row_count_capped: bool = False
    non_empty_result: bool = False
    widget_mapping: WidgetMapping | None = None
    graph_valid: bool = False
    graph_checksum: str | None = None


class EhrsqlFeasibilitySummary(BaseModel):
    """50件の実行可能性確認を集計した結果。"""

    model_config = ConfigDict(frozen=True)

    selected_case_count: int = Field(ge=0)
    unique_template_count: int = Field(ge=0)
    execution_success_count: int = Field(ge=0)
    execution_success_rate: float = Field(ge=0.0, le=1.0)
    non_empty_result_count: int = Field(ge=0)
    non_empty_result_rate: float = Field(ge=0.0, le=1.0)
    graph_valid_count: int = Field(ge=0)
    graph_valid_rate: float = Field(ge=0.0, le=1.0)
    metric_mapping_count: int = Field(ge=0)
    dataframe_mapping_count: int = Field(ge=0)
    outcome_counts: dict[str, int]


class EhrsqlRunManifest(BaseModel):
    """入力版、コード版、実行条件、出力チェックサムを保持する。"""

    model_config = ConfigDict(frozen=True)

    experiment_id: str = "tracebench-ehr-feasibility"
    experiment_version: str = "0.1.0"
    executed_at: str
    dataset_repository: str
    dataset_commit: str
    dataset_split: str
    dataset_version: str
    code_commit: str
    sample_seed: int
    sample_size: int
    query_timeout_seconds: float
    max_result_rows: int
    python_version: str
    platform: str
    input_checksums: dict[str, str]
    implementation_checksums: dict[str, str]
    output_checksums: dict[str, str]


def sha256_text(value: str) -> str:
    """文字列のSHA-256を16進文字列で返す。"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """ファイルのSHA-256をメモリへ全読み込みせずに返す。"""

    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ehrsql_cases(annotated_path: Path, *, split: str) -> list[EhrsqlCase]:
    """EHRSQL-2024のannotated.jsonを読み、重複IDを検査する。"""

    raw_cases = json.loads(annotated_path.read_text(encoding="utf-8"))
    if not isinstance(raw_cases, list):
        raise EhrsqlFeasibilityError("annotated data must be a JSON array")

    cases: list[EhrsqlCase] = []
    seen_case_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise EhrsqlFeasibilityError("each annotated case must be an object")
        case = EhrsqlCase(
            case_id=str(raw_case.get("id", "")),
            split=split,
            question=str(raw_case.get("question", "")),
            query=str(raw_case.get("query", "")),
            template=str(raw_case.get("template", "")),
        )
        if not case.case_id or not case.question or not case.query or not case.template:
            raise EhrsqlFeasibilityError("annotated case has an empty required field")
        if case.case_id in seen_case_ids:
            raise EhrsqlFeasibilityError(f"duplicate case id: {case.case_id}")
        seen_case_ids.add(case.case_id)
        cases.append(case)
    return cases


def select_ehrsql_cases(
    cases: Sequence[EhrsqlCase],
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = DEFAULT_SAMPLE_SEED,
) -> list[EhrsqlCase]:
    """テンプレートの重複を避けながら回答可能ケースを決定的に選ぶ。"""

    if sample_size <= 0:
        raise EhrsqlFeasibilityError("sample_size must be positive")

    answerable_cases = [case for case in cases if case.is_answerable]
    if sample_size > len(answerable_cases):
        raise EhrsqlFeasibilityError(
            f"requested {sample_size} cases from {len(answerable_cases)} answerable cases"
        )

    cases_by_template: dict[str, list[EhrsqlCase]] = defaultdict(list)
    for case in answerable_cases:
        cases_by_template[case.template].append(case)

    representatives = [
        min(
            template_cases,
            key=lambda case: _stable_selection_key(seed, case.case_id),
        )
        for template_cases in cases_by_template.values()
    ]
    representatives.sort(key=lambda case: _stable_selection_key(seed, case.template))
    selected = representatives[:sample_size]

    if len(selected) < sample_size:
        selected_ids = {case.case_id for case in selected}
        remaining = sorted(
            (case for case in answerable_cases if case.case_id not in selected_ids),
            key=lambda case: _stable_selection_key(seed, case.case_id),
        )
        selected.extend(remaining[: sample_size - len(selected)])

    return selected


def selected_case_record(case: EhrsqlCase) -> SelectedCaseRecord:
    """EHRSQLケースから内容を含まない選定記録を作る。"""

    return SelectedCaseRecord(
        case_id=case.case_id,
        split=case.split,
        query_checksum=sha256_text(case.query),
        template_checksum=sha256_text(case.template),
    )


def validate_read_only_query(query: str) -> None:
    """単一のSELECTまたはWITH文だけを許可する。"""

    stripped_query = query.strip()
    if stripped_query.endswith(";"):
        stripped_query = stripped_query[:-1].rstrip()
    if not stripped_query or ";" in stripped_query:
        raise EhrsqlFeasibilityError("query must contain one SQL statement")
    if _READ_QUERY_PATTERN.match(stripped_query) is None:
        raise EhrsqlFeasibilityError("query must start with SELECT or WITH")


def run_ehrsql_feasibility(
    cases: Sequence[EhrsqlCase],
    *,
    database_path: Path,
    query_timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
    max_result_rows: int = DEFAULT_MAX_RESULT_ROWS,
) -> list[EhrsqlCaseResult]:
    """正解SQLを読み取り専用で実行し、値を保存せず変換可否を返す。"""

    if query_timeout_seconds <= 0:
        raise EhrsqlFeasibilityError("query_timeout_seconds must be positive")
    if max_result_rows <= 0:
        raise EhrsqlFeasibilityError("max_result_rows must be positive")

    connection = _open_read_only_connection(database_path)
    try:
        return [
            _run_case(
                case,
                connection=connection,
                query_timeout_seconds=query_timeout_seconds,
                max_result_rows=max_result_rows,
            )
            for case in cases
        ]
    finally:
        connection.close()


def summarize_feasibility(
    cases: Sequence[EhrsqlCase],
    results: Sequence[EhrsqlCaseResult],
) -> EhrsqlFeasibilitySummary:
    """ケース別結果から主要評価を集計する。"""

    if len(cases) != len(results):
        raise EhrsqlFeasibilityError("cases and results must have the same length")

    selected_count = len(results)
    success_count = sum(result.outcome == QueryOutcome.SUCCESS for result in results)
    non_empty_count = sum(result.non_empty_result for result in results)
    graph_valid_count = sum(result.graph_valid for result in results)
    metric_count = sum(
        result.widget_mapping == WidgetMapping.METRIC for result in results
    )
    dataframe_count = sum(
        result.widget_mapping == WidgetMapping.DATAFRAME for result in results
    )
    outcome_counts = {
        outcome.value: sum(result.outcome == outcome for result in results)
        for outcome in QueryOutcome
    }
    return EhrsqlFeasibilitySummary(
        selected_case_count=selected_count,
        unique_template_count=len({case.template for case in cases}),
        execution_success_count=success_count,
        execution_success_rate=_safe_rate(success_count, selected_count),
        non_empty_result_count=non_empty_count,
        non_empty_result_rate=_safe_rate(non_empty_count, selected_count),
        graph_valid_count=graph_valid_count,
        graph_valid_rate=_safe_rate(graph_valid_count, selected_count),
        metric_mapping_count=metric_count,
        dataframe_mapping_count=dataframe_count,
        outcome_counts=outcome_counts,
    )


def write_feasibility_outputs(
    *,
    output_dir: Path,
    cases: Sequence[EhrsqlCase],
    results: Sequence[EhrsqlCaseResult],
    annotated_path: Path,
    dataset_data_path: Path,
    database_path: Path,
    dataset_repository: str,
    dataset_commit: str,
    dataset_version: str,
    code_commit: str,
    sample_seed: int,
    query_timeout_seconds: float,
    max_result_rows: int,
    implementation_paths: Sequence[Path],
) -> EhrsqlRunManifest:
    """個票値を除いた結果、集計、レポート、実行マニフェストを書く。"""

    if len(cases) != len(results):
        raise EhrsqlFeasibilityError("cases and results must have the same length")
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_path = output_dir / "selected_cases.json"
    results_path = output_dir / "case_results.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"
    manifest_path = output_dir / "run_manifest.json"

    selected_records = [
        selected_case_record(case).model_dump(mode="json") for case in cases
    ]
    _write_json(selected_path, selected_records)
    _write_json_lines(
        results_path,
        [result.model_dump(mode="json") for result in results],
    )

    summary = summarize_feasibility(cases, results)
    _write_json(summary_path, summary.model_dump(mode="json"))
    report_path.write_text(_build_report(summary), encoding="utf-8")

    output_checksums = {
        path.name: sha256_file(path)
        for path in (selected_path, results_path, summary_path, report_path)
    }
    manifest = EhrsqlRunManifest(
        executed_at=datetime.now(timezone.utc).isoformat(),
        dataset_repository=dataset_repository,
        dataset_commit=dataset_commit,
        dataset_split=cases[0].split if cases else "unknown",
        dataset_version=dataset_version,
        code_commit=code_commit,
        sample_seed=sample_seed,
        sample_size=len(cases),
        query_timeout_seconds=query_timeout_seconds,
        max_result_rows=max_result_rows,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        input_checksums={
            "annotated.json": sha256_file(annotated_path),
            "data.json": sha256_file(dataset_data_path),
            "mimic_iv.sqlite": sha256_file(database_path),
        },
        implementation_checksums={
            path.name: sha256_file(path) for path in implementation_paths
        },
        output_checksums=output_checksums,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    return manifest


def read_dataset_version(data_path: Path) -> str:
    """EHRSQL-2024のdata.jsonから版を読む。"""

    raw_data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("version"), str):
        raise EhrsqlFeasibilityError("data.json does not contain a version")
    return raw_data["version"]


def _stable_selection_key(seed: int, value: str) -> str:
    """seedと文字列から決定的な並び順を作る。"""

    return sha256_text(f"{seed}:{value}")


def _open_read_only_connection(database_path: Path) -> sqlite3.Connection:
    """SQLiteをファイル読み取り専用かつquery_onlyで開く。"""

    resolved_path = database_path.resolve()
    if not resolved_path.is_file():
        raise EhrsqlFeasibilityError(f"database does not exist: {database_path}")
    database_uri = f"{resolved_path.as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(database_uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    connection.set_authorizer(_sqlite_authorizer)
    return connection


def _sqlite_authorizer(
    action_code: int,
    _argument_one: str | None,
    _argument_two: str | None,
    _database_name: str | None,
    _trigger_name: str | None,
) -> int:
    """SQLiteの書き込み、DDL、PRAGMA、トランザクションを拒否する。"""

    if action_code in _SQLITE_WRITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _run_case(
    case: EhrsqlCase,
    *,
    connection: sqlite3.Connection,
    query_timeout_seconds: float,
    max_result_rows: int,
) -> EhrsqlCaseResult:
    """1件のSQLを実行し、結果値を破棄して形状とグラフ妥当性を返す。"""

    started_at = time.monotonic()
    try:
        validate_read_only_query(case.query)
    except EhrsqlFeasibilityError:
        return _failed_result(
            case,
            outcome=QueryOutcome.REJECTED_NOT_READ_ONLY,
            started_at=started_at,
        )

    deadline = time.monotonic() + query_timeout_seconds

    def progress_handler() -> int:
        """期限を超えたSQLite実行を停止する。"""

        return int(time.monotonic() > deadline)

    connection.set_progress_handler(progress_handler, 1_000)
    try:
        cursor = connection.execute(case.query)
        column_names = [str(description[0]) for description in cursor.description or []]
        rows = cursor.fetchmany(max_result_rows + 1)
    except sqlite3.OperationalError as error:
        outcome = (
            QueryOutcome.TIMEOUT
            if "interrupted" in str(error).lower()
            else QueryOutcome.SQL_ERROR
        )
        return _failed_result(case, outcome=outcome, started_at=started_at)
    except sqlite3.Error:
        return _failed_result(
            case,
            outcome=QueryOutcome.SQL_ERROR,
            started_at=started_at,
        )
    finally:
        connection.set_progress_handler(None, 0)

    row_count_capped = len(rows) > max_result_rows
    observed_rows = rows[:max_result_rows]
    widget_mapping = _choose_widget_mapping(column_names, len(observed_rows))
    record = selected_case_record(case)
    try:
        graph = _build_feasibility_graph(
            case,
            column_names=column_names,
            widget_mapping=widget_mapping,
        )
        canonical_graph = json.dumps(
            graph.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        ScenarioGraph.model_validate_json(canonical_graph)
    except Exception:
        return EhrsqlCaseResult(
            case_id=record.case_id,
            split=record.split,
            query_checksum=record.query_checksum,
            template_checksum=record.template_checksum,
            outcome=QueryOutcome.GRAPH_ERROR,
            execution_seconds=time.monotonic() - started_at,
            column_names=column_names,
            observed_row_count=len(observed_rows),
            row_count_capped=row_count_capped,
            non_empty_result=bool(observed_rows),
            widget_mapping=widget_mapping,
            graph_valid=False,
        )

    return EhrsqlCaseResult(
        case_id=record.case_id,
        split=record.split,
        query_checksum=record.query_checksum,
        template_checksum=record.template_checksum,
        outcome=QueryOutcome.SUCCESS,
        execution_seconds=time.monotonic() - started_at,
        column_names=column_names,
        observed_row_count=len(observed_rows),
        row_count_capped=row_count_capped,
        non_empty_result=bool(observed_rows),
        widget_mapping=widget_mapping,
        graph_valid=True,
        graph_checksum=sha256_text(canonical_graph),
    )


def _failed_result(
    case: EhrsqlCase,
    *,
    outcome: QueryOutcome,
    started_at: float,
) -> EhrsqlCaseResult:
    """内容を含まない失敗結果を作る。"""

    record = selected_case_record(case)
    return EhrsqlCaseResult(
        case_id=record.case_id,
        split=record.split,
        query_checksum=record.query_checksum,
        template_checksum=record.template_checksum,
        outcome=outcome,
        execution_seconds=time.monotonic() - started_at,
    )


def _choose_widget_mapping(
    column_names: Sequence[str],
    observed_row_count: int,
) -> WidgetMapping:
    """単一値はMetric、それ以外はDataframeへ決定的に割り当てる。"""

    if len(column_names) == 1 and observed_row_count <= 1:
        return WidgetMapping.METRIC
    return WidgetMapping.DATAFRAME


def _build_feasibility_graph(
    case: EhrsqlCase,
    *,
    column_names: Sequence[str],
    widget_mapping: WidgetMapping,
) -> ScenarioGraph:
    """質問、SQL、結果列から最小のScenarioGraphを構築する。"""

    case_key = case.case_id.lower()
    context_key = f"ehrsql_{case_key}"
    data_node = DataNode(
        id=f"data_{case_key}",
        context_key=context_key,
        model_name=None,
        data_type="scalar" if widget_mapping == WidgetMapping.METRIC else "table",
        description="EHRSQL-2024 gold SQL result",
        primary_fields=list(column_names),
        sql=case.query,
    )
    if widget_mapping == WidgetMapping.METRIC:
        label = column_names[0] if column_names else "result"
        widget = MetricSpec(label=label, value_key=context_key)
    else:
        widget = DataframeSpec(
            data_key=context_key,
            column_order=list(column_names) or None,
        )
    widget_node = WidgetNode(
        id=f"widget_{case_key}",
        title="EHRSQL result",
        widget=widget,
        data_nodes=[data_node],
    )
    task_node = TaskNode(
        id=f"task_{case_key}",
        title=case.question,
        description="EHRSQL-2024 feasibility case",
        order=0,
        widgets=[widget_node],
    )
    return ScenarioGraph(
        id=f"scenario_{case_key}",
        title="TraceBench-EHR feasibility",
        description="Deterministic mapping from EHRSQL-2024",
        tasks=[task_node],
    )


def _safe_rate(numerator: int, denominator: int) -> float:
    """分母が0なら0.0を返す比率計算。"""

    return numerator / denominator if denominator else 0.0


def _write_json(path: Path, value: object) -> None:
    """JSONをキー順固定、UTF-8、末尾改行付きで書く。"""

    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_json_lines(path: Path, values: Sequence[Mapping[str, object]]) -> None:
    """1行1JSONで値を書き、順序を入力順のまま保つ。"""

    lines = [
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for value in values
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_report(summary: EhrsqlFeasibilitySummary) -> str:
    """患者単位の値を含まないMarkdown結果要約を作る。"""

    outcome_lines = "\n".join(
        f"- {outcome}: {count}件"
        for outcome, count in summary.outcome_counts.items()
        if count
    )
    return (
        "# TraceBench-EHR EHRSQL 50件実行可能性確認 v0.1\n\n"
        "## 解釈の範囲\n\n"
        "EHRSQL-2024と匿名化済みMIMIC-IV Demo v2.2を用いた技術的な確認です。"
        "臨床上の安全性、使いやすさ、他施設への一般化は評価していません。\n\n"
        "## 選定\n\n"
        f"- 選定ケース: {summary.selected_case_count}件\n"
        f"- 異なる質問テンプレート: {summary.unique_template_count}件\n\n"
        "## 主要結果\n\n"
        f"- 正解SQL実行成功: {summary.execution_success_count}/"
        f"{summary.selected_case_count}件 "
        f"({summary.execution_success_rate:.1%})\n"
        f"- 非空結果取得: {summary.non_empty_result_count}/"
        f"{summary.selected_case_count}件 "
        f"({summary.non_empty_result_rate:.1%})\n"
        f"- ScenarioGraph検証成功: {summary.graph_valid_count}/"
        f"{summary.selected_case_count}件 "
        f"({summary.graph_valid_rate:.1%})\n"
        f"- Metric割当: {summary.metric_mapping_count}件\n"
        f"- Dataframe割当: {summary.dataframe_mapping_count}件\n\n"
        "## 実行結果の分類\n\n"
        f"{outcome_lines}\n\n"
        "## データ管理\n\n"
        "生データ、質問文、正解SQL、患者単位の結果値は成果物へ保存していません。"
        "ケースID、チェックサム、結果形状、実行成否だけを記録しています。\n"
    )
