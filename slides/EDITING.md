# Marpスライド手編集ガイド

スライド本文は通常のMarkdownで書き、見た目は `theme/research.css` に任せる。`div`、`span`、`style=` などのHTMLは書かない。

## 目次

- [編集と出力](#編集と出力)
- [1枚の基本構造](#1枚の基本構造)
- [基本Markdown一覧](#基本markdown一覧)
- [レイアウト一覧](#レイアウト一覧)
- [書き方のルール](#書き方のルール)

## 編集と出力

```bash
cd slides
npm ci
npm run dev
```

ブラウザでプレビューしながら `YYYY-MM-DD/slides.md` を編集する。

```bash
npm run check -- YYYY-MM-DD/slides.md
npm run build -- YYYY-MM-DD/slides.md -o YYYY-MM-DD/slides.pdf
npm run render -- YYYY-MM-DD/slides.md -o .render/slides.png
```

## 1枚の基本構造

スライドは `---` で区切る。`_class` コメントを置くと、そのスライドだけレイアウトが変わる。

```markdown
<!-- _class: flow -->

# スライドタイトル

1. Input
2. Method
3. **Result**

---

# 次のスライド

通常の本文
```

先頭のYAMLはデッキ全体の設定なので残す。

```yaml
---
marp: true
theme: research
paginate: true
title: "発表タイトル"
author: "氏名"
lang: "ja"
---
```

## 基本Markdown一覧

| 書くもの | Markdown | 表示 |
| --- | --- | --- |
| スライドタイトル | `# タイトル` | 濃紺の大見出し |
| 小見出し | `## 小見出し` | 濃紺の中見出し |
| 本文 | `説明文を書く` | 通常の本文 |
| 強調 | `**重要な結果**` | 朱色の強調 |
| 箇条書き | `- 項目` | 通常の箇条書き |
| 番号付き | `1. 項目` | 番号付きリスト。レイアウト指定時はカードなどに変わる |
| 表 | `｜項目｜内容｜` | 表。`summary` 指定時は要約行に変わる |
| 画像 | `![説明](assets/image.png)` | 画像。`visual` 指定時は大きく中央表示 |
| 引用 | `> 出典: 著者, 年` | 引用。`citation` 指定時は下部の出典表示 |
| 改ページ | `---` | 次のスライド |

Markdown内で明示的に改行したい場合は、行末にバックスラッシュを置く。

```markdown
1. 必要情報を\
   画面横断で探索
```

## レイアウト一覧

### 通常

指定なし。見出し、本文、箇条書きを素直に表示する。

```markdown
# 今回わかったこと

- 操作回数が減少した
- 探索時間も短縮した
- **次は被験者数を増やす**
```

表示: 白背景、濃紺のタイトル、朱色の強調。

### `cover` — 表紙

```markdown
<!-- _class: cover -->
<!-- _paginate: false -->

# 対話的グラフ構造化を用いた
# 診療記録のタスク駆動型可視化

###### Research Seminar · 2026-07-03

#### 京都大学大学院 情報学研究科 · 氏名
```

表示: 上部が濃紺、下部が白の表紙。長い題目は `#` を2行書いて分割できる。

### `section` — 章扉

```markdown
<!-- _class: section -->

# 2. 提案手法

## タスクを起点にUIを構成する
```

表示: 全面濃紺、白文字の章扉。

### `summary` — 要点一覧

```markdown
<!-- _class: summary -->

# 研究テーマ

| 項目 | 内容 |
| --- | --- |
| 背景 | 必要情報の探索負荷が高い |
| 目的 | 診療時のUXを改善する |
| 方法 | タスクからデータとUIを構成する |
```

表示: 左列が濃紺のラベル、右列が説明の3〜4行の要約。

### `flow` — 横方向フロー

```markdown
<!-- _class: flow -->

# 提案の流れ

1. 診療タスク
2. ScenarioGraph
3. **UIを生成**
```

表示: 番号付きカードが矢印で横につながる。最後のカードが朱色になる。3〜5項目を推奨する。

### `architecture` — 2段の構成図

```markdown
<!-- _class: architecture -->

# システム構成

1. **Task Recognition**

   ユーザが達成したいタスクを表現する。

2. **Data Collection**

   必要項目をDWHから取得する。

3. **UI Generation**

   閲覧目的に合うUIを描画する。
```

表示: 1・2が上段の2列、3が下段全幅のカードになる。

### `comparison` — 左右比較

```markdown
<!-- _class: comparison -->

# 実験条件

1. **従来UI**

   固定された画面を横断して情報を探す。

2. **提案UI**

   タスクに必要な情報だけを表示する。
```

表示: 2枚の比較カード。右側の枠が朱色になる。

### `progress` — 進捗一覧

```markdown
<!-- _class: progress -->

# 現在の実装

1. ScenarioGraphからUIを描画
2. DWHをSQLで参照
3. **実験シナリオを検証中**
```

表示: 丸い番号付きの横長カードを縦に並べる。

### `timeline` — 時系列

```markdown
<!-- _class: timeline -->

# 次の予定

1. **シナリオ**\
   有識者意見を反映
2. **グラフ**\
   比較条件を固定
3. **実験**\
   操作・負荷を評価
4. **論文**\
   結果を統合
```

表示: マイルストーンを横に並べる。最初の項目の上線が朱色になる。

### `visual` — 画像中心

```markdown
<!-- _class: visual -->

# プロトタイプ

![生成されたUI](assets/prototype.png)
```

表示: 画像を縦横比を保ってスライド中央へ大きく配置する。

### `citation` — 出典付き

複数クラスは空白で並べる。

```markdown
<!-- _class: visual citation -->

# 関連研究

![論文中の概念図](assets/paper-figure.png)

> 出典: Author et al., Journal, 2026
```

表示: `visual` の画像配置に加え、引用をスライド下部へ小さく表示する。

## 書き方のルール

- 1枚につき伝えたいことを1つに絞る。
- タイトルは原則1行、本文は6行程度までを目安にする。
- 強調したい語だけを `**太字**` にする。
- raw HTML、インラインCSS、外部スクリプトを書かない。
- レイアウトを変えたいときはHTMLを追加せず、`_class` を選ぶか `theme/research.css` を変更する。
- 画像はデッキと同じ階層の `assets/` に置き、相対パスで参照する。
- PDF出力前に `npm run check` とPNG確認を行う。
