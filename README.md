# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

現在は初回のUI実行経路として、固定の慢性疾患外来サンプルをStreamlit上で表示できます。表示データは `data/dwh/*.csv` と慢性疾患外来用の合成サンプルから作成したローカルSQLite DBをSQLで参照します。

UIは `ScenarioGraph` JSON から描画されます。画面右側の「タスクグラフ JSON」を編集すると、valid な JSON の場合だけ左側の「UI プレビュー」に即時反映されます。不正な JSON やスキーマ検証エラーがある場合、最後に valid だったタスクグラフを描画し続けます。

## セットアップ

```bash
uv sync
uv run python scripts/build_dwh_database.py --overwrite
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

サイドバーの「Gemini生成」では、プロンプトから `ScenarioGraph` を構造化出力として生成できます。Gemini は widget node ごとに専用 data node とSQLを生成し、アプリはそのSQLをローカルSQLite DBに対して実行して `context[data_node.context_key]` にDataFrameとして保持します。電子カルテデータ本体は `ScenarioGraph` JSON には埋め込みません。

## Docker（インターネット非接続環境での実行）

依存関係・コード・サンプルDB（`data/dwh.sqlite`）をすべて1つのイメージに同梱します。ネット接続が必要なのは **イメージのビルド時のみ** で、生成後はオフライン環境へ持ち込んで動作します。Gemini APIはオフラインでは利用できませんが、起動時のサンプル慢性疾患外来シナリオ表示・タスクグラフJSON編集はGemini認証なしで動作します。

### 1. ビルド（ネット接続のある環境で）

```bash
docker build -t interactive-ehr:latest .
```

ビルド中に `scripts/build_dwh_database.py` を実行し、`data/dwh/*.csv` からSQLite DBをイメージ内に作成します。

### 2. オフライン環境へ転送

```bash
# ネット接続環境でイメージをtarに保存
docker save interactive-ehr:latest -o interactive-ehr-image.tar

# 非接続環境へtarを持ち込み、ロード
docker load -i interactive-ehr-image.tar
```

### 3. 起動

```bash
docker run -d -p 8501:8501 --name interactive-ehr interactive-ehr:latest
```

ブラウザで http://localhost:8501 を開きます。`--network none` でも動作します（外部通信は不要）。

### コードを編集する

ホスト側のソースをバインドマウントすると、編集が即時反映されます（Streamlitの自動再実行）。依存関係はイメージ内の `/opt/venv` にあるため影響しません。

```bash
docker compose up -d   # ./src と ./scripts をマウントして起動
```

プロジェクトディレクトリを持ち込めない場合は、コンテナ内で直接編集できます（`nano` / `vim` 同梱）。

```bash
docker exec -it interactive-ehr nano /app/src/interactive_ehr/app.py
```

## テスト

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ty check src/interactive_ehr/widgets src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py
```

`ty` の初期ゲートは手書き runtime code を中心に限定しています。全体 `uv run ty check` はより広い参考診断として利用できます。

## 研究スライド

定期ゼミ用のMarpスライドは `slides/YYYY-MM-DD/` で管理します。初回のみ依存関係を導入し、ブラウザでプレビューできます。

```bash
cd slides
npm ci
npm run dev
```

PDFを更新する場合:

```bash
npm run check -- YYYY-MM-DD/slides.md
npm test
npm run build -- YYYY-MM-DD/slides.md -o YYYY-MM-DD/slides.pdf
```

共有テーマは `slides/theme/research.css` です。Markdown、テーマ、使用画像、最終PDFをGitで管理します。
2026年8月14日の資料は、監査可能な臨床UI更新の研究質問を組み立てた議論、評価設計、ゼミでの相談事項を説明します。

## モデル生成

DWHテーブル設計書（`data/dwh_table_design_2025-11-01.xlsx`）からPydanticモデルを自動生成:

```bash
uv run python scripts/generate_models.py
```

## DWHサンプルCSV生成

全DWHモデルの fake データを `data/dwh/{model_name}.csv` に生成:

```bash
uv run python scripts/generate_fake_csvs.py
```

既存CSVはデフォルトでは上書きしません。再生成する場合は `--overwrite` を指定します。

## DWH SQLite DB生成

`data/dwh/*.csv` と慢性疾患外来用の合成サンプルを `data/dwh.sqlite` に読み込みます。アプリの表示データはこのDBへのSELECT SQLから取得します。

```bash
uv run python scripts/build_dwh_database.py --overwrite
```

DBファイルは生成物です。CSVを更新した場合は、上記コマンドでDBを再生成してください。

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
  generate_fake_csvs.py   -- DWHモデルごとのfake CSVを生成
  build_dwh_database.py   -- DWH CSVをSQLite DBへ読み込み
```
