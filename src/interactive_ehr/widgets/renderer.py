"""Streamlit renderer for widget specifications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal

import altair as alt
import pandas as pd
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
    NumberInputSpec,
    RadioSpec,
    SelectboxSpec,
    SliderSpec,
    TextAreaSpec,
    TextInputSpec,
    TimeInputSpec,
)
from interactive_ehr.widgets.layout import ColumnsSpec, ExpanderSpec, TabsSpec

if TYPE_CHECKING:
    from interactive_ehr.widgets import AnyWidget

LineChartAxisType = Literal["quantitative", "ordinal", "temporal", "nominal"]


def _missing_key(kind: str, key: str) -> None:
    st.warning(f"{kind} '{key}' が表示コンテキストに存在しません。")


def _resolve_context_value(
    context: Mapping[str, Any],
    key: str,
    kind: str,
) -> Any | None:
    if key not in context:
        _missing_key(kind, key)
        return None
    return context[key]


def _resolve_options(
    context: Mapping[str, Any],
    key: str,
) -> Sequence[Any] | None:
    value = _resolve_context_value(context, key, "options_key")
    if value is None:
        return None
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    st.warning(f"options_key '{key}' は選択肢リストとして扱えません。")
    return None


def _without_none(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _columns_for_data(data: Any) -> set[str] | None:
    if isinstance(data, pd.DataFrame):
        return {str(column) for column in data.columns}
    if isinstance(data, Sequence) and not isinstance(data, str | bytes):
        columns: set[str] = set()
        for row in data:
            if isinstance(row, Mapping):
                columns.update(str(column) for column in row)
        return columns or None
    return None


def _chart_axis_kwargs(
    data: Any,
    *,
    data_key: str,
    x: str | None,
    y: str | list[str] | None,
) -> tuple[str | None, str | list[str] | None]:
    columns = _columns_for_data(data)
    if columns is None:
        return x, y

    chart_x: str | None = None
    chart_y: str | list[str] | None = None
    if x is not None:
        if x in columns:
            chart_x = x
        else:
            st.warning(
                f"data_key '{data_key}' に chart の x カラム '{x}' が存在しません。"
            )

    if isinstance(y, list):
        valid_y = [column for column in y if column in columns]
        missing_y = [column for column in y if column not in columns]
        for column in missing_y:
            st.warning(
                f"data_key '{data_key}' に chart の y カラム '{column}' が存在しません。"
            )
        if valid_y:
            chart_y = valid_y
    elif isinstance(y, str):
        if y in columns:
            chart_y = y
        else:
            st.warning(
                f"data_key '{data_key}' に chart の y カラム '{y}' が存在しません。"
            )

    return chart_x, chart_y


def _dataframe_column_order(
    data: Any,
    *,
    data_key: str,
    column_order: list[str],
) -> list[str] | None:
    columns = _columns_for_data(data)
    if columns is None:
        return column_order

    valid_columns = [column for column in column_order if column in columns]
    for column in column_order:
        if column not in columns:
            st.warning(
                f"data_key '{data_key}' に dataframe の column_order "
                f"カラム '{column}' が存在しません。"
            )
    return valid_columns or None


def _line_chart_dataframe(data: Any, x: str | None) -> tuple[pd.DataFrame, str]:
    """折れ線グラフ用のDataFrameと横軸カラム名を返す."""

    dataframe = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    if x is not None:
        return dataframe, x

    index_name = str(dataframe.index.name or "index")
    while index_name in dataframe.columns:
        index_name = f"_{index_name}"
    dataframe = dataframe.reset_index(names=index_name)
    return dataframe, index_name


def _line_chart_y_columns(
    dataframe: pd.DataFrame,
    y: str | list[str] | None,
    *,
    x: str,
) -> list[str]:
    """折れ線グラフに描画する縦軸カラムを選ぶ."""

    if isinstance(y, str):
        return [y]
    if isinstance(y, list):
        return y
    return [
        str(column)
        for column in dataframe.select_dtypes(include="number").columns
        if str(column) != x
    ]


def _looks_like_date_axis(column_name: str) -> bool:
    """カラム名から日付・時刻の横軸かを判定する."""

    normalized = column_name.lower()
    return any(
        marker in normalized
        for marker in ("date", "time", "日", "月", "年", "時")
    )


def _coerce_line_chart_x(
    dataframe: pd.DataFrame,
    x: str,
    *,
    data_key: str,
) -> tuple[pd.DataFrame, LineChartAxisType]:
    """横軸を数値または日時へ変換し、Altairの型を返す."""

    converted = dataframe.copy()
    values = converted[x]
    non_null = values.dropna()
    if pd.api.types.is_datetime64_any_dtype(values):
        return converted.sort_values(x, kind="stable"), "temporal"
    if pd.api.types.is_numeric_dtype(values):
        return converted.sort_values(x, kind="stable"), "quantitative"
    if non_null.empty:
        return converted, "nominal"

    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().all():
        converted[x] = pd.to_numeric(values, errors="coerce")
        return converted.sort_values(x, kind="stable"), "quantitative"

    parsed_dates = pd.to_datetime(non_null, errors="coerce", format="mixed")
    if parsed_dates.notna().all():
        converted[x] = pd.to_datetime(values, errors="coerce", format="mixed")
        return converted.sort_values(x, kind="stable"), "temporal"

    if _looks_like_date_axis(x):
        st.warning(
            f"data_key '{data_key}' の横軸 '{x}' に日付へ変換できない値があるため、"
            "カテゴリ軸で表示します。"
        )
    return converted, "nominal"


def _build_line_chart(
    data: Any,
    *,
    data_key: str,
    x: str | None,
    y: str | list[str] | None,
    x_label: str | None,
    y_label: str | None,
    height: int | None,
) -> alt.LayerChart | None:
    """実測点付きの折れ線グラフを構築する."""

    dataframe, chart_x = _line_chart_dataframe(data, x)
    if chart_x not in dataframe.columns:
        return None
    y_columns = _line_chart_y_columns(dataframe, y, x=chart_x)
    if not y_columns:
        st.warning(f"data_key '{data_key}' に描画できる数値カラムがありません。")
        return None

    dataframe, x_type = _coerce_line_chart_x(
        dataframe,
        chart_x,
        data_key=data_key,
    )
    long_data = dataframe.melt(
        id_vars=[chart_x],
        value_vars=y_columns,
        var_name="系列",
        value_name="値",
    )
    base = alt.Chart(long_data).encode(
        x=alt.X(chart_x, type=x_type, title=x_label),
        y=alt.Y("値", type="quantitative", title=y_label),
        color=alt.Color(
            "系列",
            type="nominal",
            legend=None if len(y_columns) == 1 else alt.Legend(title=None),
        ),
        tooltip=[
            alt.Tooltip(chart_x, type=x_type, title=x_label or chart_x),
            alt.Tooltip("系列", type="nominal"),
            alt.Tooltip("値", type="quantitative", title=y_label or "値"),
        ],
    )
    chart = base.mark_line() + base.mark_point(filled=True, size=55)
    return chart if height is None else chart.properties(height=height)


def render_widgets(
    widgets: Sequence[AnyWidget],
    context: Mapping[str, Any],
) -> list[object | None]:
    """Render multiple widgets and return Streamlit return values."""

    return [render_widget(widget, context) for widget in widgets]


def render_widget(
    widget: AnyWidget,
    context: Mapping[str, Any],
) -> object | None:
    """Render one widget specification with Streamlit.

    Missing context keys are reported in the UI and do not stop rendering.
    """

    if isinstance(widget, DataframeSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        if widget.column_order is not None:
            column_order = _dataframe_column_order(
                data,
                data_key=widget.data_key,
                column_order=widget.column_order,
            )
            if column_order is None:
                return st.dataframe(
                    data,
                    **_without_none(
                        hide_index=widget.hide_index,
                        height=widget.height,
                        key=widget.key,
                    ),
                )
            return st.dataframe(
                data,
                column_order=column_order,
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
        if widget.data_key is not None:
            data = _resolve_context_value(context, widget.data_key, "data_key")
            return None if data is None else st.markdown(str(data))
        if widget.body is None:
            st.warning("markdown widget に body または data_key を設定してください。")
            return None
        return st.markdown(widget.body)

    if isinstance(widget, TextSpec):
        return st.text(widget.body)

    if isinstance(widget, LineChartSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        chart_x, chart_y = _chart_axis_kwargs(
            data,
            data_key=widget.data_key,
            x=widget.x,
            y=widget.y,
        )
        chart = _build_line_chart(
            data,
            data_key=widget.data_key,
            x=chart_x,
            y=chart_y,
            x_label=widget.x_label,
            y_label=widget.y_label,
            height=widget.height,
        )
        return None if chart is None else st.altair_chart(chart, width="stretch")

    if isinstance(widget, BarChartSpec):
        data = _resolve_context_value(context, widget.data_key, "data_key")
        if data is None:
            return None
        chart_x, chart_y = _chart_axis_kwargs(
            data,
            data_key=widget.data_key,
            x=widget.x,
            y=widget.y,
        )
        return st.bar_chart(
            data,
            x=chart_x,
            y=chart_y,
            **_without_none(
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

    if isinstance(widget, TimeInputSpec):
        return st.time_input(
            widget.label,
            **_without_none(
                value=widget.default_value,
                step=timedelta(seconds=widget.step_seconds),
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

    if isinstance(widget, TextAreaSpec):
        return st.text_area(
            widget.label,
            **_without_none(
                value=widget.default_value,
                height=widget.height,
                max_chars=widget.max_chars,
                placeholder=widget.placeholder,
                key=widget.key,
            ),
        )

    if isinstance(widget, NumberInputSpec):
        return st.number_input(
            widget.label,
            **_without_none(
                min_value=widget.min_value,
                max_value=widget.max_value,
                value=widget.default_value,
                step=widget.step,
                format=widget.format_str,
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
