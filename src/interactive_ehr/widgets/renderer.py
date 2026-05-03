"""Streamlit renderer for widget specifications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import streamlit as st

from interactive_ehr.widgets.chart import BarChartSpec, LineChartSpec
from interactive_ehr.widgets.display import (
    DataframeSpec,
    JsonSpec,
    MarkdownSpec,
    MetricSpec,
    TableSpec,
    TextSpec,
)
from interactive_ehr.widgets.input import (
    CheckboxSpec,
    DateInputSpec,
    MultiselectSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TextInputSpec,
)
from interactive_ehr.widgets.layout import ColumnsSpec, ExpanderSpec, TabsSpec

if TYPE_CHECKING:
    from interactive_ehr.widgets import AnyWidget


def _missing_key(kind: str, key: str) -> None:
    st.warning(f"{kind} '{key}' が表示コンテキストに存在しません。")


def _resolve_context_value(
    context: Mapping[str, object],
    key: str,
    kind: str,
) -> object | None:
    if key not in context:
        _missing_key(kind, key)
        return None
    return context[key]


def _resolve_options(
    context: Mapping[str, object],
    key: str,
) -> Sequence[object] | None:
    value = _resolve_context_value(context, key, "options_key")
    if value is None:
        return None
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    st.warning(f"options_key '{key}' は選択肢リストとして扱えません。")
    return None


def _without_none(**kwargs: object) -> dict[str, object]:
    return {key: value for key, value in kwargs.items() if value is not None}


def render_widgets(
    widgets: Sequence[AnyWidget],
    context: Mapping[str, object],
) -> list[object | None]:
    """Render multiple widgets and return Streamlit return values."""

    return [render_widget(widget, context) for widget in widgets]


def render_widget(
    widget: AnyWidget,
    context: Mapping[str, object],
) -> object | None:
    """Render one widget specification with Streamlit.

    Missing context keys are reported in the UI and do not stop rendering.
    """

    if isinstance(widget, DataframeSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        if widget.column_order is not None:
            return st.dataframe(
                data,
                column_order=widget.column_order,
                **_without_none(
                    hide_index=widget.hide_index,
                    height=widget.height,
                    key=widget.key,
                ),
            )
        return st.dataframe(
            data,
            **_without_none(
                hide_index=widget.hide_index,
                height=widget.height,
                key=widget.key,
            ),
        )

    if isinstance(widget, TableSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        return None if data is None else st.table(data)

    if isinstance(widget, MetricSpec):
        value = _resolve_context_value(context, widget.value_key, "value_key")
        if value is None:
            return None
        delta = None
        if widget.delta_key is not None:
            delta = _resolve_context_value(context, widget.delta_key, "delta_key")
        return st.metric(
            widget.label,
            value,
            delta=delta,
            delta_color=widget.delta_color,
        )

    if isinstance(widget, JsonSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        return None if data is None else st.json(data, expanded=widget.expanded)

    if isinstance(widget, MarkdownSpec):
        return st.markdown(widget.body)

    if isinstance(widget, TextSpec):
        return st.text(widget.body)

    if isinstance(widget, LineChartSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        return st.line_chart(
            data,
            **_without_none(
                x=widget.x,
                y=widget.y,
                x_label=widget.x_label,
                y_label=widget.y_label,
                height=widget.height,
            ),
        )

    if isinstance(widget, BarChartSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        return st.bar_chart(
            data,
            **_without_none(
                x=widget.x,
                y=widget.y,
                x_label=widget.x_label,
                y_label=widget.y_label,
                height=widget.height,
                horizontal=widget.horizontal,
            ),
        )

    if isinstance(widget, SelectboxSpec):
        options = _resolve_options(context, widget.options_key)
        if options is None:
            return None
        return st.selectbox(
            widget.label,
            options,
            **_without_none(
                index=widget.default_index,
                placeholder=widget.placeholder,
                key=widget.key,
            ),
        )

    if isinstance(widget, MultiselectSpec):
        options = _resolve_options(context, widget.options_key)
        if options is None:
            return None
        return st.multiselect(
            widget.label,
            options,
            **_without_none(
                default=widget.default_keys,
                max_selections=widget.max_selections,
                placeholder=widget.placeholder,
                key=widget.key,
            ),
        )

    if isinstance(widget, DateInputSpec):
        return st.date_input(
            widget.label,
            **_without_none(
                value=widget.default_value,
                min_value=widget.min_value,
                max_value=widget.max_value,
                key=widget.key,
            ),
        )

    if isinstance(widget, TextInputSpec):
        return st.text_input(
            widget.label,
            **_without_none(
                value=widget.default_value,
                max_chars=widget.max_chars,
                placeholder=widget.placeholder,
                key=widget.key,
            ),
        )

    if isinstance(widget, CheckboxSpec):
        return st.checkbox(
            widget.label,
            **_without_none(value=widget.default_value, key=widget.key),
        )

    if isinstance(widget, RadioSpec):
        options = _resolve_options(context, widget.options_key)
        if options is None:
            return None
        return st.radio(
            widget.label,
            options,
            **_without_none(
                index=widget.default_index,
                horizontal=widget.horizontal,
                key=widget.key,
            ),
        )

    if isinstance(widget, SliderSpec):
        return st.slider(
            widget.label,
            **_without_none(
                min_value=widget.min_value,
                max_value=widget.max_value,
                value=widget.default_value,
                step=widget.step,
                key=widget.key,
            ),
        )

    if isinstance(widget, ColumnsSpec):
        column_handles = st.columns(
            widget.widths if widget.widths is not None else len(widget.columns),
            gap=widget.gap,
        )
        rendered: list[object | None] = []
        for column, children in zip(column_handles, widget.columns, strict=True):
            with column:
                rendered.extend(render_widgets(children, context))
        return rendered

    if isinstance(widget, TabsSpec):
        tab_handles = st.tabs(widget.labels)
        rendered = []
        for tab, children in zip(tab_handles, widget.tabs, strict=True):
            with tab:
                rendered.extend(render_widgets(children, context))
        return rendered

    if isinstance(widget, ExpanderSpec):
        with st.expander(widget.label, expanded=widget.expanded):
            return render_widgets(widget.children, context)

    st.warning(f"未対応のウィジェット種別です: {type(widget).__name__}")
    return None
