"""Bounded, synthetic evaluation of actual model-generated data UI updates.

The checker consumes explicit task conditions, never a reference SQL string.
Audit labels use a separate SQL implementation on held-out database states.
Neither is a clinical oracle or a proof of SQL equivalence.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from interactive_ehr.widgets.display import DataframeSpec
from interactive_ehr.widgets.chart import LineChartSpec
from interactive_ehr.widgets.renderer import render_widget

END = "2026-09-08 12:00:00"
COLUMNS = ["observed_at", "value", "unit"]
SCHEMA = (
    "CREATE TABLE measurements (patient TEXT, measure TEXT, "
    "observed_at TEXT, value REAL, unit TEXT)"
)


class Query(BaseModel):
    """One named, read-only query in the generated artifact."""

    model_config = ConfigDict(extra="forbid")
    id: str
    sql: str


class Widget(BaseModel):
    """Small supported subset of the repository's real widget renderer."""

    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    kind: Literal["dataframe", "line_chart"]
    data_key: str
    columns: list[str]
    x: str | None = None
    y: str | None = None


class Interface(BaseModel):
    """Portable query and widget artifact generated in one model call."""

    model_config = ConfigDict(extra="forbid")
    queries: list[Query] = Field(min_length=1, max_length=6)
    widgets: list[Widget] = Field(min_length=1, max_length=6)


class Target(BaseModel):
    """Explicit technical requirements authored before generation."""

    patient: str = "SYN_A"
    measure: Literal["weight", "pulse"] = "weight"
    days: int = 1
    descending: bool = False
    limit: int | None = None
    grams: bool = False
    kind: Literal["dataframe", "line_chart"] = "dataframe"


class Case(BaseModel):
    """One independent request starting from the same synthetic interface."""

    id: str
    family: str
    request: str
    target: Target


def sha256(path: Path) -> str:
    """Return the byte checksum of an existing file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: Any) -> None:
    """Write readable JSON with stable key ordering and no NaN values."""
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def make_cases() -> list[Case]:
    """Fix 20 explicit requests without consulting any model output."""
    definitions: list[tuple[str, str, dict[str, Any]]] = [
        ("window", "体重を直近7日間に広げてください。", {"days": 7}),
        ("window", "体重を直近3日間に広げてください。", {"days": 3}),
        ("window", "体重を直近14日間に広げてください。", {"days": 14}),
        ("window", "体重を直近30日間に広げてください。", {"days": 30}),
        (
            "patient",
            "体重ウィジェットだけ患者SYN_Bへ切り替えてください。",
            {"patient": "SYN_B"},
        ),
        (
            "patient",
            "体重ウィジェットだけ患者SYN_Cへ切り替えてください。",
            {"patient": "SYN_C"},
        ),
        ("order", "体重を新しい日時から順に並べてください。", {"descending": True}),
        (
            "limit",
            "体重の最新1件だけを表示してください。",
            {"descending": True, "limit": 1},
        ),
        (
            "limit",
            "体重の最新3件までを、新しい順に表示してください。",
            {"descending": True, "limit": 3},
        ),
        (
            "unit",
            "体重をkgからgへ変換し、値と単位を合わせてください。",
            {"grams": True},
        ),
        (
            "measure",
            "主ウィジェットを体重から脈拍へ切り替えてください。",
            {"measure": "pulse"},
        ),
        (
            "visualization",
            "体重を折れ線グラフにしてください。横軸はobserved_at、縦軸はvalueです。",
            {"kind": "line_chart"},
        ),
        (
            "window_order",
            "体重を直近7日間に広げ、新しい順にしてください。",
            {"days": 7, "descending": True},
        ),
        (
            "window_order",
            "体重を直近14日間に広げ、新しい順にしてください。",
            {"days": 14, "descending": True},
        ),
        (
            "patient_window",
            "体重ウィジェットだけを患者SYN_Bの直近7日間にしてください。",
            {"patient": "SYN_B", "days": 7},
        ),
        (
            "patient_window",
            "体重ウィジェットだけを患者SYN_Cの直近3日間にしてください。",
            {"patient": "SYN_C", "days": 3},
        ),
        (
            "unit_window",
            "体重を直近7日間に広げ、kgからgへ値と単位を変換してください。",
            {"days": 7, "grams": True},
        ),
        (
            "unit_window",
            "体重を直近30日間に広げ、kgからgへ値と単位を変換してください。",
            {"days": 30, "grams": True},
        ),
        (
            "patient_measure",
            "主ウィジェットだけを患者SYN_Bの脈拍へ切り替えてください。",
            {"patient": "SYN_B", "measure": "pulse"},
        ),
        (
            "window_limit",
            "体重を直近7日間に広げ、最新3件までを新しい順に表示してください。",
            {"days": 7, "descending": True, "limit": 3},
        ),
    ]
    return [
        Case(
            id=f"update_{index:02d}",
            family=family,
            request=request,
            target=Target(**changes),
        )
        for index, (family, request, changes) in enumerate(definitions, start=1)
    ]


def make_rows(state: int) -> list[dict[str, Any]]:
    """Create synthetic boundaries, missing values and distractors deterministically."""
    offsets = [
        0,
        0.25,
        0.5,
        1,
        1 + 1 / 86400,
        2,
        3,
        3 + 1 / 86400,
        7,
        7 + 1 / 86400,
        14,
        14 + 1 / 86400,
        30,
        31,
        -1,
    ]
    rows: list[dict[str, Any]] = []
    end = datetime.fromisoformat(END)
    for person, patient in enumerate(["SYN_A", "SYN_B", "SYN_C"]):
        for measure in ["weight", "pulse"]:
            for index, offset in enumerate(offsets):
                if (
                    state in (1, 4)
                    and patient == "SYN_A"
                    and measure == "weight"
                    and 0 <= offset <= 1
                ):
                    continue
                value: float | None = 50 + person * 20 + index + state * 0.25
                if measure == "pulse":
                    value += 40
                if index == 5 and state % 2 == 0:
                    value = None
                rows.append(
                    {
                        "patient": patient,
                        "measure": measure,
                        "observed_at": (end - timedelta(days=offset)).isoformat(
                            sep=" "
                        ),
                        "value": value,
                        "unit": "kg" if measure == "weight" else "bpm",
                    }
                )
    return rows


def create_database(rows: list[dict[str, Any]], path: Path) -> None:
    """Build a new database solely from the synthetic fixture rows."""
    if path.exists():
        raise FileExistsError(path)
    with sqlite3.connect(path) as connection:
        connection.execute(SCHEMA)
        connection.executemany(
            "INSERT INTO measurements VALUES (:patient,:measure,:observed_at,:value,:unit)",
            rows,
        )


def _authorize(
    action: int,
    arg1: str | None,
    arg2: str | None,
    database: str | None,
    trigger: str | None,
) -> int:
    """Allow SELECT over measurements only, without external or write capabilities."""
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 == "measurements" else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in {
        "datetime",
        "date",
        "strftime",
        "julianday",
        "round",
        "coalesce",
        "ifnull",
        "cast",
        "min",
        "max",
        "abs",
        "iif",
        "typeof",
        "count",
        "sum",
        "avg",
    }:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def execute(sql: str, path: Path) -> tuple[list[str], list[list[Any]]]:
    """Execute one read-only query with a bounded SQLite instruction budget."""
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as connection:
        connection.set_authorizer(_authorize)
        steps = 0

        def progress() -> int:
            """Stop SQL exceeding one million virtual-machine instructions."""
            nonlocal steps
            steps += 1
            return int(steps > 1000)

        connection.set_progress_handler(progress, 1000)
        cursor = connection.execute(sql)
        columns = [str(item[0]) for item in cursor.description or []]
        rows = cursor.fetchmany(1001)
        if len(rows) > 1000:
            raise ValueError("result_row_budget")
        return columns, [list(row) for row in rows]


def reference_sql(target: Target) -> str:
    """Compile a target to SQL for the privileged baseline and held-out audit only."""
    start = (datetime.fromisoformat(END) - timedelta(days=target.days)).isoformat(
        sep=" "
    )
    value = "value * 1000.0" if target.grams else "value"
    unit = "'g'" if target.grams else "unit"
    limit = f" LIMIT {target.limit}" if target.limit is not None else ""
    order = "DESC" if target.descending else "ASC"
    return (
        f"SELECT observed_at, {value} AS value, {unit} AS unit FROM measurements "
        f"WHERE patient = '{target.patient}' AND measure = '{target.measure}' "
        f"AND observed_at >= '{start}' AND observed_at <= '{END}' "
        f"ORDER BY observed_at {order}{limit}"
    )


def expected_rows(target: Target, rows: list[dict[str, Any]]) -> list[list[Any]]:
    """Interpret an explicit request in Python without constructing or reading SQL."""
    end = datetime.fromisoformat(END)
    selected = [
        row
        for row in rows
        if row["patient"] == target.patient
        and row["measure"] == target.measure
        and 0
        <= (end - datetime.fromisoformat(row["observed_at"])).total_seconds()
        <= target.days * 86400
    ]
    selected.sort(key=lambda row: row["observed_at"], reverse=target.descending)
    if target.limit is not None:
        selected = selected[: target.limit]
    return [
        [
            row["observed_at"],
            row["value"] * 1000
            if target.grams and row["value"] is not None
            else row["value"],
            "g" if target.grams else row["unit"],
        ]
        for row in selected
    ]


def reference_interface(target: Target) -> Interface:
    """Construct initial state or privileged reference without model assistance."""
    return Interface(
        queries=[
            Query(id="main_data", sql=reference_sql(target)),
            Query(id="stable_data", sql=reference_sql(Target(measure="pulse"))),
        ],
        widgets=[
            Widget(
                id="main",
                title="主表示",
                kind=target.kind,
                data_key="main_data",
                columns=COLUMNS,
                x="observed_at" if target.kind == "line_chart" else None,
                y="value" if target.kind == "line_chart" else None,
            ),
            Widget(
                id="stable",
                title="保持する脈拍",
                kind="dataframe",
                data_key="stable_data",
                columns=COLUMNS,
            ),
        ],
    )


def build_prompt(case: Case) -> str:
    """Expose current artifact and request; withhold target contract and reference answer."""
    return f"""合成データだけを使う電子カルテ風のUI更新課題です。
以下の現在のUIを要求に沿って更新し、Interface JSONだけを返してください。
SQLはローカルSQLiteで実行し、widgetsを既存レンダラで表示します。

利用可能なスキーマ: {SCHEMA}
patientはSYN_A/SYN_B/SYN_C、measureはweightまたはpulseです。
weightのvalueはkg、pulseのvalueはbpmです。valueがNULLの場合は欠損のまま残します。
observed_atはYYYY-MM-DD HH:MM:SS形式のTEXTです。
基準日時は{END}です。直近N日間は、基準日時-N日以上、基準日時以下の両端を含む範囲です。
患者の実データや行の例は渡しません。取得結果の値をSQLへ埋め込まないでください。

明示されていない条件は現在のまま保持してください。stableウィジェットは常に変更対象外です。
main/stableとmain_data/stable_dataのID、対応関係は保持してください。
SQLは読み取り専用です。全クエリはobserved_at,value,unitをこの順で返してください。
dataframeはこの3列を表示します。line_chartはx=observed_at,y=valueとしcolumnsも3列を保持します。
新しい表示部品や補足文は追加しません。タイトルの言い換えは許容します。
現在のUI:
{reference_interface(Target()).model_dump_json(indent=2)}

更新要求:
{case.request}
"""


def _structure(artifact: Interface, database: Path) -> list[str]:
    """Check query execution, unique IDs, bindings and available display columns."""
    issues: list[str] = []
    queries = {query.id: query for query in artifact.queries}
    if len(queries) != len(artifact.queries) or len(
        {w.id for w in artifact.widgets}
    ) != len(artifact.widgets):
        issues.append("duplicate_id")
    columns: dict[str, list[str]] = {}
    for query in artifact.queries:
        try:
            columns[query.id] = execute(query.sql, database)[0]
        except (sqlite3.Error, ValueError):
            issues.append(f"query_execution:{query.id}")
    for widget in artifact.widgets:
        available = columns.get(widget.data_key)
        if available is None:
            issues.append(f"binding:{widget.id}")
        elif any(column not in available for column in widget.columns):
            issues.append(f"display_column:{widget.id}")
        elif widget.kind == "line_chart" and (
            widget.x not in available or widget.y not in available
        ):
            issues.append(f"chart_axis:{widget.id}")
    return issues


def _display_contract(artifact: Interface, target: Target) -> list[str]:
    """Compare declared display requirements without demanding title or SQL identity."""
    issues: list[str] = []
    if {q.id for q in artifact.queries} != {"main_data", "stable_data"}:
        issues.append("query_set")
    if [w.id for w in artifact.widgets] != ["main", "stable"]:
        issues.append("widget_set_or_order")
    for widget in artifact.widgets:
        kind = target.kind if widget.id == "main" else "dataframe"
        if widget.data_key != f"{widget.id}_data":
            issues.append(f"requested_binding:{widget.id}")
        if widget.columns != COLUMNS or widget.kind != kind:
            issues.append(f"requested_display:{widget.id}")
        if kind == "line_chart" and (widget.x != "observed_at" or widget.y != "value"):
            issues.append(f"requested_axes:{widget.id}")
    return issues


def check_contract(
    artifact: Interface, target: Target, inputs: Path, states: tuple[int, ...]
) -> list[str]:
    """Check display and Python-computed rows on visible synthetic states."""
    issues = _display_contract(artifact, target)
    for state in states:
        database = inputs / f"state_{state}.sqlite"
        issues.extend(_structure(artifact, database))
        rows = json.loads((inputs / f"state_{state}.json").read_text())
        for query in artifact.queries:
            spec = target if query.id == "main_data" else Target(measure="pulse")
            try:
                columns, actual = execute(query.sql, database)
                if columns != COLUMNS or actual != expected_rows(spec, rows):
                    issues.append(f"result_mismatch:{state}:{query.id}")
            except (sqlite3.Error, ValueError):
                issues.append(f"query_execution:{state}:{query.id}")
    return sorted(set(issues))


def audit_artifact(artifact: Interface, target: Target, inputs: Path) -> list[str]:
    """Use separately executed reference SQL on four withheld states as audit labels."""
    issues = _display_contract(artifact, target)
    for state in (3, 4, 5, 6):
        database = inputs / f"state_{state}.sqlite"
        issues.extend(_structure(artifact, database))
        for query in artifact.queries:
            spec = target if query.id == "main_data" else Target(measure="pulse")
            try:
                if execute(query.sql, database) != execute(
                    reference_sql(spec), database
                ):
                    issues.append(f"audit_result:{state}:{query.id}")
            except (sqlite3.Error, ValueError):
                issues.append(f"audit_execution:{state}:{query.id}")
    return sorted(set(issues))


def evaluate(case: Case, raw_text: str, inputs: Path) -> dict[str, Any]:
    """Retain malformed and rejected outputs in the common evaluation denominator."""
    try:
        artifact = Interface.model_validate_json(raw_text)
    except ValueError:
        return {
            "id": case.id,
            "family": case.family,
            "parse_ok": False,
            "audit_valid": False,
            "audit_issues": ["parse_error"],
            "accepted": {
                key: False
                for key in ("structure", "reference", "one_state", "three_states")
            },
            "issues": {"parse": ["parse_error"]},
        }
    structure = _structure(artifact, inputs / "state_0.sqlite")
    reference = reference_interface(case.target)

    def normalize(sql: str) -> str:
        """Normalize outer whitespace only, without altering literals or identifiers."""
        return sql.strip().removesuffix(";").strip()

    exact = {q.id: normalize(q.sql) for q in artifact.queries} == {
        q.id: normalize(q.sql) for q in reference.queries
    }
    reference_issues = structure + _display_contract(artifact, case.target)
    if not exact:
        reference_issues.append("reference_query_mismatch")
    issues = {
        "structure": structure,
        "reference": reference_issues,
        "one_state": check_contract(artifact, case.target, inputs, (0,)),
        "three_states": check_contract(artifact, case.target, inputs, (0, 1, 2)),
    }
    audit = audit_artifact(artifact, case.target, inputs)
    return {
        "id": case.id,
        "family": case.family,
        "parse_ok": True,
        "audit_valid": not audit,
        "audit_issues": audit,
        "accepted": {key: not value for key, value in issues.items()},
        "issues": issues,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Count diagnostic outcomes; avoid inferential claims from purposive small samples."""
    valid = sum(record["audit_valid"] for record in records)
    conditions = {}
    for condition in ("structure", "reference", "one_state", "three_states"):
        conditions[condition] = {
            "accepted": sum(record["accepted"][condition] for record in records),
            "invalid_accepted": sum(
                record["accepted"][condition] and not record["audit_valid"]
                for record in records
            ),
            "valid_rejected": sum(
                not record["accepted"][condition] and record["audit_valid"]
                for record in records
            ),
        }
    return {
        "n": len(records),
        "audit_valid": valid,
        "audit_invalid": len(records) - valid,
        "parse_errors": sum(not record["parse_ok"] for record in records),
        "families": dict(Counter(record["family"] for record in records)),
        "conditions": conditions,
    }


def prepare_inputs(output: Path) -> None:
    """Freeze all inputs before the model is called; never replace an existing run."""
    output.mkdir(parents=True, exist_ok=False)
    cases = make_cases()
    save_json(output / "cases.json", [case.model_dump() for case in cases])
    save_json(output / "response_schema.json", Interface.model_json_schema())
    for state in range(7):
        rows = make_rows(state)
        save_json(output / f"state_{state}.json", rows)
        create_database(rows, output / f"state_{state}.sqlite")
    for case in cases:
        (output / f"{case.id}.txt").write_text(build_prompt(case), encoding="utf-8")
    save_json(
        output / "input_manifest.json",
        {path.name: sha256(path) for path in sorted(output.iterdir())},
    )


def render_interface(artifact: Interface, database: Path) -> None:
    """Render actual evaluated SQL results through the repository's Streamlit renderer."""
    context: dict[str, pd.DataFrame] = {}
    for query in artifact.queries:
        columns, rows = execute(query.sql, database)
        context[query.id] = pd.DataFrame(rows, columns=columns)
    for widget in artifact.widgets:
        if widget.kind == "dataframe":
            render_widget(
                DataframeSpec(data_key=widget.data_key, column_order=widget.columns),
                context,
            )
        else:
            units = ", ".join(
                sorted(
                    str(value)
                    for value in context[widget.data_key]["unit"].dropna().unique()
                )
            )
            render_widget(
                LineChartSpec(
                    data_key=widget.data_key,
                    x=widget.x,
                    y=widget.y,
                    y_label=f"value ({units})",
                ),
                context,
            )
