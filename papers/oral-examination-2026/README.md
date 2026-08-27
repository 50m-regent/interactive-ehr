# 口頭試問会原稿

Notionの研究ダッシュボードと関連ページ、`socguide202304.doc`の作成要領を基にしたLaTeX原稿です。

## ビルド

TeX Live 2024以降で次を実行します。

```bash
make
```

最終PDFは`output/pdf/Hirata_Ren.pdf`へ生成されます。中間生成物は`build/`へ保存されます。

## 体裁

- A4、本文2段組、要旨1段組
- 上30mm、下27mm、左18mm、右18mm、段間7mm
- 表題12pt、著者名・所属・見出し・本文10.5pt
- 和文はHaranoAji明朝、欧文はTimes New Roman互換のTimes系
- ページ番号なし
- 図はTikZによるベクター描画
