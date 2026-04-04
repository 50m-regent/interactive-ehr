import streamlit as st


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
    st.sidebar.info("シナリオは今後追加されます")

    st.info("システムは現在開発中です。")


main()
