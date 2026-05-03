from __future__ import annotations

import json
from typing import Any

import streamlit as st
from pydantic import ValidationError

from interactive_ehr.sample_scenarios import get_chronic_disease_graph_scenario
from interactive_ehr.scenario_graph import (
    ScenarioGraph,
    generate_scenario_graph_incrementally,
    parse_scenario_graph_json,
    render_scenario_graph,
)


GRAPH_STATE_KEY = "scenario_graph"
GRAPH_JSON_STATE_KEY = "scenario_graph_json"
CONTEXT_STATE_KEY = "scenario_context"


def main() -> None:
    """Streamlitアプリのエントリポイント。ページ設定と初期UIを構築する。"""
    st.set_page_config(
        page_title="Interactive EHR",
        page_icon="🏥",
        layout="wide",
    )

    st.title("Interactive EHR")
    st.markdown("タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム")
    _inject_debug_json_styles()

    _initialize_state()
    preview_container = st.empty()
    _render_sidebar(preview_container)
    _render_preview(preview_container)


def _initialize_state() -> None:
    if GRAPH_STATE_KEY in st.session_state and CONTEXT_STATE_KEY in st.session_state:
        return

    graph, context = get_chronic_disease_graph_scenario()
    st.session_state[GRAPH_STATE_KEY] = graph
    st.session_state[CONTEXT_STATE_KEY] = context
    st.session_state[GRAPH_JSON_STATE_KEY] = _format_graph_json(graph)


def _render_sidebar(preview_container: Any) -> None:
    st.sidebar.header("シナリオ選択")
    st.sidebar.selectbox(
        "固定サンプル",
        ["慢性疾患を持つ高齢患者の外来診察"],
    )
    st.sidebar.caption("API認証なしで表示できる検証用ダミーデータです。")

    st.sidebar.divider()
    st.sidebar.header("Gemini生成")
    prompt = st.sidebar.text_area(
        "プロンプト",
        placeholder="例: 腎機能悪化の確認を中心に、検査推移と処方確認を分けて表示する",
        height=160,
    )
    if st.sidebar.button("タスクグラフ生成", type="primary"):
        _generate_graph_from_prompt(prompt, preview_container)

    st.sidebar.divider()
    st.sidebar.header("タスクグラフ JSON")
    st.sidebar.caption("手編集した valid JSON は UI プレビューに反映されます。")
    reset_clicked = st.sidebar.button("サンプルへ戻す")
    format_clicked = st.sidebar.button("JSON整形")
    if reset_clicked:
        _reset_to_sample()
    elif format_clicked:
        _format_current_json()

    json_text = st.sidebar.text_area(
        "現在描画しているタスクグラフ",
        key=GRAPH_JSON_STATE_KEY,
        height=520,
    )
    _update_graph_from_json(json_text)


def _render_preview(preview_container: Any) -> None:
    _render_graph_preview(preview_container, generating=False)


def _generate_graph_from_prompt(
    prompt: str,
    preview_container: Any,
) -> None:
    if not prompt.strip():
        st.sidebar.warning("生成プロンプトを入力してください。")
        return

    progress = st.sidebar.empty()
    for event in generate_scenario_graph_incrementally(
        prompt,
        st.session_state[CONTEXT_STATE_KEY],
    ):
        st.session_state[GRAPH_STATE_KEY] = event.graph
        st.session_state[GRAPH_JSON_STATE_KEY] = _format_graph_json(event.graph)
        _render_graph_preview(
            preview_container,
            generating=event.status != "completed",
        )
        if event.status == "failed":
            progress.warning(f"Gemini生成に失敗しました: {event.message}")
            return
        if event.status == "completed":
            progress.success(event.message)
        else:
            progress.info(event.message)


def _reset_to_sample() -> None:
    graph, context = get_chronic_disease_graph_scenario()
    st.session_state[GRAPH_STATE_KEY] = graph
    st.session_state[CONTEXT_STATE_KEY] = context
    st.session_state[GRAPH_JSON_STATE_KEY] = _format_graph_json(graph)


def _format_current_json() -> None:
    json_text = st.session_state.get(GRAPH_JSON_STATE_KEY, "")
    try:
        graph = parse_scenario_graph_json(json_text)
    except (json.JSONDecodeError, ValidationError) as exc:
        st.sidebar.error(f"JSONを整形できません: {exc}")
        return

    st.session_state[GRAPH_STATE_KEY] = graph
    st.session_state[GRAPH_JSON_STATE_KEY] = _format_graph_json(graph)


def _update_graph_from_json(json_text: str) -> None:
    try:
        graph = parse_scenario_graph_json(json_text)
    except json.JSONDecodeError as exc:
        st.sidebar.error(f"JSON構文エラー: {exc}")
        return
    except ValidationError as exc:
        st.sidebar.error(f"タスクグラフの検証エラー: {exc}")
        return

    st.session_state[GRAPH_STATE_KEY] = graph


def _render_graph_preview(
    preview_container: Any,
    *,
    generating: bool,
) -> None:
    with preview_container.container():
        st.subheader("UI プレビュー")
        graph = st.session_state[GRAPH_STATE_KEY]
        if generating and not graph.tasks:
            st.info("タスクグラフを生成しています。")
            return
        render_scenario_graph(
            graph,
            st.session_state[CONTEXT_STATE_KEY],
            show_missing_reference_warnings=not generating,
        )


def _format_graph_json(graph: ScenarioGraph) -> str:
    return graph.model_dump_json(indent=4)


def _inject_debug_json_styles() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"]
        textarea[aria-label="現在描画しているタスクグラフ"] {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
                "Liberation Mono", "Courier New", monospace;
            font-size: 10px !important;
            line-height: 1.25 !important;
            tab-size: 4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


main()
