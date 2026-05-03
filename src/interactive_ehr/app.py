import streamlit as st

from interactive_ehr.sample_scenarios import get_chronic_disease_scenario
from interactive_ehr.widgets.renderer import render_widgets


def main() -> None:
    """Streamlitアプリのエントリポイント。ページ設定と初期UIを構築する。"""
    st.set_page_config(
        page_title="Interactive EHR",
        page_icon="🏥",
        layout="wide",
    )

    st.title("Interactive EHR")
    st.markdown("タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム")

    st.sidebar.header("シナリオ選択")
    scenario = st.sidebar.selectbox(
        "固定サンプル",
        ["慢性疾患を持つ高齢患者の外来診察"],
    )
    st.sidebar.caption("API認証なしで表示できる検証用ダミーデータです。")

    if scenario == "慢性疾患を持つ高齢患者の外来診察":
        widgets, context = get_chronic_disease_scenario()
        render_widgets(widgets, context)


main()
