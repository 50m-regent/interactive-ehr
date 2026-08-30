import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { sourceViolations, violations } from "./check-markdown.mjs";

test("標準Markdownだけのスライドを受け入れる", () => {
  const source = `
<!-- _class: procedure -->

# 手順

1. 条件を決める
2. 実験する
3. 比較する
`;

  assert.deepEqual(sourceViolations("valid.md", source), []);
});

test("raw HTMLを拒否する", () => {
  const source = `
# 不正な例

<div>本文</div>
`;

  assert.match(sourceViolations("html.md", source).join("\n"), /raw HTML/);
});

test("summaryの箇条書きを受け入れる", () => {
  const source = `
<!-- _class: summary -->

# 研究テーマ

- 背景
- 目的
`;

  assert.deepEqual(sourceViolations("summary-list.md", source), []);
});

test("summaryの番号付きリストを受け入れる", () => {
  const source = `
<!-- _class: summary -->

# 研究質問

1. どの誤りが残るか
2. どこまで直せるか
`;

  assert.deepEqual(sourceViolations("summary-ordered-list.md", source), []);
});

test("summaryに表もリストもない場合は拒否する", () => {
  const source = `
<!-- _class: summary -->

# 研究テーマ

背景と目的を説明する
`;

  assert.match(
    sourceViolations("summary-text.md", source).join("\n"),
    /Markdown表またはリストが必要/,
  );
});

test("parallelに二つの見出しとリストを求める", () => {
  const source = `
<!-- _class: parallel -->

# 今後の進め方

## 実験

1. 実施する
`;

  const issues = sourceViolations("parallel.md", source).join("\n");
  assert.match(issues, /小見出しが2つ必要/);
  assert.match(issues, /番号付きリストが2つ必要/);
});

test("visualにMarkdown画像を求める", () => {
  const source = `
<!-- _class: visual -->

# 構成図

画像を置く
`;

  assert.match(
    sourceViolations("visual.md", source).join("\n"),
    /Markdown画像が必要/,
  );
});

test("visualの画像直後にキャプションを求める", () => {
  const source = `
<!-- _class: visual -->

# 構成図

![構成図](assets/figure.png)
`;

  assert.match(
    sourceViolations("visual-caption.md", source).join("\n"),
    /各画像の直後にキャプションが必要/,
  );
});

test("visual-pairに画像とキャプションを二組求める", () => {
  const source = `
<!-- _class: visual-pair -->

# 画面比較

![従来画面](assets/current.png)

従来画面

![提案画面](assets/proposed.png)

提案画面

同じ条件で比較する
`;

  assert.deepEqual(sourceViolations("visual-pair.md", source), []);
});

test("visual-pairで画像が一つの場合は拒否する", () => {
  const source = `
<!-- _class: visual-pair -->

# 画面比較

![従来画面](assets/current.png)

従来画面
`;

  assert.match(
    sourceViolations("visual-pair.md", source).join("\n"),
    /Markdown画像が2つ必要/,
  );
});

test("citationに出典の引用を求める", () => {
  const source = `
<!-- _class: visual citation -->

# 関連研究

![概念図](assets/figure.png)

概念図のキャプション
`;

  assert.match(
    sourceViolations("citation.md", source).join("\n"),
    /出典の引用が必要/,
  );
});

test("citationで画像より前の引用だけでは拒否する", () => {
  const source = `
<!-- _class: visual citation -->

# 関連研究

> 研究の目的

![概念図](assets/figure.png)

概念図のキャプション
`;

  assert.match(
    sourceViolations("citation-order.md", source).join("\n"),
    /画像とキャプションの後に出典の引用が必要/,
  );
});

test("relationに二列の表と出典を受け入れる", () => {
  const source = `
<!-- _class: relation citation -->

# Widget generation

| 入力 | 出力 |
| --- | --- |
| タスクとデータ | Widget |

入力に応じて表示する

> 出典: 著者名ほか, 2026
`;

  assert.deepEqual(sourceViolations("relation.md", source), []);
});

test("labeled-sectionsに二つの見出しと箇条書きを求める", () => {
  const source = `
<!-- _class: labeled-sections -->

# Current System

> 利用場面を整理した

## Scenario

> 患者の状態を確認する

## Tasks

- 検査結果を確認する
`;

  assert.deepEqual(sourceViolations("labeled-sections.md", source), []);
});

test("sectionで現在章が一つだけなら受け入れる", () => {
  const source = `
<!-- _class: section -->

# Research Theme

- **Architecture**
- Methods
- Procedure
`;

  assert.deepEqual(sourceViolations("section.md", source), []);
});

test("sectionで現在章が複数ある場合は拒否する", () => {
  const source = `
<!-- _class: section -->

# **Research Theme**

- **Architecture**
- Methods
- Procedure
`;

  assert.match(
    sourceViolations("section.md", source).join("\n"),
    /現在章を1つだけ太字/,
  );
});

test("sectionで現在章がない場合は拒否する", () => {
  const source = `
<!-- _class: section -->

# Research Theme

- Architecture
- Methods
- Procedure
`;

  assert.match(
    sourceViolations("section.md", source).join("\n"),
    /現在章を1つだけ太字/,
  );
});

test("参照再構成デッキのfrontmatterとページ別クラスを受け入れる", () => {
  const source = `---
marp: true
theme: research
class: reference-rebuild
---

<!-- _class: summary -->

# 背景

- 情報が分散している
`;

  assert.deepEqual(sourceViolations("reference.md", source), []);
});

test("参照再構成デッキにresearchテーマを求める", () => {
  const source = `---
marp: true
theme: default
class: reference-rebuild
---

<!-- _class: summary -->

# 背景

- 情報が分散している
`;

  assert.match(
    sourceViolations("reference-theme.md", source).join("\n"),
    /theme: researchが必要/,
  );
});

test("参照再構成デッキの全スライドにページ別クラスを求める", () => {
  const source = `---
marp: true
theme: research
class: reference-rebuild
---

<!-- _class: summary -->

# 背景

- 情報が分散している

---

# 目的

- 操作を減らす
`;

  assert.match(
    sourceViolations("reference-class.md", source).join("\n"),
    /スライド2にページ別クラスが必要/,
  );
});

test("参照再構成クラスだけでfrontmatterがない場合は拒否する", () => {
  const source = `
<!-- _class: reference-rebuild summary -->

# 背景

- 情報が分散している
`;

  const issues = sourceViolations("reference-frontmatter.md", source).join("\n");
  assert.match(issues, /frontmatterが必要/);
  assert.match(issues, /marp: trueが必要/);
});

test("存在するローカル画像を受け入れる", async () => {
  const directory = await mkdtemp(join(tmpdir(), "marp-check-"));
  try {
    await mkdir(join(directory, "assets"));
    await writeFile(join(directory, "assets", "figure.png"), "png");
    const deck = join(directory, "slides.md");
    await writeFile(
      deck,
      `<!-- _class: visual -->\n\n# 図\n\n![図](assets/figure.png)\n\n図の説明\n`,
    );

    assert.deepEqual(await violations(deck), []);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("存在しないローカル画像を拒否する", async () => {
  const directory = await mkdtemp(join(tmpdir(), "marp-check-"));
  try {
    const deck = join(directory, "slides.md");
    await writeFile(
      deck,
      `<!-- _class: visual -->\n\n# 図\n\n![図](assets/missing.png)\n\n図の説明\n`,
    );

    assert.match((await violations(deck)).join("\n"), /画像ファイルがありません/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
