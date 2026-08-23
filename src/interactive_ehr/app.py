from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from html import escape
from typing import Any, Literal
from zoneinfo import ZoneInfo

import streamlit as st
from pydantic import ValidationError

from interactive_ehr.provenance import source_overview, summarize_data_nodes
from interactive_ehr.sample_scenarios import (
    get_anesthesia_preop_graph_scenario,
    get_chronic_disease_graph_scenario,
)
from interactive_ehr.scenario_graph import (
    ScenarioGraph,
    build_dwh_context_for_graph,
    build_sql_context_for_graph,
    parse_scenario_graph_json,
    render_scenario_graph,
    update_scenario_graph_incrementally,
)


GraphOrigin = Literal["sample", "gemini", "manual"]
SampleFactory = Callable[[], tuple[ScenarioGraph, dict[str, object]]]

GRAPH_STATE_KEY = "scenario_graph"
GRAPH_JSON_STATE_KEY = "scenario_graph_json"
CONTEXT_STATE_KEY = "scenario_context"
GRAPH_ORIGIN_STATE_KEY = "scenario_graph_origin"
LOADED_AT_STATE_KEY = "scenario_loaded_at"
CURRENT_SAMPLE_STATE_KEY = "current_sample"
SAMPLE_SELECT_WIDGET_KEY = "sample_selector"

DEFAULT_SAMPLE_NAME = "麻酔科術前外来"
SAMPLE_FACTORIES: dict[str, SampleFactory] = {
    "麻酔科術前外来": get_anesthesia_preop_graph_scenario,
    "慢性疾患外来": get_chronic_disease_graph_scenario,
}
GRAPH_ORIGIN_LABELS: dict[GraphOrigin, str] = {
    "sample": "標準デモ",
    "gemini": "Gemini生成",
    "manual": "JSON編集",
}
JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")


def main() -> None:
    """Streamlitアプリのページ設定と診療UIを構築する。"""

    st.set_page_config(
        page_title="Interactive EHR",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    _inject_clinical_styles()
    _initialize_state()
    preview_container = st.empty()
    _render_sidebar(preview_container)
    _render_preview(preview_container)


def _initialize_state() -> None:
    """初回表示に必要なScenarioGraphとセッション情報を初期化する。"""

    if GRAPH_STATE_KEY in st.session_state and CONTEXT_STATE_KEY in st.session_state:
        graph = st.session_state[GRAPH_STATE_KEY]
        sample_name = _sample_name_for_graph(graph)
        st.session_state.setdefault(CURRENT_SAMPLE_STATE_KEY, sample_name)
        st.session_state.setdefault(SAMPLE_SELECT_WIDGET_KEY, sample_name)
        st.session_state.setdefault(GRAPH_ORIGIN_STATE_KEY, "sample")
        st.session_state.setdefault(LOADED_AT_STATE_KEY, _now())
        return
    _reset_to_sample(DEFAULT_SAMPLE_NAME)
    st.session_state[SAMPLE_SELECT_WIDGET_KEY] = DEFAULT_SAMPLE_NAME


def _render_sidebar(preview_container: Any) -> None:
    """デモ選択と折りたたんだUI編集ツールをサイドバーへ表示する。"""

    st.sidebar.markdown("## Interactive EHR")
    st.sidebar.caption("研究用の合成症例デモ")
    selected_sample = st.sidebar.selectbox(
        "表示するシナリオ",
        list(SAMPLE_FACTORIES),
        key=SAMPLE_SELECT_WIDGET_KEY,
    )
    if selected_sample != st.session_state[CURRENT_SAMPLE_STATE_KEY]:
        _reset_to_sample(selected_sample)
    st.sidebar.caption(
        "診療画面では患者文脈と情報源を優先して表示します。生成・編集機能は下にまとめています。"
    )

    with st.sidebar.expander("UI生成・編集ツール", expanded=False):
        _render_graph_editor(preview_container)


def _render_graph_editor(preview_container: Any) -> None:
    """Gemini生成とScenarioGraph JSON編集の操作を表示する。"""

    st.markdown("#### Geminiで画面構成を更新")
    st.caption(
        "合成データの表示コンテキストが設定済みのGemini接続先へ送信されます。"
    )
    with st.form("prompt_form", clear_on_submit=False):
        prompt = st.text_area(
            "変更内容",
            key="user_prompt",
            placeholder="例: 腎機能悪化の確認を中心に、検査推移と処方確認を分けて表示する",
            height=140,
        )
        submitted = st.form_submit_button("画面構成を生成", type="primary")
    if submitted:
        _generate_graph_from_prompt(prompt, preview_container)

    st.divider()
    st.markdown("#### ScenarioGraph JSON")
    st.caption("有効なJSONだけを診療画面へ反映します。表示値はJSONに含みません。")
    button_columns = st.columns(2)
    with button_columns[0]:
        reset_clicked = st.button("デモへ戻す", use_container_width=True)
    with button_columns[1]:
        format_clicked = st.button("JSONを整形", use_container_width=True)
    if reset_clicked:
        _reset_to_sample(st.session_state[CURRENT_SAMPLE_STATE_KEY])
    elif format_clicked:
        _format_current_json()

    json_text = st.text_area(
        "現在のScenarioGraph",
        key=GRAPH_JSON_STATE_KEY,
        height=480,
    )
    _update_graph_from_json(json_text)


def _render_preview(preview_container: Any) -> None:
    """現在のScenarioGraphを診療画面として表示する。"""

    _render_graph_preview(preview_container, generating=False)


def _generate_graph_from_prompt(
    prompt: str,
    preview_container: Any,
) -> None:
    """GeminiでScenarioGraphを増分更新し、進行中の画面を表示する。"""

    if not prompt.strip():
        st.warning("変更内容を入力してください。")
        return

    progress = st.empty()
    for event in update_scenario_graph_incrementally(
        prompt,
        st.session_state[GRAPH_STATE_KEY],
        st.session_state[CONTEXT_STATE_KEY],
    ):
        _store_graph(event.graph, event.context, origin="gemini")
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


def _reset_to_sample(sample_name: str) -> None:
    """指定した合成サンプルを読み込み、編集中の画面を置き換える。"""

    try:
        graph, context = SAMPLE_FACTORIES[sample_name]()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    _store_graph(graph, context, origin="sample", sample_name=sample_name)


def _store_graph(
    graph: ScenarioGraph,
    context: Mapping[str, object],
    *,
    origin: GraphOrigin,
    sample_name: str | None = None,
    update_json: bool = True,
) -> None:
    """ScenarioGraphと表示コンテキストをセッションへ一貫して保存する。"""

    st.session_state[GRAPH_STATE_KEY] = graph
    st.session_state[CONTEXT_STATE_KEY] = dict(context)
    st.session_state[GRAPH_ORIGIN_STATE_KEY] = origin
    st.session_state[LOADED_AT_STATE_KEY] = _now()
    if update_json:
        st.session_state[GRAPH_JSON_STATE_KEY] = _format_graph_json(graph)
    if sample_name is not None:
        st.session_state[CURRENT_SAMPLE_STATE_KEY] = sample_name


def _format_current_json() -> None:
    """JSON入力欄を検証して整形し、診療画面へ反映する。"""

    json_text = st.session_state.get(GRAPH_JSON_STATE_KEY, "")
    try:
        graph = parse_scenario_graph_json(json_text)
    except (json.JSONDecodeError, ValidationError) as exc:
        st.error(f"JSONを整形できません: {exc}")
        return

    _store_graph(graph, _build_context_for_graph(graph), origin="manual")


def _update_graph_from_json(json_text: str) -> None:
    """有効なJSON編集だけを検出し、現在のScenarioGraphへ反映する。"""

    try:
        graph = parse_scenario_graph_json(json_text)
    except json.JSONDecodeError as exc:
        st.error(f"JSON構文エラー: {exc}")
        return
    except ValidationError as exc:
        st.error(f"ScenarioGraphの検証エラー: {exc}")
        return

    current_graph = st.session_state.get(GRAPH_STATE_KEY)
    if isinstance(current_graph, ScenarioGraph) and current_graph == graph:
        return

    _store_graph(
        graph,
        _build_context_for_graph(graph),
        origin="manual",
        update_json=False,
    )


def _build_context_for_graph(graph: ScenarioGraph) -> dict[str, object]:
    """DataNodeのモデル参照とSQLから表示コンテキストを再構築する。"""

    context: dict[str, object] = {}
    if any(data_node.model_name is not None for data_node in graph.data_nodes):
        context.update(build_dwh_context_for_graph(graph))
    if any(data_node.sql is not None for data_node in graph.data_nodes):
        context.update(build_sql_context_for_graph(graph))
    return context


def _render_graph_preview(
    preview_container: Any,
    *,
    generating: bool,
) -> None:
    """診療画面のヘッダーとタスクタブを同じ領域へ描画する。"""

    with preview_container.container():
        graph = st.session_state[GRAPH_STATE_KEY]
        if generating and not graph.tasks:
            st.info("画面構成を生成しています。")
            return
        context = st.session_state[CONTEXT_STATE_KEY]
        _render_clinical_header(graph, context)
        render_scenario_graph(
            graph,
            context,
            show_missing_reference_warnings=not generating,
        )


def _render_clinical_header(
    graph: ScenarioGraph,
    context: Mapping[str, object],
) -> None:
    """患者文脈、データ種別、情報源、更新状態を画面上部へ表示する。"""

    patient_summary = "患者識別情報は各タスク内で確認してください"
    if graph.patient_context_key is not None:
        patient_value = context.get(graph.patient_context_key)
        if patient_value is not None:
            patient_summary = str(patient_value)

    provenance_summaries = summarize_data_nodes(graph.data_nodes, context)
    source_text, latest_text = source_overview(provenance_summaries)
    origin = st.session_state.get(GRAPH_ORIGIN_STATE_KEY, "sample")
    origin_label = GRAPH_ORIGIN_LABELS.get(origin, "不明")
    loaded_at = st.session_state.get(LOADED_AT_STATE_KEY, _now())
    loaded_at_text = loaded_at.strftime("%Y-%m-%d %H:%M")
    description = graph.description or "診療タスクに必要な情報をまとめて表示します。"

    st.markdown(
        f"""
        <section class="clinical-header" aria-label="患者と診療場面">
            <div class="clinical-eyebrow">INTERACTIVE EHR</div>
            <h1>{escape(graph.title)}</h1>
            <div class="patient-context">{escape(patient_summary)}</div>
            <p>{escape(description)}</p>
        </section>
        <section class="trust-strip" aria-label="データの状態">
            <span class="trust-badge">研究用・合成データ</span>
            <span class="trust-warning">診療判断には使用できません</span>
            <span>情報源: {escape(source_text)}</span>
            <span>最終データ日時: {escape(latest_text)}</span>
            <span>画面構成: {escape(origin_label)}</span>
            <span>画面更新: {loaded_at_text}</span>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _sample_name_for_graph(graph: object) -> str:
    """既存セッションのScenarioGraphから対応するデモ名を判定する。"""

    if isinstance(graph, ScenarioGraph) and graph.id == "chronic_disease_outpatient":
        return "慢性疾患外来"
    return DEFAULT_SAMPLE_NAME


def _format_graph_json(graph: ScenarioGraph) -> str:
    """ScenarioGraphを編集しやすいインデント付きJSONへ変換する。"""

    return graph.model_dump_json(indent=4)


def _now() -> datetime:
    """画面上の取得時刻に使う日本時間を返す。"""

    return datetime.now(tz=JAPAN_TIME_ZONE)


def _inject_clinical_styles() -> None:
    """診療情報の階層と可読性を整える最小限のCSSを適用する。"""

    st.markdown(
        """
        <style>
        .stApp {
            background: #f4f7f9;
        }
        .block-container {
            max-width: 1540px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }
        .clinical-header {
            background: linear-gradient(135deg, #ffffff 0%, #f7fbfb 100%);
            border: 1px solid #dce5e8;
            border-radius: 14px 14px 0 0;
            padding: 1.3rem 1.5rem 1.15rem;
            box-shadow: 0 5px 18px rgba(26, 49, 58, 0.05);
        }
        .clinical-eyebrow {
            color: #087f7a;
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.11em;
            margin-bottom: 0.35rem;
        }
        .clinical-header h1 {
            color: #17242b;
            font-size: clamp(1.55rem, 2.2vw, 2.1rem);
            letter-spacing: -0.02em;
            line-height: 1.2;
            margin: 0;
        }
        .clinical-header p {
            color: #56666e;
            font-size: 0.9rem;
            margin: 0.4rem 0 0;
        }
        .patient-context {
            color: #263b44;
            font-size: 1rem;
            font-weight: 650;
            margin-top: 0.65rem;
        }
        .trust-strip {
            align-items: center;
            background: #eef5f5;
            border: 1px solid #d2e2e2;
            border-radius: 0 0 14px 14px;
            color: #40565e;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.78rem;
            gap: 0.45rem 1rem;
            margin-bottom: 1.15rem;
            padding: 0.7rem 1.5rem;
        }
        .trust-badge {
            background: #fff2cc;
            border: 1px solid #e8d18a;
            border-radius: 999px;
            color: #654f12;
            font-weight: 700;
            padding: 0.18rem 0.55rem;
        }
        .trust-warning {
            color: #764216;
            font-weight: 650;
        }
        section[data-testid="stSidebar"] {
            border-right: 1px solid #dce5e8;
        }
        section[data-testid="stSidebar"] textarea[aria-label="現在のScenarioGraph"] {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
                "Liberation Mono", "Courier New", monospace;
            font-size: 10px !important;
            line-height: 1.3 !important;
            tab-size: 4;
        }
        section[data-testid="stMain"] [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #dce5e8;
            border-radius: 10px;
            min-height: 106px;
            padding: 0.85rem 1rem;
        }
        section[data-testid="stMain"] [data-testid="stMetricValue"] {
            color: #17242b;
            font-size: 1.15rem;
            font-weight: 700;
            line-height: 1.35;
            overflow-wrap: anywhere;
            white-space: normal;
        }
        section[data-testid="stMain"] [data-testid="stMetricLabel"] {
            color: #53666f;
            font-size: 0.82rem;
            font-weight: 650;
        }
        section[data-testid="stMain"] [data-testid="stExpander"] {
            background: #ffffff;
            border-color: #dce5e8;
            border-radius: 10px;
            margin-top: 1.25rem;
        }
        section[data-testid="stMain"] [data-testid="stDataFrame"],
        section[data-testid="stMain"] [data-testid="stTable"] {
            background: #ffffff;
            border-radius: 10px;
        }
        section[data-testid="stMain"] [role="tablist"] {
            gap: 0.25rem;
        }
        section[data-testid="stMain"] button[role="tab"] {
            color: #4b5f68;
            font-weight: 650;
            min-height: 2.75rem;
        }
        section[data-testid="stMain"] button[role="tab"][aria-selected="true"] {
            color: #087f7a;
        }
        section[data-testid="stMain"] h4 {
            color: #263b44;
            font-size: 1rem;
            margin-top: 1.25rem;
        }
        section[data-testid="stMain"] p {
            line-height: 1.55;
        }
        @media (max-width: 760px) {
            .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
            .clinical-header,
            .trust-strip {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


main()
