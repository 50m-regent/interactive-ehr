# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 作業場所

ローカル作業はこの`interactive-ehr/`だけで行います。追加のcloneやworktreeは作らず、作業用ブランチを順番に切り替えます。複数のチャットから同時に変更しないでください。

## 作業はIssue・Notion・PRへ記録する

リポジトリを変更する前に、対応するGitHub Issueを確認します。既存Issueがなければ作成し、Notionのタスクまたは成果物と相互にリンクします。PR本文にはIssueとNotionページを記載してください。作業終了前に差分、検証結果、開いているIssueとPRを見直し、セルフレビューを通過したPRは統合します。重複や不要になったものは、理由を残して閉じます。

PRの統合によってIssueが完了する場合は`Closes #番号`、作業が残る場合は`Refs #番号`を使います。倫理確認、専門家確認、外部レビュー、ユーザーの判断が残るPRは統合せず、必要な確認内容をIssue、PR、Notionへ記録します。状態を変えない調査や閲覧だけの作業では、Issueの作成は不要です。

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

現在は麻酔科術前外来と慢性疾患外来の合成サンプルをStreamlit上で切り替えて表示できます。初期表示は麻酔科術前外来です。表示データは `data/dwh/*.csv` と慢性疾患外来用の合成サンプルから作成したローカルSQLite DBをSQLで参照します。

診療画面の上部には患者文脈、合成データであること、画面構成の作成元、画面更新時刻を表示します。各タスクには情報源と最終データ日時の要約があり、「情報源と取得条件」を開くと件数、欠損状態、参照テーブル、読み取り専用SQLを確認できます。表示値とGeminiが生成する画面構成を区別して確認できます。

UIは `ScenarioGraph` JSON から描画されます。サイドバーは初期状態で閉じています。「UI生成・編集ツール」を開くと、Geminiによる画面構成の更新とScenarioGraph JSONの編集ができます。有効なJSONだけを診療画面へ反映し、検証エラーがある場合は最後に有効だった画面を描画し続けます。

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

## 層間整合性評価の実行可能性確認

CHI 2027向けの層間整合性評価では、EHRSQL-2024の質問と正解SQLをMIMIC-IV Clinical Database Demo v2.2上で実行し、質問、SQL、実行結果、ScenarioGraph、Widgetを一つの追跡契約へ変換できるか確認します。EHRSQL v1.5.xはMIMIC-IIIとeICU向けのため、この確認にはMIMIC-IV向けのEHRSQL-2024を使用します。

`scripts/run_ehrsql_feasibility.py` は、train分割の回答可能ケースから異なる質問テンプレートを優先して50件を決定的に選びます。正解SQLは読み取り専用SQLite接続で実行し、単一値をMetric、それ以外をDataframeへ割り当てた最小のScenarioGraphを検証します。Geminiは呼び出しません。

外部データはGit管理外の一時ディレクトリへ置きます。生データ、質問文、正解SQL、患者単位の結果値は、このリポジトリの成果物へ保存しません。ケースID、入力のチェックサム、結果形状、実行成否、グラフ検証結果、実行マニフェストだけを保存します。

EHRSQL-2024はCC BY 4.0で公開されています。MIMIC-IV Clinical Database Demo v2.2由来の情報を含み、同データはOpen Database License v1.0で利用できます。成果物を公開する場合は、[EHRSQL-2024](https://github.com/glee4810/ehrsql-2024)と[MIMIC-IV Clinical Database Demo v2.2](https://physionet.org/content/mimic-iv-demo/2.2/)を明記します。

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

2026年8月27日に、EHRSQL-2024のcommit `f9e1aa02160d39e3f8df52bf5c69c5cf2e472499` とinteractive-ehrのcommit `74dcc2f7f35072e78b69641bebd04e33ced00d87` を使ってv0.1を実行しました。

- 異なる質問テンプレートから50件を選定しました。
- 正解SQLは50件すべてで実行に成功しました。
- 49件で非空結果を取得し、1件は列を持つ空結果でした。
- 50件すべてでScenarioGraphの検証に成功しました。
- Metricへ40件、Dataframeへ10件を割り当てました。
- タイムアウト、SQLエラー、書き込みSQL、グラフ検証エラーはありませんでした。

この結果は、選定したtrain分割50件を現行ScenarioGraphとWidgetへ機械的に変換できることを示します。全ケースへの適用可能性や、表示方法の臨床的な妥当性はこの確認だけでは判断できません。この確認を踏まえ、正式技術評価v1.1では空結果の扱い、対象ケース、変異規則、独立オラクル、開発・評価分割を固定しました。

この確認から臨床上の安全性、使いやすさ、認知負荷、臨床転帰、他施設への一般化は主張しません。

## 層間整合性の正式技術評価

`data/evaluation/tracebench_ehr.v1.json` は、EHRSQL-2024とMIMIC-IV Clinical Database Demo v2.2を用いる正式技術評価v1.1の条件を固定します。実装は `src/interactive_ehr/evaluation/tracebench_ehr.py`、統計集計は `src/interactive_ehr/evaluation/tracebench_analysis.py`、実行入口は `scripts/run_tracebench_ehr.py` です。Geminiや外部モデルは使用しません。

評価対象の不整合は次の8種類です。

- 対象患者
- 対象項目
- 期間
- 集約方法
- 情報源
- 結果とWidgetの表示方式
- DataNodeとWidgetの接続
- SQL更新後に古い実行結果が残る部分更新

結果とWidgetの表示方式は、基準がMetricならDataframeへ、DataframeならTableへ変えます。SQL、実行結果、列、結果値は維持し、描画可能な表示方式と基準契約の対応だけを壊します。v1.0で予定していた列順の変異は、validationで成功したSQL結果がすべて1列だったため使いません。

各候補へ次の4条件を適用します。

- 局所検査
- 成果物ごとの契約
- 質問からWidgetまでの対応を持つグラフ契約
- グラフと同じ契約内容を持つ平坦なサイドカー契約

主要評価は、不整合の流出率と妥当な更新の受理率です。副次評価として、問題箇所の特定率、1回の契約ベース修復成功率、検証時間を測ります。条件間の対応差と95%信頼区間は、質問テンプレート単位のクラスターブートストラップ10,000回で求めます。

2026年8月27日にvalidation全件でv1.1パイロットを実行しました。

- 全1,163件のうち、正解SQLを持つ931件を対象にしました。
- SQL実行と基準グラフ検証は924件で成功し、成功率は99.25%でした。
- 758組、6,064回の候補検証を実行しました。
- 各変異は34から133テンプレートあり、事前の下限である10テンプレートと30候補を満たしました。
- オラクルと候補ラベルの不一致は0件でした。
- グラフ契約とサイドカー契約の判定不一致は0件でした。
- 質問文、SQL、患者ID、結果値を保存していないことを確認しました。

このパイロットで停止条件を通過した後、評価コードと設定をcommit `baa82075b6bfd3bad70b2ca2bc4ae4852db91beb` で固定しました。固定後のtest分割は一度だけ実行しました。

- 全1,167件のうち、正解SQLを持つ934件を対象にし、回答不能233件を主評価から除外しました。
- 934件すべてでSQL実行と基準成果物の構築に成功しました。
- 134テンプレートから763組を作り、6,104回の候補検証を実行しました。
- 局所検査は注入した不整合763件をすべて受理し、不整合流出率は100%でした。
- 成果物ごとの契約は367件を受理し、不整合流出率は48.10%でした。
- グラフ契約とサイドカー契約の不整合流出率は0%でした。
- 全条件で妥当な更新763件をすべて受理し、妥当更新受理率は100%でした。
- グラフ契約と局所検査の不整合流出率の差は-100.00ポイント、95%区間は[-100.00, -100.00]ポイントでした。
- グラフ契約と成果物ごとの契約の差は-48.10ポイント、95%区間は[-49.56, -46.53]ポイントでした。
- グラフ契約とサイドカー契約の差は0ポイントでした。
- グラフ契約とサイドカー契約は、問題箇所の特定と1回の修復に763件すべて成功しました。
- オラクルと候補ラベルの不一致、グラフ契約とサイドカー契約の判定不一致はいずれも0件でした。

正式結果は `results/evaluation/tracebench_ehr_v1.1/test/`、パイロット結果は `results/evaluation/tracebench_ehr_v1.1/validation/` に保存しています。完全な変異別集計と実行時間は各 `summary.json` を参照してください。

保存済みの正式結果を表計算ソフトで確認する場合は、元のJSONとJSON Linesを変更せずTSVへ変換します。この処理は正式評価を再実行しません。元成果物のチェックサム、候補単位から再計算した主要指標、95%信頼区間を照合してから出力します。

```bash
uv run python scripts/export_tracebench_tsv.py \
  results/evaluation/tracebench_ehr_v1.1/test
```

結果は `results/evaluation/tracebench_ehr_v1.1/test/tsv/` に保存されます。

- `build_summary.tsv` は対象件数、基準成果物の構築結果、変異別の生成数を1行にまとめます。
- `condition_metrics.tsv` は4種類の検査方法の主要指標と副次指標を記録します。
- `mutation_metrics.tsv` は8種類の不整合と4種類の検査方法の組み合わせを記録します。
- `paired_differences.tsv` は条件間の対応差と95%信頼区間を記録します。
- `pair_manifest.tsv` は763組のハッシュ化した識別子、変異種類、チェックサムを記録します。
- `candidate_results.tsv` は6,104回の受理、特定、修復、検証時間を記録します。
- `export_manifest.json` は変換コード、元成果物、TSVのチェックサム、行数、照合結果を記録します。

各TSVの用途、全カラム、値の読み方は `results/evaluation/tracebench_ehr_v1.1/test/tsv/README.md` にまとめています。

TSVには質問文、SQL、患者ID、患者ごとの結果値を含めません。`mutation_kind`列の`patient`は対象患者を変える不整合の種類を表すラベルであり、患者IDではありません。

validationパイロットの実行例は次のとおりです。

```bash
uv run python scripts/run_tracebench_ehr.py \
  --split validation \
  --annotated-data <EHRSQL-2024>/data/mimic_iv/valid/annotated.json \
  --dataset-data <EHRSQL-2024>/data/mimic_iv/valid/data.json \
  --database <EHRSQL-2024>/data/mimic_iv/mimic_iv.sqlite \
  --config data/evaluation/tracebench_ehr.v1.json \
  --code-commit <interactive-ehr commit SHA> \
  --output-dir results/evaluation/tracebench_ehr_v1.1/validation
```

出力は次のとおりです。

- `pair_manifest.jsonl` はケースID、変異種類、テンプレートと候補のチェックサムを記録します。
- `candidate_results.jsonl` は候補と条件ごとの受理、特定、修復結果を記録します。
- `build_summary.json` は基準実行、空結果、変異別の件数を記録します。
- `summary.json` は主要評価、副次評価、変異別集計、95%信頼区間を記録します。
- `report.md` はCHI原稿向けの短い結果要約です。
- `run_manifest.json` は入力、コード、設定、出力のチェックサムを記録します。

成果物には、生データ、質問文、正解SQL、患者ID、患者単位の結果値を保存しません。匿名化済みデモデータ上の技術評価であり、臨床上の安全性、使いやすさ、認知負荷、臨床転帰、実運用、他施設への一般化は評価していません。

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

- `GEMINI_PROXY_URL`: プロキシURL（例: `http://gemini-proxy.example:3000/api/gemini`）
- `GEMINI_MODEL` (プロキシモードのデフォルト: `gemini-2.5-flash-lite`)
- `GEMINI_PROXY_MAX_OUTPUT_TOKENS` (デフォルト: `8192`)
- `GEMINI_PROXY_TEMPERATURE` (デフォルト: `0.2`)
- `GEMINI_PROXY_TIMEOUT` (デフォルト: `300` 秒)

## 起動

```bash
uv run streamlit run src/interactive_ehr/app.py
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

ビルド中に `scripts/build_dwh_database.py` を実行し、`data/dwh/*.csv` からSQLite DBをイメージ内に作成します。イメージに入るのは合成データだけです。院内DWHは院内環境でバックアップと整合性確認を行ってから反映します。

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
uv run pytest tests/ -v
uv run ruff check .
uv run ty check src/interactive_ehr/widgets src/interactive_ehr/evaluation src/interactive_ehr/provenance.py src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py
```

`ty` の初期ゲートは手書き runtime code を中心に限定しています。全体 `uv run ty check` はより広い参考診断として利用できます。

## 口頭試問原稿

`papers/oral-examination-2026/`には、電子カルテ利用時の認知負荷軽減を軸に研究全体を説明するLaTeX原稿とPDFがあります。タスクグラフによるUI生成、院内実装、完了した層間整合性の技術評価、卒業までに行う現行電子カルテとのユーザー評価を扱います。編集元のLaTeXと確認用PDFだけを版管理します。

```bash
cd papers/oral-examination-2026
latexmk main-revised.tex
```

## CHI 2027 Papers 確認稿

`papers/chi-2027/`には、正式技術評価の結果を反映した匿名・単一カラムの日本語版と英語版があります。評価基盤には固有名称を付けません。診療シナリオによって必要な情報と表示が変わることを出発点に、層間整合性を妥当な臨床UXの前提として位置付け、比較結果、検知メカニズム、利用者価値へつなぐための評価課題を整理しています。図はHTML内のSVGから日本語版と英語版を再生成できます。編集元のLaTeXと確認用PDFだけを版管理します。

```bash
cd papers/chi-2027
make
```

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
2026年8月24日のResearch Meeting資料は日本語版と英語版があり、患者文脈、情報源、データ時点、読み取り専用SQLの確認方法と院内配布手順を説明します。
2026年8月14日の資料は、再整理した研究質問、CHI採択研究6件を参考にした評価案、月末の矢部先生との相談、9月10日のCHI提出目標を説明します。
2026年8月28日の資料は、EHRSQL-2024とMIMIC-IV Demo v2.2を使った提案手法の技術評価について、実験方法、結果、主張できる範囲を説明します。
2026年8月31日の資料は、正式技術評価の結果と投稿範囲を整理し、人を対象とする評価を倫理審査と実施許可後の別研究として位置付けます。

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
    benchmark_analysis.py -- UI更新ベンチマークの統計集計と成果物出力
    case_manifest.py      -- 合成症例ペアの定義と準備状態の監査
    ehrsql_feasibility.py -- EHRSQL-2024の選定、SQL実行、グラフ検証
    tracebench_analysis.py -- 層間整合性評価の統計集計と成果物出力
    tracebench_ehr.py     -- 正式評価の候補生成、契約検査、修復
    task_model.py         -- 診療タスクの基準モデルと情報追跡監査
    update_benchmark.py   -- 共通変更仕様、二方式の差分生成、検査、実行器
  pages/                  -- ページコンポーネント

data/evaluation/
  ito_clinical_tasks.v1.json -- 麻酔科術前外来T1〜T7のdraft基準モデル
  ito_case_manifest.v0.1.json -- 比較実験用の合成症例ペアテンプレート
  ui_update_benchmark.v0.4.json -- RQ1技術評価の固定入力

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
  run_ehrsql_feasibility.py -- EHRSQL-2024の50件実行可能性確認
  run_tracebench_ehr.py   -- 層間整合性評価のvalidationとtestの実行
  export_tracebench_tsv.py -- 保存済みの層間整合性評価結果をTSVへ変換
  run_ui_update_benchmark.py -- RQ1技術評価の実行と結果保存

results/evaluation/ui_update_benchmark_v0.4/
  run_manifest.json       -- 再現条件とチェックサム
  report.md               -- 技術評価結果の要約
  summary.json            -- 統計集計と実装量

results/evaluation/ehrsql_feasibility_v0.1/
  selected_cases.json     -- 選定ケースIDと入力チェックサム
  case_results.jsonl      -- 値を含まないケース別実行結果
  summary.json            -- SQL実行、非空結果、グラフ検証の集計
  report.md               -- 実行可能性確認の結果要約
  run_manifest.json       -- 入力、コード、出力の再現条件

results/evaluation/tracebench_ehr_v1.1/
  validation/             -- 評価規則を固定する前の全件パイロット
  test/                   -- 固定commitで一度だけ実行した正式結果

papers/oral-examination-2026/
  main.tex                -- 2026年8月27日時点の口頭試問原稿
  references.bib          -- 原稿で参照する文献
  output/pdf/Hirata_Ren.pdf -- 検証済みPDF

papers/chi-2027/
  main-ja.tex             -- CHI 2027 Papersの日本語確認稿
  main-en.tex             -- CHI 2027 Papersの英語確認稿
  figures/src/            -- HTMLで編集する図の原稿
  figures/svg/            -- HTMLから抽出したSVG
  figures/pdf/            -- LaTeXへ読み込む図
  scripts/                -- 図をSVGへ変換するスクリプト
  references.bib          -- 原稿で参照する文献
  output/pdf/chi-2027-ja-review.pdf -- 検証済みPDF
  output/pdf/chi-2027-en-review.pdf -- 検証済みPDF
```
