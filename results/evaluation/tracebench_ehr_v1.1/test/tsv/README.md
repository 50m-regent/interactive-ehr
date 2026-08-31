# TraceBench-EHR v1.1 正式評価TSVの説明

このフォルダには、TraceBench-EHR v1.1のtest分割で得た正式評価結果を、表計算ソフトで確認できるように変換したTSVがあります。元のJSONとJSON Linesは変更していません。

TSVには、質問文、SQL、患者ID、患者ごとの結果値を含めていません。識別子とチェックサムから元の内容を復元することもできません。

## はじめに見るファイル

CHI原稿の結果を確認するときは、次の順で見ると全体をつかみやすくなります。

1. `condition_metrics.tsv`で4種類の検査方法を比較します。
2. `mutation_metrics.tsv`で8種類の不整合ごとの違いを確認します。
3. `paired_differences.tsv`で条件間の対応差と95%信頼区間を確認します。
4. 詳しい根拠が必要なときだけ、`candidate_results.tsv`と`pair_manifest.tsv`を見ます。

`build_summary.tsv`は対象件数とペア作成の状況を確認するための表です。

## 共通の読み方

- 率は0から1の小数です。`0.481`は48.1%を表します。
- 真偽値は`true`または`false`です。
- 空欄は、その行では値を計算しないことを表します。`false`とは意味が異なります。
- 件数はヘッダーを除いたデータ行を数えます。
- `checksum`が付く列はSHA-256チェックサムで、64文字の16進数です。
- `pair_id`、`source_case_id`、`target_case_id`は24文字の16進数です。患者IDではありません。

## 検査方法の値

`condition`列には次の値が入ります。

| 値 | 説明 |
|---|---|
| `local_checks` | 各成果物のSQL構文、結果の形、参照先の存在などを個別に検査します。 |
| `artifact_contracts` | 局所検査に加えて、SQLと情報源、SQLと実行結果、実行結果とWidgetの自己整合性を検査します。 |
| `graph_contract` | 局所検査と成果物ごとの検査に加えて、質問、SQL、実行結果、Widgetをグラフ上の契約に沿って検査します。 |
| `sidecar_contract` | グラフ契約と同じ期待値を、平坦なサイドカー契約として検査します。 |

## 不整合の種類

`mutation_kind`列には次の値が入ります。

| 値 | 説明 |
|---|---|
| `patient` | SQLが参照する対象患者を別の値へ変えた不整合です。 |
| `clinical_item` | 薬剤、検査、診療項目など、SQLが参照する対象項目を変えた不整合です。 |
| `time_constraint` | SQLの期間や時点の条件を変えた不整合です。 |
| `aggregation_operation` | 件数、最大値、平均など、SQLの集約方法を変えた不整合です。 |
| `information_source` | SQLが参照するテーブルと、成果物に記録した情報源を食い違わせた不整合です。 |
| `widget_mapping` | SQL結果に対応するWidgetの表示方式を変えた不整合です。 |
| `data_widget_connection` | Widgetを、目的のDataNodeとは別のDataNodeへ接続した不整合です。 |
| `stale_result` | SQLを更新した後も、更新前の実行結果を残した不整合です。 |

## build_summary.tsv

test分割の対象件数、基準成果物の構築結果、不整合ペアの作成状況を1行にまとめた表です。現在のファイルは1行です。

| カラム | 型 | 説明 |
|---|---|---|
| `split` | 文字列 | 評価に使ったデータ分割です。現在は`test`です。 |
| `total_case_count` | 整数 | test分割に含まれる全ケース数です。回答不能ケースも含みます。 |
| `answerable_case_count` | 整数 | 正解SQLが`null`ではなく、回答可能と判定したケース数です。 |
| `answerable_template_count` | 整数 | 回答可能ケースに含まれる質問テンプレートの種類数です。 |
| `baseline_success_count` | 整数 | 正解SQLを実行し、基準成果物の構築に成功したケース数です。 |
| `baseline_success_rate` | 小数 | `baseline_success_count / answerable_case_count`です。 |
| `baseline_failure_count` | 整数 | 正解SQLの実行または基準成果物の構築に失敗したケース数です。 |
| `row_count_capped_count` | 整数 | SQL結果が保存上限を超え、上限行数で打ち切った基準成果物の数です。 |
| `empty_result_count` | 整数 | SQLは成功したものの、結果が0行だった基準成果物の数です。 |
| `pair_count` | 整数 | 最終的に作成した更新ペアの総数です。1ペアには妥当候補と不整合候補が1件ずつあります。 |
| `pair_count_patient` | 整数 | 対象患者の不整合で作成したペア数です。 |
| `pair_count_clinical_item` | 整数 | 対象項目の不整合で作成したペア数です。 |
| `pair_count_time_constraint` | 整数 | 期間の不整合で作成したペア数です。 |
| `pair_count_aggregation_operation` | 整数 | 集約方法の不整合で作成したペア数です。 |
| `pair_count_information_source` | 整数 | 情報源の不整合で作成したペア数です。 |
| `pair_count_widget_mapping` | 整数 | Widgetの表示方式の不整合で作成したペア数です。 |
| `pair_count_data_widget_connection` | 整数 | DataNodeとWidgetの接続の不整合で作成したペア数です。 |
| `pair_count_stale_result` | 整数 | 古い実行結果を残す不整合で作成したペア数です。 |
| `template_count_patient` | 整数 | 対象患者の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_clinical_item` | 整数 | 対象項目の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_time_constraint` | 整数 | 期間の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_aggregation_operation` | 整数 | 集約方法の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_information_source` | 整数 | 情報源の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_widget_mapping` | 整数 | Widgetの表示方式の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_data_widget_connection` | 整数 | DataNodeとWidgetの接続の不整合ペアを作成できた質問テンプレートの種類数です。 |
| `template_count_stale_result` | 整数 | 古い実行結果を残す不整合ペアを作成できた質問テンプレートの種類数です。 |
| `construction_failure_count_patient` | 整数 | 対象患者の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_clinical_item` | 整数 | 対象項目の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_time_constraint` | 整数 | 期間の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_aggregation_operation` | 整数 | 集約方法の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_information_source` | 整数 | 情報源の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_widget_mapping` | 整数 | Widgetの表示方式の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_data_widget_connection` | 整数 | DataNodeとWidgetの接続の不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |
| `construction_failure_count_stale_result` | 整数 | 古い実行結果を残す不整合ペアを作ろうとして、構築条件を満たさず採用しなかった試行数です。 |

`construction_failure_count_*`はケース数ではありません。同じテンプレートで複数の組み合わせを試した場合、それぞれを1試行として数えます。

## condition_metrics.tsv

4種類の検査方法を比較する集計表です。1行が1種類の検査方法を表し、現在のファイルは4行です。主要結果を確認するときに最初に使います。

| カラム | 型 | 説明 |
|---|---|---|
| `condition` | 文字列 | 適用した検査方法です。値は「検査方法の値」を参照してください。 |
| `invalid_candidate_count` | 整数 | 独立した正解判定で不整合と判定された候補数です。 |
| `unsafe_acceptance_count` | 整数 | 不整合候補を検査が受理した件数です。 |
| `unsafe_acceptance_rate` | 小数 | `unsafe_acceptance_count / invalid_candidate_count`です。低いほど不整合を流出させていません。 |
| `valid_candidate_count` | 整数 | 独立した正解判定で妥当と判定された候補数です。 |
| `valid_acceptance_count` | 整数 | 妥当候補を検査が受理した件数です。 |
| `valid_acceptance_rate` | 小数 | `valid_acceptance_count / valid_candidate_count`です。高いほど妥当な更新を過剰に棄却していません。 |
| `localized_candidate_count` | 整数 | 問題箇所の特定結果を評価できた不整合候補数です。 |
| `localization_correct_count` | 整数 | 注入した不整合の種類を正しく特定できた件数です。 |
| `localization_accuracy` | 小数 | `localization_correct_count / localized_candidate_count`です。 |
| `repair_attempt_count` | 整数 | 不整合候補を棄却した後、契約に基づく1回の修復を試した件数です。 |
| `repair_success_count` | 整数 | 修復後の候補が検査に受理され、独立した正解判定でも妥当になった件数です。 |
| `repair_success_rate` | 小数 | `repair_success_count / repair_attempt_count`です。 |
| `mean_validation_milliseconds` | 小数 | 最初の検査1回にかかった平均時間です。妥当候補と不整合候補の両方を含み、修復後の再検査時間は含みません。単位はミリ秒です。 |

## mutation_metrics.tsv

8種類の不整合と4種類の検査方法を組み合わせた集計表です。1行が1つの組み合わせを表し、現在のファイルは32行です。不整合の種類によって結果が変わるかを確認できます。

この表は不整合候補だけを集計します。妥当候補は含みません。

| カラム | 型 | 説明 |
|---|---|---|
| `mutation_kind` | 文字列 | 注入した不整合の種類です。値は「不整合の種類」を参照してください。 |
| `condition` | 文字列 | 適用した検査方法です。値は「検査方法の値」を参照してください。 |
| `candidate_count` | 整数 | この不整合と検査方法に該当する不整合候補数です。 |
| `template_count` | 整数 | 該当候補に含まれる質問テンプレートの種類数です。 |
| `unsafe_acceptance_count` | 整数 | 不整合候補を検査が受理した件数です。 |
| `unsafe_acceptance_rate` | 小数 | `unsafe_acceptance_count / candidate_count`です。 |
| `safe_rejection_count` | 整数 | 不整合候補を検査が棄却した件数です。 |
| `localization_correct_count` | 整数 | 注入した不整合の種類を正しく特定できた件数です。 |
| `repair_success_count` | 整数 | 1回の修復後に、検査と独立した正解判定の両方で妥当と判定された件数です。 |

## paired_differences.tsv

同じ候補へ適用した2種類の検査方法について、率の対応差と95%信頼区間をまとめた表です。グラフ契約をほかの3条件と比べ、2指標を計算しているため、現在のファイルは6行です。

差は`first_condition`の率から`second_condition`の率を引いて計算します。たとえば、不整合流出率の差が負なら、1つ目の条件のほうが不整合流出率が低いことを表します。

| カラム | 型 | 説明 |
|---|---|---|
| `metric` | 文字列 | 比較した率です。`unsafe_acceptance_rate`または`valid_acceptance_rate`が入ります。 |
| `first_condition` | 文字列 | 差を計算するときに先に置く検査方法です。 |
| `second_condition` | 文字列 | 差を計算するときに後に置く検査方法です。 |
| `difference` | 小数 | `first_conditionの率 - second_conditionの率`です。単位は割合の差で、`-1.0`はマイナス100ポイントです。 |
| `confidence_interval_95_lower` | 小数 | 対応差の95%信頼区間の下限です。 |
| `confidence_interval_95_upper` | 小数 | 対応差の95%信頼区間の上限です。 |
| `template_count` | 整数 | 比較に含めた質問テンプレートの種類数です。 |
| `bootstrap_iterations` | 整数 | 質問テンプレート単位のクラスターブートストラップを繰り返した回数です。 |

95%信頼区間は質問テンプレート単位で再標本化しています。同じテンプレートから生じる候補を独立した観測としてばらばらに再標本化していません。

## pair_manifest.tsv

更新ペアの対応関係とチェックサムを記録した明細表です。1行が1ペアを表し、現在のファイルは763行です。質問文、SQL、結果値は含みません。

| カラム | 型 | 説明 |
|---|---|---|
| `pair_id` | 文字列 | 更新ペアを一意に識別する24文字のIDです。患者IDではありません。 |
| `mutation_kind` | 文字列 | ペアに注入した不整合の種類です。 |
| `template_checksum` | 文字列 | 質問テンプレートから計算したSHA-256チェックサムです。 |
| `source_case_id` | 文字列 | 更新元として使ったEHRSQLケースを指す24文字のIDです。患者IDではありません。 |
| `target_case_id` | 文字列 | 更新後の正しい状態として使ったEHRSQLケースを指す24文字のIDです。患者IDではありません。 |
| `valid_candidate_checksum` | 文字列 | 妥当候補全体から計算したSHA-256チェックサムです。 |
| `invalid_candidate_checksum` | 文字列 | 不整合候補全体から計算したSHA-256チェックサムです。 |
| `contract_checksum` | 文字列 | 検査に使った契約全体から計算したSHA-256チェックサムです。 |

## candidate_results.tsv

各候補へ各検査方法を適用した結果を記録した明細表です。1行が「1候補 × 1検査方法」を表します。763ペアに妥当候補と不整合候補が1件ずつあり、それぞれへ4条件を適用したため、現在のファイルは6,104行です。

| カラム | 型 | 説明 |
|---|---|---|
| `pair_id` | 文字列 | 候補が属する更新ペアのIDです。`pair_manifest.tsv`と結合できます。 |
| `candidate_id` | 文字列 | 候補のIDです。`pair_id-valid`または`pair_id-invalid`の形式です。 |
| `template_checksum` | 文字列 | 質問テンプレートから計算したSHA-256チェックサムです。 |
| `mutation_kind` | 文字列 | このペアで扱う不整合の種類です。妥当候補の行にも同じ値が入ります。 |
| `condition` | 文字列 | 候補へ適用した検査方法です。 |
| `expected_valid` | 真偽値 | 候補生成時に付けた想定ラベルです。妥当候補は`true`、不整合を注入した候補は`false`です。 |
| `oracle_valid` | 真偽値 | 実行時の検査とは別に実装した正解判定が、候補を妥当と判定したかを表します。 |
| `accepted` | 真偽値 | `condition`の検査が候補を受理したかを表します。 |
| `unsafe_acceptance` | 真偽値 | `oracle_valid`が`false`で、`accepted`が`true`のとき`true`です。不整合の流出を表します。 |
| `safe_rejection` | 真偽値 | `oracle_valid`が`false`で、`accepted`も`false`のとき`true`です。不整合を正しく棄却したことを表します。 |
| `over_rejection` | 真偽値 | `oracle_valid`が`true`で、`accepted`が`false`のとき`true`です。妥当な更新の過剰な棄却を表します。 |
| `localization_correct` | 真偽値または空欄 | 検査が報告した問題の種類に、注入した不整合の種類が含まれると`true`です。不整合候補で特定できなければ`false`、妥当候補では空欄です。 |
| `repair_attempted` | 真偽値 | 不整合候補を検査が棄却し、1回の修復を試した場合に`true`です。 |
| `repair_success` | 真偽値または空欄 | 修復後の候補が検査に受理され、独立した正解判定でも妥当なら`true`です。修復後も条件を満たさなければ`false`、修復を試していない行では空欄です。 |
| `issue_codes` | 文字列または空欄 | 最初の検査で見つけた問題コードです。複数ある場合は`|`で区切ります。問題がなければ空欄です。 |
| `validation_seconds` | 小数 | 最初の検査1回にかかった時間です。単位は秒で、修復後の再検査時間は含みません。 |

## issue_codesの値

現在の正式結果に現れる問題コードは次のとおりです。

| 値 | 説明 |
|---|---|
| `query_provenance_mismatch` | SQLが実際に参照するテーブルと、成果物に記録した情報源が一致しません。 |
| `query_result_mismatch` | 現在のSQLと、保存済み実行結果に記録したSQLチェックサムが一致しません。 |
| `semantic_patient_mismatch` | SQLの対象患者が契約で期待した値と一致しません。 |
| `semantic_clinical_item_mismatch` | SQLの対象項目が契約で期待した値と一致しません。 |
| `semantic_time_constraint_mismatch` | SQLの期間条件が契約で期待した内容と一致しません。 |
| `semantic_aggregation_operation_mismatch` | SQLの集約方法が契約で期待した内容と一致しません。 |
| `target_query_mismatch` | 目的のDataNodeにあるSQL全体が契約と一致しません。 |
| `target_provenance_mismatch` | 目的のDataNodeに記録した情報源が契約と一致しません。 |
| `widget_shape_mismatch` | Widgetの表示方式とSQL結果の形が一致しません。 |
| `target_widget_connection_mismatch` | Widgetが契約で指定したDataNodeへ接続されていません。 |
| `target_widget_mapping_mismatch` | Widgetの表示方式が契約と一致しません。 |
| `sidecar_widget_data_node_id_mismatch` | Widgetの接続先DataNodeがサイドカー契約と一致しません。 |
| `sidecar_widget_mapping_mismatch` | Widgetの表示方式がサイドカー契約と一致しません。 |

## export_manifest.json

TSVではありませんが、変換結果を確認するために同じフォルダへ保存しています。変換コード、元成果物、各TSVのチェックサム、データ行数、照合結果を記録します。

`verification`の各値が`true`なら、元成果物のチェックサム、候補明細から再計算した集計、95%信頼区間、出力列の許可リストを照合できています。

## 解釈できる範囲

この結果は、匿名化済みMIMIC-IV Demo上で行った決定的な技術評価です。検査方法が、意図的に注入した層間不整合を検出できるかを評価しています。

臨床上の安全性、使いやすさ、認知負荷、臨床転帰、実運用、他施設への一般化は、このTSVから判断できません。
