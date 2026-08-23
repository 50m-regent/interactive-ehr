"""データ来歴の要約処理を検証する。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from interactive_ehr.provenance import (
    source_names_for_node,
    source_overview,
    summarize_data_nodes,
)
from interactive_ehr.scenario_graph import DataNode


def test_summarize_data_nodes_reports_source_date_count_and_missingness() -> None:
    """情報源、最新日、件数、欠損を一つの要約へまとめる。"""

    data_node = DataNode(
        id="labs",
        context_key="lab_rows",
        data_type="dataframe",
        description="検査値推移",
        sql=(
            'SELECT "検査日", MAX("値") AS "値" FROM "検体検査結果" '
            'GROUP BY "検査日"'
        ),
    )
    context = {
        "lab_rows": pd.DataFrame(
            {
                "検査日": ["2026-04-01", "2026-05-20"],
                "値": [1.1, None],
            }
        )
    }

    summary = summarize_data_nodes([data_node], context)[0]

    assert summary.sources == ("検体検査結果",)
    assert summary.latest_recorded_at == datetime(2026, 5, 20)
    assert summary.row_count == 2
    assert summary.status == "一部欠損"
    assert summary.transformation == "集約・抽出"
    assert summary.as_row()["最終データ日時"] == "2026-05-20"


def test_source_names_for_node_collects_joined_tables_without_duplicates() -> None:
    """SQLのFROMとJOINから重複のない情報源名を取得する。"""

    data_node = DataNode(
        id="profile",
        context_key="profile",
        data_type="scalar",
        description="患者背景",
        sql=(
            'SELECT p."患者ID" FROM "患者基本" p '
            'LEFT JOIN "患者プロフィール" pp ON p."患者ID"=pp."患者ID" '
            'LEFT JOIN "患者基本" p2 ON p2."患者ID"=p."患者ID"'
        ),
    )

    assert source_names_for_node(data_node) == ("患者基本", "患者プロフィール")


def test_source_overview_limits_names_and_uses_latest_date() -> None:
    """タスク上部の要約を短くし、確認できる最新日を採用する。"""

    nodes = [
        DataNode(
            id=f"data_{index}",
            context_key=f"rows_{index}",
            data_type="dataframe",
            description=f"表示{index}",
            sql=f'SELECT "検査日" FROM "情報源{index}"',
        )
        for index in range(4)
    ]
    context = {
        f"rows_{index}": pd.DataFrame({"検査日": [f"2026-05-{index + 1:02d}"]})
        for index in range(4)
    }

    source_text, latest_text = source_overview(summarize_data_nodes(nodes, context))

    assert source_text == "情報源0、情報源1、情報源2 ほか1件"
    assert latest_text == "2026-05-04"
