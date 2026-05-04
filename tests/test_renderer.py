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

    def line_chart(self, *args: Any, **kwargs: Any) -> str:
        return self._record("line_chart", *args, **kwargs)

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
        "line_chart",
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
        "line_chart",
    ]
    assert "date" in fake.calls[0].args[0]
    assert "missing_value" in fake.calls[1].args[0]
    assert fake.calls[2].kwargs["x"] is None
    assert fake.calls[2].kwargs["y"] == ["eGFR"]


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


def test_chronic_disease_scenario_builds_valid_widgets() -> None:
    widgets, context = get_chronic_disease_scenario()
    adapter = TypeAdapter(list[AnyWidget])

    validated = adapter.validate_python(widgets)

    assert len(validated) == len(widgets)
    assert "current_prescriptions" in context
    assert "recent_labs" in context
