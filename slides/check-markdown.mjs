#!/usr/bin/env node

import { readFile } from "node:fs/promises";

const fencePattern = /^\s*(`{3,}|~{3,})/;
const htmlTagPattern = /<\/?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?\/?>/;
const inlineStylePattern = /\bstyle\s*=/i;

function withoutComments(text) {
  return text.replace(/<!--[\s\S]*?-->/g, (comment) =>
    comment.replace(/[^\n]/g, " "),
  );
}

async function violations(path) {
  const text = withoutComments(await readFile(path, "utf8"));
  const issues = [];
  let fence = null;

  for (const [index, original] of text.split(/\r?\n/).entries()) {
    const fenceMatch = original.match(fencePattern);
    if (fenceMatch) {
      const marker = fenceMatch[1][0];
      if (fence === null) {
        fence = marker;
      } else if (marker === fence) {
        fence = null;
      }
      continue;
    }
    if (fence !== null) continue;

    if (htmlTagPattern.test(original)) {
      issues.push(`${path}:${index + 1}: raw HTML tag: ${original.trim()}`);
    } else if (inlineStylePattern.test(original)) {
      issues.push(`${path}:${index + 1}: inline CSS: ${original.trim()}`);
    }
  }

  return issues;
}

const decks = process.argv.slice(2);
if (decks.length === 0) {
  console.error("Usage: node check-markdown.mjs <deck.md> [deck.md ...]");
  process.exit(2);
}

const issues = (await Promise.all(decks.map(violations))).flat();
if (issues.length > 0) {
  console.error(issues.join("\n"));
  process.exit(1);
}

console.log(`Markdown-only check passed: ${decks.length} deck(s)`);
