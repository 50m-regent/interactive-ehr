import streamlit as st


def main() -> None:
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


if __name__ == "__main__":
    main()
