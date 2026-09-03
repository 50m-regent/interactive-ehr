# CHI 2027 Papers 日本語確認稿

生成臨床UIの更新における層間整合性の技術評価を、CHI 2027 Papers向けにまとめた日本語確認稿です。投稿時は英語へ移し、内容確認中は日本語版を正本とします。

## 原稿の範囲

- EHRSQL-2024とMIMIC-IV Clinical Database Demo v2.2を使った決定的な技術評価を扱います。
- 8種類の層間不整合と4種類の検査条件を比較します。
- 検出、妥当候補の受理、問題箇所の特定、一回の自動修復を報告します。
- 臨床上の安全性、使いやすさ、認知負荷、臨床転帰は主張しません。
- 評価基盤には固有名称を付けず、本文では「層間整合性評価基盤」「評価基盤」「本評価」を使います。

## CHI 2027の形式

2026年9月3日時点の公式案内に従い、匿名、単一カラムの `acmart` review形式で作成しています。英語版では抄録を150語以内にし、本文は5,000語から8,000語を目安にします。投稿前に公式案内を再確認してください。

- Papers: https://chi2027.acm.org/authors/papers/
- Publication Formats: https://chi2027.acm.org/chi-publication-formats/

## ビルド

LuaLaTeXと `latexmk` を使います。

```bash
cd papers/chi-2027
make
```

生成物は `output/pdf/chi-2027-ja-review.pdf` です。

## 根拠となる結果

正式結果は既存の `results/evaluation/tracebench_ehr_v1.1/test/` にあります。このパスは再現性のため変更していません。本文中では内部パス名を研究名称として使いません。

主な根拠は次のファイルです。

- `report.md`
- `summary.json`
- `build_summary.json`
- `tsv/condition_metrics.tsv`
- `tsv/mutation_metrics.tsv`
- `tsv/paired_differences.tsv`
- `tsv/export_manifest.json`

## 英語版へ移す前の確認

- 日本語版で貢献、研究質問、結果、議論が一致しているか確認する
- 変異生成の失敗例と代表的な診断例を補足資料へ追加する
- 図表の説明文と代替テキストを英語へ移す
- 著者情報、謝辞、リポジトリURL、補足資料を匿名化する
- CHI 2027の最新版テンプレートと投稿要件を再確認する
