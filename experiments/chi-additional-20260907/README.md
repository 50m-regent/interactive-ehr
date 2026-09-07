# CHI原稿の追加評価

[実験計画](PROTOCOL.md)に従い、固定した検査器へ結果を保つSQLの別解と、結果を変える候補を入力します。正式評価のコードと結果はそのまま残します。追加評価は[Issue #52](https://github.com/50m-regent/interactive-ehr/issues/52)、原稿と成果物は[PR #51](https://github.com/50m-regent/interactive-ehr/pull/51)、研究状態は[NotionのCHIタスク](https://www.notion.so/3bbc165ad0ab8124aa53ebf702a83513)で追跡します。

## 実行する

リポジトリ直下から実行します。元データはEHRSQL-2024のcommit `f9e1aa02160d39e3f8df52bf5c69c5cf2e472499` の `data/mimic_iv/` を別途取得します。必要なファイルは `test/annotated.json`、`test/data.json`、`mimic_iv.sqlite` です。実行時に正式評価の設定とのチェックサム一致を確認します。元データをリポジトリへ追加しないでください。

```bash
uv run python scripts/run_chi_sql_stress.py \
  --dataset /private/tmp/chi-ehrsql-fixed \
  --output results/evaluation/chi_sql_stress_20260907
```

既存の出力先がある場合は停止します。再現実行には別の出力先を指定し、決定的な `summary.json` と `candidate_records.jsonl` を比較します。日時や所要時間を含むマニフェストは一致比較の対象にしません。

## コードを確認する

実装は `src/interactive_ehr/evaluation/chi_sql_stress.py`、合成データによる検証は `tests/test_chi_sql_stress.py` にあります。結果の多重集合、型、列名、変換箇所、適用不可・実行失敗、分母の維持を検証します。ルートREADMEにあるpytest、ruff、tyの検査対象です。

`log-replay/` には先に行った診断ログの再集計を、当時の計画、コード、結果とともに保存しています。当時の外部反映保留の記述は履歴として残し、現在の状態は本READMEとNotionで管理します。再集計の再現は次のコマンドで行えます。

```bash
uv run python experiments/chi-additional-20260907/log-replay/replay_diagnostics.py \
  --repository . --output /private/tmp/chi-log-replay-new
uv run pytest experiments/chi-additional-20260907/log-replay/test_replay_diagnostics.py -q
```

実験結果の確認後、原稿の結果・限界と査読判断へ反映します。実際の生成エラーや医療者への効果は、この実験の対象外です。
