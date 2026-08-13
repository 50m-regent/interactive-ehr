import assert from "node:assert/strict";
import test from "node:test";

import { sourceViolations } from "./check-markdown.mjs";

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

test("summaryに表がない場合は拒否する", () => {
  const source = `
<!-- _class: summary -->

# 研究テーマ

- 背景
- 目的
`;

  assert.match(
    sourceViolations("summary.md", source).join("\n"),
    /Markdown表が必要/,
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
