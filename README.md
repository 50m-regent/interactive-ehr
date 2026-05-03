# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

現在は初回のUI実行経路として、固定の慢性疾患外来サンプルをStreamlit上で表示できます。Gemini API認証なしで、患者概要、血圧/腎機能推移、現在処方、直近検査、過去カルテ記事を確認できます。

UIは `ScenarioGraph` JSON から描画されます。画面右側の「タスクグラフ JSON」を編集すると、valid な JSON の場合だけ左側の「UI プレビュー」に即時反映されます。不正な JSON やスキーマ検証エラーがある場合、最後に valid だったタスクグラフを描画し続けます。

## セットアップ

```bash
uv sync
```

### Gemini API (Vertex AI) の認証設定

LLM機能を使う場合は、Vertex AI のサービスアカウントキーを配置し環境変数を設定:

```bash
cp .env.example .env
# .env を編集して GOOGLE_APPLICATION_CREDENTIALS にサービスアカウントJSONへのパスを設定
```

オプション環境変数（デフォルト値あり）:
- `GEMINI_PROJECT` (デフォルト: `gemini-api-project-464304`)
- `GEMINI_LOCATION` (デフォルト: `asia-northeast1`)
- `GEMINI_MODEL` (デフォルト: `gemini-2.5-pro`)

## 起動

```bash
uv run streamlit run src/interactive_ehr/app.py
```

サイドバーの「Gemini生成」では、プロンプトから `ScenarioGraph` を構造化出力として生成できます。Gemini 生成は固定サンプルの `context` key を参照する UI/タスクグラフ構造だけを生成し、電子カルテデータ本体は生成しません。生成はタスクグラフのノード単位で進み、生成済みの部分から UI プレビューに反映されます。

## テスト

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ty check src/interactive_ehr/widgets src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py
```

`ty` の初期ゲートは手書き runtime code を中心に限定しています。全体 `uv run ty check` はより広い参考診断として利用できます。

## モデル生成

DWHテーブル設計書（`data/dwh_table_design_2025-11-01.xlsx`）からPydanticモデルを自動生成:

```bash
uv run python scripts/generate_models.py
```

## 構成

```
src/interactive_ehr/
  app.py                  -- Streamlitエントリポイント
  scenario_graph.py       -- タスクグラフモデル、JSONパース、Graphレンダラ、Gemini生成
  sample_scenarios.py     -- 固定サンプルデータ、ScenarioGraph、WidgetSpec互換API
  models/
    _base.py              -- 共通ベースモデル (DwhBaseModel)
    patient.py            -- 患者系テーブル (PATIENT)
    order_exam.py         -- 検査系テーブル (ORDER)
    order_treatment.py    -- 治療・処方系テーブル (ORDER)
    order_record.py       -- 記録・文書系テーブル (ORDER)
    mr.py                 -- カルテ記事テーブル (MR)
    nurse.py              -- 看護系テーブル (NURSE)
    other.py              -- その他テーブル (DPC等)
  widgets/
    _base.py              -- WidgetSpec基底 + WidgetType enum
    display.py            -- データ表示系 (Dataframe, Table, Metric, Json, Markdown, Text)
    chart.py              -- チャート系 (LineChart, BarChart)
    input.py              -- 入力系 (Selectbox, Multiselect, DateInput, TextInput等)
    layout.py             -- レイアウト系 (Columns, Tabs, Expander)
    renderer.py           -- WidgetSpecをStreamlitへ描画するレンダラ
  llm/
    gemini.py             -- Gemini API (Vertex AI) 呼び出しmixin
  pages/                  -- ページコンポーネント

scripts/
  generate_models.py      -- xlsxからPydanticモデルを自動生成
```
