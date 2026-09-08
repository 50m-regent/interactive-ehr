"""Frozen synthetic sequences for the application's actual incremental updater.

All checkers receive the same explicit targets. Python execution expectations and
held-out SQL audit share those authored targets, so neither is independent human
ground truth or a general SQL equivalence proof.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Literal, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict
import sqlglot
from sqlglot import exp

from interactive_ehr.evaluation.generated_update_pilot import (
    COLUMNS,
    END,
    SCHEMA,
    Target,
    create_database,
    execute,
    expected_rows,
    make_rows,
    reference_sql,
    save_json,
    sha256,
)
from interactive_ehr.models import DwhBaseModel
from interactive_ehr.scenario_graph import DataNode, ScenarioGraph, TaskNode, WidgetNode
from interactive_ehr.widgets.display import DataframeSpec


class SyntheticMeasurements(DwhBaseModel):
    """Synthetic fixture schema registered only inside the experiment process."""

    patient: str
    measure: str
    observed_at: str
    value: float | None
    unit: str


class SequentialTarget(Target):
    """Cumulative requested state, including aggregates and visible columns."""

    aggregate: Literal["rows", "average", "count"] = "rows"


class Step(BaseModel):
    """One sequential request with its authored cumulative target."""

    model_config = ConfigDict(extra="forbid")
    id: str
    sequence: str
    index: int
    request: str
    target: SequentialTarget


def make_steps() -> list[Step]:
    """Author six three-step sequences without inspecting their generated outputs."""
    sequences: list[tuple[str, list[tuple[str, dict[str, Any]]]]] = [
        (
            "window_latest_unit",
            [
                ("主表示を直近7日間に広げてください。", {"days": 7}),
                (
                    "主表示の最新3件までを新しい順に表示してください。",
                    {"limit": 3, "descending": True},
                ),
                (
                    "主表示をkgからgに変換し、値と単位を合わせてください。",
                    {"grams": True},
                ),
            ],
        ),
        (
            "patient_window_latest",
            [
                ("主表示だけを患者SYN_Bへ切り替えてください。", {"patient": "SYN_B"}),
                ("主表示を直近3日間に広げてください。", {"days": 3}),
                (
                    "主表示の最新1件だけを新しい順に表示してください。",
                    {"limit": 1, "descending": True},
                ),
            ],
        ),
        (
            "average_patient_unit",
            [
                (
                    "主表示を直近7日間の体重の平均値にしてください。NULLは除外し、対象がなければNULLとします。表はvalue,unitの2列です。",
                    {"days": 7, "aggregate": "average"},
                ),
                ("主表示だけを患者SYN_Cへ切り替えてください。", {"patient": "SYN_C"}),
                (
                    "主表示をkgからgに変換し、値と単位を合わせてください。",
                    {"grams": True},
                ),
            ],
        ),
        (
            "count_window_patient",
            [
                (
                    "主表示をvalueが欠損していない測定の件数にしてください。対象がなければ0です。表はvalue,unitの2列で、unitはcountです。",
                    {"aggregate": "count"},
                ),
                ("主表示の期間を直近7日間に広げてください。", {"days": 7}),
                ("主表示だけを患者SYN_Bへ切り替えてください。", {"patient": "SYN_B"}),
            ],
        ),
        (
            "chart_window_patient",
            [
                (
                    "主表示を折れ線グラフにしてください。横軸はobserved_at、縦軸はvalueです。",
                    {"kind": "line_chart"},
                ),
                ("主表示を直近14日間に広げてください。", {"days": 14}),
                ("主表示だけを患者SYN_Cへ切り替えてください。", {"patient": "SYN_C"}),
            ],
        ),
        (
            "window_measure_columns",
            [
                ("主表示を直近3日間に広げてください。", {"days": 3}),
                (
                    "主表示だけを体重から脈拍へ切り替えてください。値と単位は脈拍に合わせてください。",
                    {"measure": "pulse"},
                ),
                ("主表示を新しい日時から順に並べてください。", {"descending": True}),
            ],
        ),
    ]
    steps = []
    for number, (name, definitions) in enumerate(sequences, 1):
        target = SequentialTarget()
        for index, (request, changes) in enumerate(definitions, 1):
            target = SequentialTarget.model_validate({**target.model_dump(), **changes})
            steps.append(
                Step(
                    id=f"sequence_{number:02d}_step_{index}",
                    sequence=name,
                    index=index,
                    request=request,
                    target=target,
                )
            )
    return steps


def target_columns(target: SequentialTarget) -> list[str]:
    """Return the explicitly requested result and table columns."""
    return COLUMNS if target.aggregate == "rows" else ["value", "unit"]


def unit_for(target: SequentialTarget) -> str:
    """Resolve the unit explicitly specified by the synthetic task."""
    if target.aggregate == "count":
        return "count"
    return "g" if target.grams else ("kg" if target.measure == "weight" else "bpm")


def audit_sql(target: SequentialTarget) -> str:
    """Compile only the audit reference, keeping it out of the execution checker."""
    if target.aggregate == "rows":
        return reference_sql(target)
    start = (datetime.fromisoformat(END) - timedelta(days=target.days)).isoformat(
        sep=" "
    )
    expression = "COUNT(value)" if target.aggregate == "count" else "AVG(value)"
    if target.grams:
        expression += " * 1000.0"
    return (
        f"SELECT {expression} AS value, '{unit_for(target)}' AS unit FROM measurements "
        f"WHERE patient = '{target.patient}' AND measure = '{target.measure}' "
        f"AND observed_at >= '{start}' AND observed_at <= '{END}'"
    )


def interpret(target: SequentialTarget, rows: list[dict[str, Any]]) -> list[list[Any]]:
    """Compute expected rows directly in Python, never using audit SQL."""
    selected = expected_rows(target, rows)
    if target.aggregate == "rows":
        return selected
    values = [row[1] for row in selected if row[1] is not None]
    value = (
        len(values)
        if target.aggregate == "count"
        else (sum(values) / len(values) if values else None)
    )
    return [[value, unit_for(target)]]


def initial_graph() -> ScenarioGraph:
    """Construct a supported graph with a main and an unchanged companion widget."""
    widgets = []
    for name, target in [
        ("main", SequentialTarget()),
        ("stable", SequentialTarget(measure="pulse")),
    ]:
        node = DataNode(
            id=f"{name}_data",
            context_key=f"{name}_data",
            model_name="measurements",
            data_type="dataframe",
            description="独立した合成測定データ",
            primary_fields=COLUMNS,
            sql=audit_sql(target),
        )
        widgets.append(
            WidgetNode(
                id=name,
                title="主表示" if name == "main" else "保持する脈拍",
                widget=DataframeSpec(data_key=node.context_key, column_order=COLUMNS),
                data_nodes=[node],
            )
        )
    return ScenarioGraph(
        id="synthetic_sequence",
        title="合成データの連続更新",
        tasks=[TaskNode(id="overview", title="測定の確認", widgets=widgets)],
    )


def request_prompt(step: Step) -> str:
    """Expose schema and current request, withholding cumulative target and audit rows."""
    return f"""合成データだけのUI更新課題です。利用できるテーブルとDWHモデルはmeasurementsです。
スキーマ: {SCHEMA}
patientはSYN_A/SYN_B/SYN_C、measureはweightまたはpulseです。
weightはkg、pulseはbpmです。valueがNULLなら欠損です。
observed_atはYYYY-MM-DD HH:MM:SSのTEXTです。基準日時は{END}です。
直近N日間は基準日時-N日以上、基準日時以下の両端を含む範囲です。
明示していない条件は現在のまま保持してください。stableの脈拍表示は変更対象外です。
overview/main/stable/main_data/stable_dataのIDと対応関係を保持してください。
測定値の一覧はobserved_at,value,unitをこの順で返します。集約ではvalue,unitを返します。
表はSQL結果の列を順にすべて表示します。折れ線はx=observed_at,y=valueです。
新しい表示部品や説明文は追加しません。タイトルの言い換えは許容します。
今回の更新要求:
{step.request}
"""


def prepare(inputs: Path) -> None:
    """Freeze requests, initial graph and seven finite synthetic database states."""
    inputs.mkdir(parents=True, exist_ok=False)
    steps = make_steps()
    save_json(inputs / "steps.json", [step.model_dump(mode="json") for step in steps])
    save_json(inputs / "initial_graph.json", initial_graph().model_dump(mode="json"))
    for step in steps:
        (inputs / f"{step.id}.txt").write_text(request_prompt(step), encoding="utf-8")
    for state in range(7):
        rows = make_rows(state)
        save_json(inputs / f"state_{state}.json", rows)
        create_database(rows, inputs / f"state_{state}.sqlite")
    save_json(
        inputs / "input_manifest.json",
        {path.name: sha256(path) for path in sorted(inputs.iterdir())},
    )


def pack_context(context: dict[str, object]) -> dict[str, Any]:
    """Serialize actual pipeline dataframes with null values and stable column order."""
    return {
        key: {
            "type": "dataframe",
            **json.loads(cast(str, value.to_json(orient="split", double_precision=15))),
        }
        if isinstance(value, pd.DataFrame)
        else {"type": "scalar", "value": value}
        for key, value in context.items()
    }


def unpack_context(context: dict[str, Any]) -> dict[str, object]:
    """Restore recorded context for local replay and renderer checks."""
    return {
        key: pd.DataFrame(value["data"], columns=value["columns"], index=value["index"])
        if value["type"] == "dataframe"
        else value["value"]
        for key, value in context.items()
    }


def same_rows(left: list[list[Any]], right: list[list[Any]]) -> bool:
    """Compare ordered rows, preserving NULL and allowing only numeric roundoff."""
    if len(left) != len(right):
        return False
    for a_row, b_row in zip(left, right, strict=True):
        if len(a_row) != len(b_row):
            return False
        for a, b in zip(a_row, b_row, strict=True):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
                    return False
            elif a != b:
                return False
    return True


def structure_issues(
    graph: ScenarioGraph, context: dict[str, Any], database: Path
) -> list[str]:
    """Check executable queries, actual cached results and resolvable display fields."""
    issues = []
    identifiers = [node.id for node in graph.widget_nodes]
    if len(identifiers) != len(set(identifiers)):
        issues.append("duplicate_widget")
    for widget in graph.widget_nodes:
        for node in widget.data_nodes:
            try:
                columns, rows = execute(node.sql or "", database)
                cached = context.get(node.context_key, {})
                if cached.get("columns") != columns or not same_rows(
                    cached.get("data", []), rows
                ):
                    issues.append(f"stale_context:{node.id}")
            except (sqlite3.Error, ValueError):
                issues.append(f"execution:{node.id}")
        spec = widget.widget.model_dump(mode="json")
        key = spec.get("data_key", spec.get("value_key"))
        cached = context.get(key, {})
        if not cached:
            issues.append(f"binding:{widget.id}")
        fields = spec.get("column_order") or []
        fields += [spec["x"]] if spec.get("x") else []
        fields += [spec["y"]] if isinstance(spec.get("y"), str) else spec.get("y") or []
        if any(field not in cached.get("columns", []) for field in fields):
            issues.append(f"display_column:{widget.id}")
    return issues


def display_issues(graph: ScenarioGraph, target: SequentialTarget) -> list[str]:
    """Apply identical binding and visible-field requirements to all informed checks."""
    issues = []
    if [task.id for task in graph.tasks] != ["overview"]:
        issues.append("task_set")
    if [widget.id for widget in graph.widget_nodes] != ["main", "stable"]:
        issues.append("widget_set_or_order")
    for widget in graph.widget_nodes:
        spec = target if widget.id == "main" else SequentialTarget(measure="pulse")
        view = widget.widget.model_dump(mode="json")
        expected_key = f"{widget.id}_data"
        if (
            len(widget.data_nodes) != 1
            or any(
                node.id != expected_key or node.context_key != expected_key
                for node in widget.data_nodes
            )
            or view.get("data_key") != expected_key
        ):
            issues.append(f"requested_binding:{widget.id}")
        if view["widget_type"] != spec.kind:
            issues.append(f"requested_kind:{widget.id}")
        if view["widget_type"] == "dataframe" and view.get("column_order") not in (
            None,
            target_columns(spec),
        ):
            issues.append(f"requested_columns:{widget.id}")
        if view["widget_type"] == "line_chart" and (
            view.get("x") != "observed_at" or view.get("y") not in ("value", ["value"])
        ):
            issues.append(f"requested_axes:{widget.id}")
    return issues


def conjuncts(expression: exp.Expression) -> list[exp.Expression]:
    """Flatten mandatory AND clauses without accepting optional OR branches."""
    if isinstance(expression, exp.Paren):
        return conjuncts(expression.this)
    if isinstance(expression, exp.And):
        return conjuncts(expression.this) + conjuncts(expression.expression)
    return [expression]


def constant(expression: exp.Expression, database: Path) -> Any:
    """Evaluate a constant SQL expression using the same restricted local executor."""
    if list(expression.find_all(exp.Column)) or list(expression.find_all(exp.Subquery)):
        return None
    try:
        return execute("SELECT " + expression.sql(dialect="sqlite"), database)[1][0][0]
    except (sqlite3.Error, ValueError, IndexError):
        return None


def simple_sql_issues(sql: str, target: SequentialTarget, database: Path) -> list[str]:
    """Check common SQL features without comparing reference SQL or executing target rows.

    This deliberately transparent baseline recognizes mandatory patient/item/time
    filters, aggregate kind, unit conversion, ordering and row limit. It is not a
    complete semantic analyzer: extra predicates and arithmetic can escape it.
    """
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return ["sql_parse"]
    if not isinstance(tree, exp.Select):
        return ["unsupported_query_shape"]
    where = tree.args.get("where")
    if where is None:
        return ["missing_where"]
    found: set[tuple[str, str, Any]] = set()
    reverse = {"GTE": "LTE", "LTE": "GTE", "EQ": "EQ"}
    for term in conjuncts(where.this):
        if isinstance(term, exp.Between) and isinstance(term.this, exp.Column):
            found.add((term.this.name, "GTE", constant(term.args["low"], database)))
            found.add((term.this.name, "LTE", constant(term.args["high"], database)))
        elif isinstance(term, (exp.EQ, exp.GTE, exp.LTE)):
            if isinstance(term.this, exp.Column):
                found.add(
                    (
                        term.this.name,
                        type(term).__name__,
                        constant(term.expression, database),
                    )
                )
            elif isinstance(term.expression, exp.Column):
                found.add(
                    (
                        term.expression.name,
                        reverse[type(term).__name__],
                        constant(term.this, database),
                    )
                )
    start = (datetime.fromisoformat(END) - timedelta(days=target.days)).isoformat(
        sep=" "
    )
    required = {
        ("patient", "EQ", target.patient),
        ("measure", "EQ", target.measure),
        ("observed_at", "GTE", start),
        ("observed_at", "LTE", END),
    }
    issues = [f"predicate:{item[0]}:{item[1]}" for item in sorted(required - found)]
    if {table.name for table in tree.find_all(exp.Table)} != {"measurements"}:
        issues.append("source")
    projections = {
        item.alias_or_name: item.this if isinstance(item, exp.Alias) else item
        for item in tree.expressions
    }
    if list(projections) != target_columns(target):
        issues.append("projection_columns")
    value = projections.get("value")
    unit = projections.get("unit")
    if value is None or unit is None:
        return issues + ["missing_projection"]
    aggregates = list(value.find_all(exp.AggFunc))
    if target.aggregate == "rows" and aggregates:
        issues.append("unexpected_aggregate")
    if target.aggregate == "average" and not any(
        isinstance(item, exp.Avg) for item in aggregates
    ):
        issues.append("average")
    if target.aggregate == "count" and not any(
        isinstance(item, exp.Count)
        and isinstance(item.this, exp.Column)
        and item.this.name == "value"
        for item in aggregates
    ):
        issues.append("count_nonnull")
    multipliers = [
        item
        for item in value.find_all(exp.Mul)
        if constant(item.this, database) == 1000
        or constant(item.expression, database) == 1000
    ]
    if bool(multipliers) != target.grams:
        issues.append("unit_multiplier")
    if not (
        isinstance(unit, exp.Column)
        and unit.name == "unit"
        and not target.grams
        and target.aggregate == "rows"
    ):
        if constant(unit, database) != unit_for(target):
            issues.append("unit_label")
    limit = tree.args.get("limit")
    actual_limit = constant(limit.expression, database) if limit is not None else None
    if actual_limit != target.limit:
        issues.append("limit")
    if target.aggregate == "rows":
        order = tree.args.get("order")
        first = (
            order.expressions[0] if order is not None and order.expressions else None
        )
        if (
            first is None
            or not isinstance(first.this, exp.Column)
            or first.this.name != "observed_at"
            or bool(first.args.get("desc")) != target.descending
        ):
            issues.append("order")
    return issues


def semantic_issues(
    graph: ScenarioGraph,
    target: SequentialTarget,
    inputs: Path,
    states: tuple[int, ...],
    *,
    audit: bool = False,
) -> list[str]:
    """Evaluate actual query behavior on visible or held-out synthetic states."""
    issues = display_issues(graph, target)
    for state in states:
        database = inputs / f"state_{state}.sqlite"
        fixture = json.loads((inputs / f"state_{state}.json").read_text())
        for widget in graph.widget_nodes:
            spec = target if widget.id == "main" else SequentialTarget(measure="pulse")
            for node in widget.data_nodes:
                try:
                    columns, actual = execute(node.sql or "", database)
                    expected = (
                        execute(audit_sql(spec), database)[1]
                        if audit
                        else interpret(spec, fixture)
                    )
                    if columns != target_columns(spec) or not same_rows(
                        actual, expected
                    ):
                        issues.append(f"result:{state}:{node.id}")
                except (sqlite3.Error, ValueError):
                    issues.append(f"execution:{state}:{node.id}")
    return issues


def evaluate(step: Step, event: dict[str, Any], inputs: Path) -> dict[str, Any]:
    """Score all terminal states, separating pipeline completion from correctness."""
    graph = ScenarioGraph.model_validate(event["graph"])
    structure = structure_issues(graph, event["context"], inputs / "state_0.sqlite")
    if event["status"] != "completed":
        structure.append("pipeline_not_completed")
    common = structure + display_issues(graph, step.target)
    simple = list(common)
    for widget in graph.widget_nodes:
        target = (
            step.target if widget.id == "main" else SequentialTarget(measure="pulse")
        )
        for node in widget.data_nodes:
            simple.extend(
                f"{node.id}:{issue}"
                for issue in simple_sql_issues(
                    node.sql or "", target, inputs / "state_0.sqlite"
                )
            )
    checks = {
        "structure": structure,
        "simple_sql": simple,
        "one_state": common + semantic_issues(graph, step.target, inputs, (0,)),
        "three_states": common + semantic_issues(graph, step.target, inputs, (0, 1, 2)),
    }
    audit = common + semantic_issues(
        graph, step.target, inputs, (3, 4, 5, 6), audit=True
    )
    return {
        "id": step.id,
        "sequence": step.sequence,
        "index": step.index,
        "pipeline_completed": event["status"] == "completed",
        "audit_valid": not audit,
        "audit_issues": sorted(set(audit)),
        "accepted": {key: not value for key, value in checks.items()},
        "issues": {key: sorted(set(value)) for key, value in checks.items()},
    }
