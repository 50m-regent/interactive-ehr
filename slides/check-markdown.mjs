#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const fencePattern = /^\s*(`{3,}|~{3,})/;
const htmlTagPattern = /<\/?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?\/?>/;
const inlineStylePattern = /\bstyle\s*=/i;
const orderedListPattern = /^\s*\d+[.)]\s+/m;
const markdownImagePattern = /!\[[^\]]*]\([^)]+\)/;
const blockquotePattern = /^\s*>\s?/m;
const tableSeparatorPattern =
  /^\s*\|?\s*:?-{3,}:?\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/m;
const strongPattern = /(?:\*\*|__)(?=\S)(.+?)(?<=\S)(?:\*\*|__)/g;

const classRequirements = new Map([
  ["summary", ["table"]],
  ["statement", ["two-tables", "blockquote"]],
  ["pipeline", ["ordered-list"]],
  ["procedure", ["ordered-list"]],
  ["flow", ["ordered-list"]],
  ["parallel", ["two-headings", "two-ordered-lists"]],
  ["agenda", ["ordered-list"]],
  ["callout", ["blockquote"]],
  ["architecture", ["ordered-list"]],
  ["comparison", ["ordered-list"]],
  ["progress", ["ordered-list"]],
  ["timeline", ["ordered-list"]],
  ["visual", ["image"]],
  ["citation", ["blockquote"]],
]);

const requirementMessages = {
  table: "Markdown表が必要です",
  "two-tables": "Markdown表が2つ必要です",
  blockquote: "Markdown引用が必要です",
  "ordered-list": "番号付きリストが必要です",
  "two-headings": "小見出しが2つ必要です",
  "two-ordered-lists": "番号付きリストが2つ必要です",
  image: "Markdown画像が必要です",
};

export function withoutComments(text) {
  return text.replace(/<!--[\s\S]*?-->/g, (comment) =>
    comment.replace(/[^\n]/g, " "),
  );
}

function countMatches(text, pattern) {
  return [...text.matchAll(pattern)].length;
}

function requirementSatisfied(slide, requirement) {
  if (requirement === "table") {
    return tableSeparatorPattern.test(slide);
  }
  if (requirement === "two-tables") {
    return countMatches(slide, new RegExp(tableSeparatorPattern, "gm")) >= 2;
  }
  if (requirement === "blockquote") {
    return blockquotePattern.test(slide);
  }
  if (requirement === "ordered-list") {
    return orderedListPattern.test(slide);
  }
  if (requirement === "two-headings") {
    return countMatches(slide, /^##\s+.+$/gm) >= 2;
  }
  if (requirement === "two-ordered-lists") {
    const listStarts = countMatches(slide, /^\s*1[.)]\s+/gm);
    return listStarts >= 2;
  }
  if (requirement === "image") {
    return markdownImagePattern.test(slide);
  }
  return true;
}

function classNames(slide) {
  const classMatch = slide.match(/<!--\s*_class:\s*([^>]+?)\s*-->/);
  return classMatch ? classMatch[1].trim().split(/\s+/) : [];
}

export function semanticViolations(path, text) {
  const issues = [];
  const slides = text.split(/^\s*---\s*$/m);

  for (const [slideIndex, slide] of slides.entries()) {
    const classes = classNames(slide);
    if (classes.length === 0) continue;

    if (classes.includes("summary")) {
      if (/^#\s+目次\s*$/m.test(slide)) {
        issues.push(`${path}: 目次にはsummaryではなくagendaを使ってください`);
      }

      for (const line of slide.split(/\r?\n/)) {
        const tableRow = line.match(/^\s*\|\s*([^|]+?)\s*\|/);
        if (tableRow && /^\d+$/.test(tableRow[1].trim())) {
          issues.push(
            `${path}: 数字をラベルにしたsummaryはagendaへ変更してください`,
          );
          break;
        }
      }
    }

    if (classes.includes("section")) {
      const activeSections = countMatches(slide, strongPattern);
      if (activeSections !== 1) {
        issues.push(
          `${path}: スライド${slideIndex + 1}のsectionでは現在章を1つだけ太字にしてください`,
        );
      }
    }

    for (const className of classes) {
      const requirements = classRequirements.get(className) ?? [];
      for (const requirement of requirements) {
        if (!requirementSatisfied(slide, requirement)) {
          issues.push(
            `${path}: スライド${slideIndex + 1}の${className}には${requirementMessages[requirement]}`,
          );
        }
      }
    }
  }

  return issues;
}

export function sourceViolations(path, source) {
  const text = withoutComments(source);
  const issues = semanticViolations(path, source);
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

export async function violations(path) {
  const source = await readFile(path, "utf8");
  return sourceViolations(path, source);
}

async function main() {
  const decks = process.argv.slice(2);
  if (decks.length === 0) {
    console.error("Usage: node check-markdown.mjs <deck.md> [deck.md ...]");
    return 2;
  }

  const issues = (await Promise.all(decks.map(violations))).flat();
  if (issues.length > 0) {
    console.error(issues.join("\n"));
    return 1;
  }

  console.log(`Markdown-only check passed: ${decks.length} deck(s)`);
  return 0;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  process.exitCode = await main();
}
