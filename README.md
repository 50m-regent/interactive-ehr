# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

現在は麻酔科術前外来と慢性疾患外来の合成サンプルをStreamlit上で切り替えて表示できます。初期表示は麻酔科術前外来です。表示データは `data/dwh/*.csv` と慢性疾患外来用の合成サンプルから作成したローカルSQLite DBをSQLで参照します。

診療画面の上部には患者文脈、合成データであること、画面構成の作成元、画面更新時刻を表示します。説明文を重ねず、見出しとデータの配置で確認順序が分かる構成です。各タスクには情報源と最終データ日時の要約があり、「情報源と取得条件」を開くと件数、欠損状態、参照テーブル、読み取り専用SQLを確認できます。表示値とGeminiが生成する画面構成を区別して確認できます。

UIは `ScenarioGraph` JSON から描画されます。サイドバーは初期状態で閉じています。サイドバーの「UI生成・編集ツール」を開くと、Geminiによる画面構成の更新とScenarioGraph JSONの編集ができます。有効なJSONだけを診療画面へ反映し、検証エラーがある場合は最後に有効だった画面を描画し続けます。

折れ線グラフは、日付や数値を横軸の値に応じた間隔で表示します。線上には実測点を示すドットを重ね、マウスを合わせると日付、系列、値を確認できます。

研究評価では、診療タスクとUIのタブ構成を分けて扱います。麻酔科術前外来について、ヒアリングで得たT1〜T7の確認・判断、依存関係、完了条件、必要情報を `data/evaluation/ito_clinical_tasks.v1.json` に保存しています。このモデルは専門家確認前の `draft` であり、現時点では医学的な正解データとして扱いません。

`interactive_ehr.evaluation` は、臨床タスクモデルの検証と、必要情報が現在の `ScenarioGraph` のDataNodeまで追跡できるかの監査を提供します。これにより、UIの操作時間を測る前に、必要情報の欠落を明示できます。

比較実験用の合成症例は `data/evaluation/ito_case_manifest.v0.1.json` で管理します。症例ペア、設問、採点基準、難易度、専門家確認の状態を記録し、未確定の項目があればパイロット実験を止めます。参照する臨床タスクモデルの専門家確認と、対応するScenarioGraphファイルの存在も開始条件です。現在のファイルは臨床内容を未記入にしたテンプレートであり、実験には利用できません。

麻酔科術前外来のdraftモデルと現在のUIを照合するには、次を実行します。

```bash
uv run python scripts/audit_clinical_task_trace.py \
  data/evaluation/ito_clinical_tasks.v1.json \
  data/scenarios/ito.json
```

合成症例ペアの準備状態を確認するには、次を実行します。準備未完了の場合は終了コード1を返します。

```bash
uv run python scripts/audit_evaluation_case_manifest.py \
  data/evaluation/ito_case_manifest.v0.1.json \
  data/evaluation/ito_clinical_tasks.v1.json
```

## セットアップ

```bash
uv sync
uv run --with-editable . python scripts/build_dwh_database.py --overwrite
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

### 閉域ネットワーク向けプロキシモード

Vertex AI に到達できない閉域環境では、環境変数 `GEMINI_PROXY_URL` を設定すると
ベンダー提供の Gemini プロキシ経由で生成します（サービスアカウント認証は不要。
未設定なら従来どおり Vertex AI を使用）。プロキシには JSON Schema 構造化出力の
機能がないため、スキーマをプロンプトに埋め込み、返却 JSON を Pydantic で検証します。

- `GEMINI_PROXY_URL`: プロキシURL（例: `http://192.168.197.130:3000/api/gemini`）
- `GEMINI_MODEL` (プロキシモードのデフォルト: `gemini-2.5-flash-lite`)
- `GEMINI_PROXY_MAX_OUTPUT_TOKENS` (デフォルト: `8192`)
- `GEMINI_PROXY_TEMPERATURE` (デフォルト: `0.2`)
- `GEMINI_PROXY_TIMEOUT` (デフォルト: `300` 秒)

## 起動

```bash
uv run --with-editable . python -m streamlit run src/interactive_ehr/app.py
```

サイドバーの「UI生成・編集ツール」では、入力した変更内容から `ScenarioGraph` を構造化出力として生成できます。Gemini は widget node ごとに専用 data node とSQLを生成し、アプリはそのSQLをローカルSQLite DBに対して実行して `context[data_node.context_key]` にDataFrameとして保持します。電子カルテデータ本体は `ScenarioGraph` JSON には埋め込みません。

## Docker（インターネット非接続環境での実行）

依存関係・コード・サンプルDB（`data/dwh.sqlite`）をすべて1つのイメージに同梱します。ネット接続が必要なのは **イメージのビルド時のみ** で、生成後はオフライン環境へ持ち込んで動作します。起動時のサンプル慢性疾患外来シナリオ表示・タスクグラフJSON編集はGemini認証なしで動作します。閉域内に Gemini プロキシがある場合は `-e GEMINI_PROXY_URL=...` を付けて起動するとタスクグラフ生成も利用できます（上記「閉域ネットワーク向けプロキシモード」参照）。

### 1. Linux AMD64イメージをビルド（ネット接続のある環境で）

```bash
docker buildx build \
  --platform linux/amd64 \
  --load \
  -t interactive-ehr:2026-08-24-ui \
  -t interactive-ehr:latest \
  .
```

ビルド中に `scripts/build_dwh_database.py` を実行し、`data/dwh/*.csv` からSQLite DBをイメージ内に作成します。
イメージに入るのは合成データだけです。院内DWHは院内環境でバックアップと整合性確認を行ってから反映します。

### 2. オフライン環境へ転送

```bash
# ネット接続環境で圧縮イメージとチェックサムを作成
mkdir -p dist
docker save interactive-ehr:2026-08-24-ui interactive-ehr:latest \
  | gzip -n > dist/interactive-ehr-amd64-20260824.tar.gz
cd dist
shasum -a 256 interactive-ehr-amd64-20260824.tar.gz \
  > interactive-ehr-amd64-20260824.tar.gz.sha256

# 非接続環境へ2ファイルを持ち込み、検証してロード
sha256sum -c interactive-ehr-amd64-20260824.tar.gz.sha256
docker load -i interactive-ehr-amd64-20260824.tar.gz
```

稼働中の院内DWHを保持したままUIだけを更新する手順は `DEPLOY.md` にあります。

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
uv run --with-editable . python -m pytest tests/ -v
uv run ruff check .
uv run ty check src/interactive_ehr/widgets src/interactive_ehr/evaluation src/interactive_ehr/provenance.py src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py
```

`ty` の初期ゲートは手書き runtime code を中心に限定しています。全体 `uv run ty check` はより広い参考診断として利用できます。

## 発表資料

Research Meeting資料は `slides/2026-08-24/` にあります。日本語版は `slides.md`、英語版は `slides.en.md` です。
Markdownを編集した後は、次のコマンドで検査とPDF出力を行います。

```bash
cd slides
npm ci
npm test
npm run check -- 2026-08-24/slides.md
npm run build -- 2026-08-24/slides.md -o 2026-08-24/slides.pdf
npm run check -- 2026-08-24/slides.en.md
npm run build -- 2026-08-24/slides.en.md -o 2026-08-24/slides.en.pdf
```

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
uv run --with-editable . python scripts/build_dwh_database.py --overwrite
```

DBファイルは生成物です。CSVを更新した場合は、上記コマンドでDBを再生成してください。

## 構成

```
src/interactive_ehr/
  app.py                  -- Streamlitエントリポイント
  provenance.py           -- 情報源、データ時点、件数、欠損状態の表示用要約
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
  evaluation/
    case_manifest.py      -- 合成症例ペアの定義と準備状態の監査
    task_model.py         -- 診療タスクの基準モデルと情報追跡監査
  pages/                  -- ページコンポーネント

data/evaluation/
  ito_clinical_tasks.v1.json -- 麻酔科術前外来T1〜T7のdraft基準モデル
  ito_case_manifest.v0.1.json -- 比較実験用の合成症例ペアテンプレート
data/scenarios/
  ito.json                -- 麻酔科術前外来の初期表示ScenarioGraph

slides/
  2026-08-24/             -- Research Meeting資料と画面画像
  theme/                  -- Marp共通テーマ

dist/                     -- Git管理しないDocker配布物

scripts/
  generate_models.py      -- xlsxからPydanticモデルを自動生成
  generate_fake_csvs.py   -- DWHモデルごとのfake CSVを生成
  build_dwh_database.py   -- DWH CSVをSQLite DBへ読み込み
  audit_clinical_task_trace.py -- 診療タスクとUIの情報追跡監査
  audit_evaluation_case_manifest.py -- 合成症例ペアの準備状態監査
```
