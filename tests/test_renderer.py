"""Streamlit renderer tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from typing import Any

from pydantic import TypeAdapter

import interactive_ehr.widgets.renderer as renderer
from interactive_ehr.sample_scenarios import get_chronic_disease_scenario
from interactive_ehr.widgets import (
    AnyWidget,
    BarChartSpec,
    CheckboxSpec,
    ColumnsSpec,
    DataframeSpec,
    DateInputSpec,
    ExpanderSpec,
    JsonSpec,
    LineChartSpec,
    MarkdownSpec,
    MetricSpec,
    MultiselectSpec,
    NumberInputSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TableSpec,
    TabsSpec,
    TextAreaSpec,
    TextInputSpec,
    TextSpec,
    TimeInputSpec,
)


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class FakeContainer:
    def __enter__(self) -> FakeContainer:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[Call] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> str:
        self.calls.append(Call(name=name, args=args, kwargs=kwargs))
        return f"{name}-result"

    def dataframe(self, *args: Any, **kwargs: Any) -> str:
        return self._record("dataframe", *args, **kwargs)

    def table(self, *args: Any, **kwargs: Any) -> str:
        return self._record("table", *args, **kwargs)

    def metric(self, *args: Any, **kwargs: Any) -> str:
        return self._record("metric", *args, **kwargs)

    def json(self, *args: Any, **kwargs: Any) -> str:
        return self._record("json", *args, **kwargs)

    def markdown(self, *args: Any, **kwargs: Any) -> str:
        return self._record("markdown", *args, **kwargs)

    def text(self, *args: Any, **kwargs: Any) -> str:
        return self._record("text", *args, **kwargs)

    def caption(self, *args: Any, **kwargs: Any) -> str:
        return self._record("caption", *args, **kwargs)

    def code(self, *args: Any, **kwargs: Any) -> str:
        return self._record("code", *args, **kwargs)

    def line_chart(self, *args: Any, **kwargs: Any) -> str:
        return self._record("line_chart", *args, **kwargs)

    def altair_chart(self, *args: Any, **kwargs: Any) -> str:
        return self._record("altair_chart", *args, **kwargs)

    def bar_chart(self, *args: Any, **kwargs: Any) -> str:
        return self._record("bar_chart", *args, **kwargs)

    def selectbox(self, *args: Any, **kwargs: Any) -> str:
        return self._record("selectbox", *args, **kwargs)

    def multiselect(self, *args: Any, **kwargs: Any) -> str:
        return self._record("multiselect", *args, **kwargs)

    def date_input(self, *args: Any, **kwargs: Any) -> str:
        return self._record("date_input", *args, **kwargs)

    def text_input(self, *args: Any, **kwargs: Any) -> str:
        return self._record("text_input", *args, **kwargs)

    def time_input(self, *args: Any, **kwargs: Any) -> str:
        return self._record("time_input", *args, **kwargs)

    def text_area(self, *args: Any, **kwargs: Any) -> str:
        return self._record("text_area", *args, **kwargs)

    def number_input(self, *args: Any, **kwargs: Any) -> str:
        return self._record("number_input", *args, **kwargs)

    def checkbox(self, *args: Any, **kwargs: Any) -> str:
        return self._record("checkbox", *args, **kwargs)

    def radio(self, *args: Any, **kwargs: Any) -> str:
        return self._record("radio", *args, **kwargs)

    def slider(self, *args: Any, **kwargs: Any) -> str:
        return self._record("slider", *args, **kwargs)

    def warning(self, *args: Any, **kwargs: Any) -> str:
        return self._record("warning", *args, **kwargs)

    def columns(self, *args: Any, **kwargs: Any) -> list[FakeContainer]:
        self._record("columns", *args, **kwargs)
        count_or_widths = args[0]
        count = count_or_widths if isinstance(count_or_widths, int) else len(count_or_widths)
        return [FakeContainer() for _ in range(count)]

    def tabs(self, *args: Any, **kwargs: Any) -> list[FakeContainer]:
        self._record("tabs", *args, **kwargs)
        return [FakeContainer() for _ in args[0]]

    def expander(self, *args: Any, **kwargs: Any) -> FakeContainer:
        self._record("expander", *args, **kwargs)
        return FakeContainer()


def test_render_display_widgets(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    widgets: list[AnyWidget] = [
        DataframeSpec(data_key="rows", column_order=["name"]),
        TableSpec(data_key="rows"),
        MetricSpec(label="血圧", value_key="bp", delta_key="bp_delta"),
        JsonSpec(data_key="raw", expanded=False),
        MarkdownSpec(body="**note**"),
        TextSpec(body="plain"),
    ]
    context = {"rows": [{"name": "A"}], "bp": "140", "bp_delta": "+4", "raw": {"a": 1}}

    results = renderer.render_widgets(widgets, context)

    assert results == [
        "dataframe-result",
        "table-result",
        "metric-result",
        "json-result",
        "markdown-result",
        "text-result",
    ]
    assert [call.name for call in fake.calls] == [
        "dataframe",
        "table",
        "metric",
        "json",
        "markdown",
        "text",
    ]
    assert fake.calls[0].kwargs["column_order"] == ["name"]
    assert fake.calls[2].kwargs["delta"] == "+4"
    assert fake.calls[3].kwargs["expanded"] is False


def test_markdown_data_key_renders_context_value(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    result = renderer.render_widget(
        MarkdownSpec(data_key="summary"),
        {"summary": "### 患者サマリ\n- 72歳男性"},
    )

    assert result == "markdown-result"
    assert [call.name for call in fake.calls] == ["markdown"]
    assert fake.calls[0].args[0].startswith("### 患者サマリ")


def test_render_chart_and_input_widgets(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    widgets: list[AnyWidget] = [
        LineChartSpec(data_key="trend", x="日付", y=["A"]),
        BarChartSpec(data_key="bars", x="分類", y="件数", horizontal=True),
        SelectboxSpec(label="患者", options_key="patients"),
        MultiselectSpec(label="カテゴリ", options_key="categories", default_keys=["検査"]),
        DateInputSpec(label="基準日"),
        TimeInputSpec(label="服薬時刻", default_value=time(9, 0), step_seconds=1800),
        TextInputSpec(label="検索", placeholder="keyword"),
        TextAreaSpec(label="メモ", default_value="note", height=160, max_chars=200),
        NumberInputSpec(
            label="閾値",
            min_value=0,
            max_value=10,
            default_value=3,
            step=0.5,
            format_str="%.1f",
        ),
        CheckboxSpec(label="詳細", default_value=True),
        RadioSpec(label="目的", options_key="purposes", horizontal=True),
        SliderSpec(label="期間", min_value=1, max_value=12, default_value=6),
    ]
    context = {
        "trend": [{"日付": "2026-01-01", "A": 1}],
        "bars": [{"分類": "x", "件数": 1}],
        "patients": ["P1"],
        "categories": ["概要", "検査"],
        "purposes": ["定期外来"],
    }

    renderer.render_widgets(widgets, context)

    assert [call.name for call in fake.calls] == [
        "altair_chart",
        "bar_chart",
        "selectbox",
        "multiselect",
        "date_input",
        "time_input",
        "text_input",
        "text_area",
        "number_input",
        "checkbox",
        "radio",
        "slider",
    ]
    assert fake.calls[1].kwargs["horizontal"] is True
    assert fake.calls[0].kwargs["width"] == "stretch"
    assert fake.calls[3].kwargs["default"] == ["検査"]
    assert fake.calls[5].kwargs["step"] == timedelta(seconds=1800)
    assert fake.calls[7].kwargs["height"] == 160
    assert fake.calls[8].kwargs["format"] == "%.1f"
    assert fake.calls[10].kwargs["horizontal"] is True


def test_chart_missing_columns_warn_without_exception(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    renderer.render_widgets(
        [
            LineChartSpec(
                data_key="renal_trend",
                x="date",
                y=["eGFR", "missing_value"],
            )
        ],
        {
            "renal_trend": [
                {"検査日": "2026-04-20", "eGFR": 38.2, "Cr": 1.19},
            ]
        },
    )

    assert [call.name for call in fake.calls] == [
        "warning",
        "warning",
        "altair_chart",
    ]
    assert "date" in fake.calls[0].args[0]
    assert "missing_value" in fake.calls[1].args[0]
    chart_spec = fake.calls[2].args[0].to_dict()
    assert chart_spec["layer"][0]["encoding"]["x"]["field"] == "index"


def test_line_chart_uses_temporal_spacing_and_observation_points(
    monkeypatch: Any,
) -> None:
    """日付を時間軸へ変換し、折れ線と実測点を重ねて描画する."""

    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    renderer.render_widget(
        LineChartSpec(
            data_key="trend",
            x="検査日",
            y="eGFR",
            x_label="検査日",
            y_label="eGFR",
        ),
        {
            "trend": [
                {"検査日": "2026-05-01", "eGFR": 42.0},
                {"検査日": "2025-10-01", "eGFR": 50.0},
                {"検査日": "2026-01-01", "eGFR": 47.0},
                {"検査日": "2026-04-01", "eGFR": 43.0},
            ]
        },
    )

    assert [call.name for call in fake.calls] == ["altair_chart"]
    chart_spec = fake.calls[0].args[0].to_dict()
    assert [layer["mark"]["type"] for layer in chart_spec["layer"]] == [
        "line",
        "point",
    ]
    assert chart_spec["layer"][0]["encoding"]["x"]["type"] == "temporal"
    assert chart_spec["layer"][1]["mark"]["filled"] is True
    dataset = next(iter(chart_spec["datasets"].values()))
    assert [row["検査日"] for row in dataset] == [
        "2025-10-01T00:00:00",
        "2026-01-01T00:00:00",
        "2026-04-01T00:00:00",
        "2026-05-01T00:00:00",
    ]


def test_line_chart_uses_quantitative_x_for_numeric_strings(
    monkeypatch: Any,
) -> None:
    """数値文字列の横軸を等間隔のカテゴリとして扱わない."""

    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    renderer.render_widget(
        LineChartSpec(data_key="trend", x="経過日", y=["A", "B"]),
        {
            "trend": [
                {"経過日": "30", "A": 2, "B": 3},
                {"経過日": "1", "A": 1, "B": 2},
            ]
        },
    )

    chart_spec = fake.calls[0].args[0].to_dict()
    assert chart_spec["layer"][0]["encoding"]["x"]["type"] == "quantitative"
    assert chart_spec["layer"][0]["encoding"]["color"]["legend"] == {
        "title": None
    }


def test_line_chart_warns_and_preserves_invalid_date_values(
    monkeypatch: Any,
) -> None:
    """不正な日付を黙って欠落させず、カテゴリ軸へ戻す."""

    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    renderer.render_widget(
        LineChartSpec(data_key="trend", x="検査日", y="A"),
        {
            "trend": [
                {"検査日": "2026-01-01", "A": 1},
                {"検査日": "日付不明", "A": 2},
            ]
        },
    )

    assert [call.name for call in fake.calls] == ["warning", "altair_chart"]
    assert "カテゴリ軸" in fake.calls[0].args[0]
    chart_spec = fake.calls[1].args[0].to_dict()
    assert chart_spec["layer"][0]["encoding"]["x"]["type"] == "nominal"
    dataset = next(iter(chart_spec["datasets"].values()))
    assert {row["検査日"] for row in dataset} == {"2026-01-01", "日付不明"}


def test_dataframe_missing_column_order_warns_without_exception(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    renderer.render_widgets(
        [DataframeSpec(data_key="rows", column_order=["name", "missing"])],
        {"rows": [{"name": "A"}]},
    )

    assert [call.name for call in fake.calls] == ["warning", "dataframe"]
    assert "missing" in fake.calls[0].args[0]
    assert fake.calls[1].kwargs["column_order"] == ["name"]


def test_render_nested_layouts(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    widgets: list[AnyWidget] = [
        ColumnsSpec(
            columns=[
                [MetricSpec(label="A", value_key="a")],
                [TextSpec(body="B")],
            ],
            widths=[2, 1],
        ),
        TabsSpec(
            labels=["tab1", "tab2"],
            tabs=[
                [MarkdownSpec(body="tab1")],
                [ExpanderSpec(label="detail", children=[TextSpec(body="detail")])],
            ],
        ),
    ]

    renderer.render_widgets(widgets, {"a": 1})

    assert [call.name for call in fake.calls] == [
        "columns",
        "metric",
        "text",
        "tabs",
        "markdown",
        "expander",
        "text",
    ]
    assert fake.calls[0].args == ([2, 1],)
    assert fake.calls[5].kwargs["expanded"] is False


def test_missing_context_keys_warn_without_exception(monkeypatch: Any) -> None:
    fake = FakeStreamlit()
    monkeypatch.setattr(renderer, "st", fake)

    results = renderer.render_widgets(
        [
            DataframeSpec(data_key="missing_rows"),
            MetricSpec(label="x", value_key="missing_value"),
            SelectboxSpec(label="x", options_key="missing_options"),
        ],
        {},
    )

    assert results == [None, None, None]
    assert [call.name for call in fake.calls] == ["warning", "warning", "warning"]
    assert "missing_rows" in fake.calls[0].args[0]
    assert "missing_value" in fake.calls[1].args[0]
    assert "missing_options" in fake.calls[2].args[0]


def test_chronic_disease_scenario_builds_valid_widgets(monkeypatch: Any) -> None:
    import interactive_ehr.scenario_graph as scenario_graph

    monkeypatch.setattr(
        scenario_graph,
        "execute_read_sql",
        lambda sql: _sample_sql_result(sql),
    )
    widgets, context = get_chronic_disease_scenario()
    adapter = TypeAdapter(list[AnyWidget])

    validated = adapter.validate_python(widgets)

    assert len(validated) == len(widgets)
    assert "chart_bp_trend" in context
    assert "metric_latest_egfr" in context
    assert "metric_patient_material" in context
    flattened = _flatten_widgets(validated)
    assert all(not isinstance(widget, DataframeSpec | TableSpec) for widget in flattened)
    assert all(not isinstance(widget, MarkdownSpec) for widget in flattened)


def _flatten_widgets(widgets: list[AnyWidget]) -> list[AnyWidget]:
    flattened: list[AnyWidget] = []
    for widget in widgets:
        flattened.append(widget)
        if isinstance(widget, ColumnsSpec):
            for column in widget.columns:
                flattened.extend(_flatten_widgets(column))
        if isinstance(widget, TabsSpec):
            for tab in widget.tabs:
                flattened.extend(_flatten_widgets(tab))
        if isinstance(widget, ExpanderSpec):
            flattened.extend(_flatten_widgets(widget.children))
    return flattened


def _sample_sql_result(sql: str) -> Any:
    import pandas as pd

    if "慢性疾患外来_検査推移" in sql:
        return pd.DataFrame(
            [
                {"検査日": "2026-01-20", "HbA1c": 7.3, "eGFR": 48, "UACR": 88},
                {"検査日": "2026-04-21", "HbA1c": 7.2, "eGFR": 45, "UACR": 96},
            ]
        )
    if "慢性疾患外来_血圧推移" in sql:
        return pd.DataFrame(
            [
                {"測定日": "2026-01-20", "外来収縮期": 146, "外来拡張期": 82, "家庭収縮期": 140},
                {"測定日": "2026-04-21", "外来収縮期": 148, "外来拡張期": 84, "家庭収縮期": 142},
            ]
        )
    if "慢性疾患外来_処方" in sql:
        return pd.DataFrame([{"カテゴリ": "降圧・腎保護", "薬剤数": 2}])
    if "慢性疾患外来_生活指導" in sql:
        return pd.DataFrame([{"項目": "家庭血圧記録", "達成率": 70}])
    return pd.DataFrame([{"value": "sample"}])
