# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

現在は初回のUI実行経路として、固定の慢性疾患外来サンプルをStreamlit上で表示できます。表示データは `data/dwh/*.csv` と慢性疾患外来用の合成サンプルから作成したローカルSQLite DBをSQLで参照します。

UIは `ScenarioGraph` JSON から描画されます。画面右側の「タスクグラフ JSON」を編集すると、valid な JSON の場合だけ左側の「UI プレビュー」に即時反映されます。不正な JSON やスキーマ検証エラーがある場合、最後に valid だったタスクグラフを描画し続けます。

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

## RQ1の技術評価

`data/evaluation/ui_update_benchmark.v0.4.json` は、成果物を直接変更する方式と、グラフを介して変更する方式を同じ更新要求と構造的安全要件で比較します。Geminiは呼び出しません。共通変更仕様から二方式の差分候補を決定的に生成し、独立した意味上のオラクルで正解を確認します。

固定した内容は次のとおりです。

- 開発セットは単発8件と3手の系列2件です。
- 評価セットは期間の絞り込み、必要情報の追加、表示形式、配置、タスク条件、タスクから取得と表示までをまたぐ変更を各4件、合計24件含みます。
- 評価セットの各変更には妥当な候補1件、単一違反3件、複合違反1件があり、共通変更仕様は合計120件です。
- 違反は更新範囲、安全条件、表示とデータ取得の追跡、SQL実行の4種類です。
- 主比較では直接差分方式と完全なグラフ方式へ同じ要件を実装します。
- グラフ方式では更新範囲、安全条件、追跡検査を個別に外した条件も測ります。
- 95%区間はケース単位のクラスターブートストラップで求めます。除去比較のp値はケース単位の符号反転検定とHolm補正で求めます。

評価を再実行するには、次を実行します。`--with-editable .` は、srcレイアウトの現在の作業ツリーを評価環境へ読み込むために指定しています。

```bash
uv run --with-editable . python scripts/run_ui_update_benchmark.py
```

結果は `results/evaluation/ui_update_benchmark_v0.4/` に保存されます。

- `paired_candidates.jsonl` は共通変更仕様、直接差分、グラフ差分、各チェックサムを1候補1行で記録します。
- `candidate_results.jsonl` は各候補と比較条件の受理結果を1実行1行で記録します。
- `sequence_results.jsonl` は逐次更新の受理結果と棄却時の状態保持を1手1行で記録します。
- `summary.json` は主指標、対応差、95%区間、除去比較、要件ごとの実装量を記録します。
- `report.md` は論文執筆向けの短い結果要約です。
- `run_manifest.json` は入力、実装、出力のチェックサムと実行条件を記録します。

現行v0.4は専門家確認前の合成更新要求と合成スキーマを使います。測定対象は構造的な依存関係保護です。臨床的安全性の評価、人を対象とした評価、Geminiを含むエンドツーエンド評価はまだ実施していません。

## TraceBench-EHRの実行可能性確認

CHI 2027向けのTraceBench-EHRでは、EHRSQL-2024の質問と正解SQLをMIMIC-IV Clinical Database Demo v2.2上で実行し、質問、SQL、実行結果、ScenarioGraph、Widgetを一つの追跡契約へ変換できるか確認します。EHRSQL v1.5.xはMIMIC-IIIとeICU向けのため、この確認にはMIMIC-IV向けのEHRSQL-2024を使用します。

`scripts/run_ehrsql_feasibility.py` は、train分割の回答可能ケースから異なる質問テンプレートを優先して50件を決定的に選びます。正解SQLは読み取り専用SQLite接続で実行し、単一値をMetric、それ以外をDataframeへ割り当てた最小のScenarioGraphを検証します。Geminiは呼び出しません。

外部データはGit管理外の一時ディレクトリへ置きます。生データ、質問文、正解SQL、患者単位の結果値は、このリポジトリの成果物へ保存しません。ケースID、入力のチェックサム、結果形状、実行成否、グラフ検証結果、実行マニフェストだけを保存します。

実行例は次のとおりです。`--dataset-commit` と `--code-commit` には、実際に使用する完全なcommit SHAを指定します。

```bash
git clone --depth 1 https://github.com/glee4810/ehrsql-2024.git /private/tmp/ehrsql-2024
uv run python scripts/run_ehrsql_feasibility.py \
  --annotated-data /private/tmp/ehrsql-2024/data/mimic_iv/train/annotated.json \
  --dataset-data /private/tmp/ehrsql-2024/data/mimic_iv/train/data.json \
  --database /private/tmp/ehrsql-2024/data/mimic_iv/mimic_iv.sqlite \
  --dataset-commit <EHRSQL-2024 commit SHA> \
  --code-commit <interactive-ehr commit SHA>
```

結果は `results/evaluation/ehrsql_feasibility_v0.1/` に保存されます。

- `selected_cases.json` は選定したケースIDと入力チェックサムを記録します。
- `case_results.jsonl` は結果値を含まないケース別の実行成否と結果形状を記録します。
- `summary.json` はSQL実行率、非空結果取得率、グラフ検証率を集計します。
- `report.md` は実験結果の短い要約です。
- `run_manifest.json` は入力、実装、出力のチェックサムと実行条件を記録します。

この確認から臨床上の安全性、使いやすさ、認知負荷、臨床転帰、他施設への一般化は主張しません。

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
uv run streamlit run src/interactive_ehr/app.py
```

サイドバーの「Gemini生成」では、プロンプトから `ScenarioGraph` を構造化出力として生成できます。Gemini は widget node ごとに専用 data node とSQLを生成し、アプリはそのSQLをローカルSQLite DBに対して実行して `context[data_node.context_key]` にDataFrameとして保持します。電子カルテデータ本体は `ScenarioGraph` JSON には埋め込みません。

## Docker（インターネット非接続環境での実行）

依存関係・コード・サンプルDB（`data/dwh.sqlite`）をすべて1つのイメージに同梱します。ネット接続が必要なのは **イメージのビルド時のみ** で、生成後はオフライン環境へ持ち込んで動作します。起動時のサンプル慢性疾患外来シナリオ表示・タスクグラフJSON編集はGemini認証なしで動作します。閉域内に Gemini プロキシがある場合は `-e GEMINI_PROXY_URL=...` を付けて起動するとタスクグラフ生成も利用できます（上記「閉域ネットワーク向けプロキシモード」参照）。

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
uv run ty check src/interactive_ehr/widgets src/interactive_ehr/evaluation src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py
```

`ty` の初期ゲートは手書き runtime code を中心に限定しています。全体 `uv run ty check` はより広い参考診断として利用できます。

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
  evaluation/
    benchmark_analysis.py -- UI更新ベンチマークの統計集計と成果物出力
    case_manifest.py      -- 合成症例ペアの定義と準備状態の監査
    ehrsql_feasibility.py -- EHRSQL-2024の選定、SQL実行、グラフ検証
    task_model.py         -- 診療タスクの基準モデルと情報追跡監査
    update_benchmark.py   -- 共通変更仕様、二方式の差分生成、検査、実行器
  pages/                  -- ページコンポーネント

data/evaluation/
  ito_clinical_tasks.v1.json -- 麻酔科術前外来T1〜T7のdraft基準モデル
  ito_case_manifest.v0.1.json -- 比較実験用の合成症例ペアテンプレート
  ui_update_benchmark.v0.4.json -- RQ1技術評価の固定入力

scripts/
  generate_models.py      -- xlsxからPydanticモデルを自動生成
  generate_fake_csvs.py   -- DWHモデルごとのfake CSVを生成
  build_dwh_database.py   -- DWH CSVをSQLite DBへ読み込み
  audit_clinical_task_trace.py -- 診療タスクとUIの情報追跡監査
  audit_evaluation_case_manifest.py -- 合成症例ペアの準備状態監査
  run_ehrsql_feasibility.py -- EHRSQL-2024の50件実行可能性確認
  run_ui_update_benchmark.py -- RQ1技術評価の実行と結果保存

results/evaluation/ui_update_benchmark_v0.4/
  run_manifest.json       -- 再現条件とチェックサム
  report.md               -- 技術評価結果の要約
  summary.json            -- 統計集計と実装量
```
