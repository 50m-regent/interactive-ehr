#!/usr/bin/env node

import { access, readFile } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const fencePattern = /^\s*(`{3,}|~{3,})/;
const htmlTagPattern = /<\/?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?\/?>/;
const inlineStylePattern = /\bstyle\s*=/i;
const orderedListPattern = /^\s*\d+[.)]\s+/m;
const unorderedListPattern = /^\s*[-+*]\s+/m;
const markdownImagePattern = /!\[[^\]]*]\([^)]+\)/;
const markdownImagePathPattern = /!\[[^\]]*]\((?:<([^>]+)>|([^\s)]+))(?:\s+["'][^"']*["'])?\)/g;
const blockquotePattern = /^\s*>\s?/m;
const tableSeparatorPattern =
  /^\s*\|?\s*:?-{3,}:?\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/m;
const strongPattern = /(?:\*\*|__)(?=\S)(.+?)(?<=\S)(?:\*\*|__)/g;
const frontmatterPattern = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

const classRequirements = new Map([
  ["summary", ["table-or-list"]],
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
  ["visual", ["image", "image-captions"]],
  ["visual-pair", ["two-images", "image-captions"]],
  ["relation", ["table"]],
  ["labeled-sections", ["two-headings", "blockquote", "unordered-list"]],
  ["citation", ["citation-blockquote"]],
]);

const requirementMessages = {
  table: "Markdown表が必要です",
  "table-or-list": "Markdown表またはリストが必要です",
  "two-tables": "Markdown表が2つ必要です",
  blockquote: "Markdown引用が必要です",
  "citation-blockquote": "画像とキャプションの後に出典の引用が必要です",
  "ordered-list": "番号付きリストが必要です",
  "unordered-list": "箇条書きが必要です",
  "two-headings": "小見出しが2つ必要です",
  "two-ordered-lists": "番号付きリストが2つ必要です",
  image: "Markdown画像が必要です",
  "two-images": "Markdown画像が2つ必要です",
  "image-captions": "各画像の直後にキャプションが必要です",
};

export function withoutComments(text) {
  return text.replace(/<!--[\s\S]*?-->/g, (comment) =>
    comment.replace(/[^\n]/g, " "),
  );
}

function countMatches(text, pattern) {
  return [...text.matchAll(pattern)].length;
}

function frontmatter(source) {
  const match = source.match(frontmatterPattern);
  if (!match) return { attributes: new Map(), body: source, present: false };

  const attributes = new Map();
  for (const line of match[1].split(/\r?\n/)) {
    const item = line.match(/^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$/);
    if (!item) continue;
    const value = item[2].replace(/^(?:"([\s\S]*)"|'([\s\S]*)')$/, "$1$2");
    attributes.set(item[1], value);
  }
  return {
    attributes,
    body: source.slice(match[0].length),
    present: true,
  };
}

function classNames(slide) {
  const classMatch = slide.match(/<!--\s*_class:\s*([^>]+?)\s*-->/);
  return classMatch ? classMatch[1].trim().split(/\s+/) : [];
}

function referenceDeck(source, attributes) {
  const globalClasses = (attributes.get("class") ?? "").split(/\s+/);
  return (
    globalClasses.includes("reference-rebuild") ||
    /<!--\s*_class:\s*[^>]*\breference-rebuild\b[^>]*-->/m.test(source)
  );
}

function imagesHaveCaptions(slide) {
  const lines = withoutComments(slide).split(/\r?\n/);
  for (const [index, line] of lines.entries()) {
    if (!markdownImagePattern.test(line)) continue;
    const caption = lines.slice(index + 1).find((candidate) => candidate.trim());
    if (!caption) return false;
    const value = caption.trim();
    if (
      markdownImagePattern.test(value) ||
      /^(?:#{1,6}\s|>\s?|[-+*]\s|\d+[.)]\s|`{3,}|~{3,}|\|)/.test(value)
    ) {
      return false;
    }
  }
  return true;
}

function requirementSatisfied(slide, requirement) {
  if (requirement === "table") {
    return tableSeparatorPattern.test(slide);
  }
  if (requirement === "table-or-list") {
    return (
      tableSeparatorPattern.test(slide) ||
      orderedListPattern.test(slide) ||
      unorderedListPattern.test(slide)
    );
  }
  if (requirement === "two-tables") {
    return countMatches(slide, new RegExp(tableSeparatorPattern, "gm")) >= 2;
  }
  if (requirement === "blockquote") {
    return blockquotePattern.test(slide);
  }
  if (requirement === "citation-blockquote") {
    const imageIndex = slide.lastIndexOf("![");
    const quotes = [...slide.matchAll(/^\s*>/gm)];
    const quoteIndex = quotes.at(-1)?.index ?? -1;
    return quoteIndex >= 0 && (imageIndex < 0 || quoteIndex > imageIndex);
  }
  if (requirement === "ordered-list") {
    return orderedListPattern.test(slide);
  }
  if (requirement === "unordered-list") {
    return unorderedListPattern.test(slide);
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
  if (requirement === "two-images") {
    return countMatches(slide, new RegExp(markdownImagePattern, "g")) === 2;
  }
  if (requirement === "image-captions") {
    return imagesHaveCaptions(slide);
  }
  return true;
}

export function semanticViolations(path, source) {
  const issues = [];
  const parsed = frontmatter(source);
  const isReferenceDeck = referenceDeck(source, parsed.attributes);
  const slides = parsed.body.split(/^\s*---\s*$/m);

  if (isReferenceDeck) {
    if (!parsed.present) {
      issues.push(`${path}: 参照再構成デッキにはfrontmatterが必要です`);
    }
    if (parsed.attributes.get("marp") !== "true") {
      issues.push(`${path}: 参照再構成デッキにはmarp: trueが必要です`);
    }
    if (parsed.attributes.get("theme") !== "research") {
      issues.push(`${path}: 参照再構成デッキにはtheme: researchが必要です`);
    }
  }

  for (const [slideIndex, slide] of slides.entries()) {
    const classes = classNames(slide);
    if (isReferenceDeck && classes.length === 0) {
      issues.push(`${path}: スライド${slideIndex + 1}にページ別クラスが必要です`);
      continue;
    }
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

function localImagePaths(source) {
  const paths = [];
  for (const match of source.matchAll(markdownImagePathPattern)) {
    const value = match[1] ?? match[2];
    if (/^(?:https?:|data:)/i.test(value)) continue;
    paths.push(decodeURIComponent(value.split("#", 1)[0]));
  }
  return paths;
}

export async function violations(path) {
  const source = await readFile(path, "utf8");
  const issues = sourceViolations(path, source);
  const base = dirname(resolve(path));
  for (const imagePath of localImagePaths(source)) {
    const candidate = isAbsolute(imagePath) ? imagePath : resolve(base, imagePath);
    try {
      await access(candidate);
    } catch {
      issues.push(`${path}: 画像ファイルがありません: ${imagePath}`);
    }
  }
  return issues;
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
