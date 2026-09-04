import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const paperDirectory = dirname(scriptDirectory);
const sourceDirectory = join(paperDirectory, "figures", "src");
const outputDirectory = join(paperDirectory, "figures", "svg");
const figureNames = [
  "scenario-to-value",
  "detection-mechanism",
  "evaluation-protocol",
  "scenario-to-value-en",
  "detection-mechanism-en",
  "evaluation-protocol-en",
];

await mkdir(outputDirectory, { recursive: true });

for (const figureName of figureNames) {
  const sourcePath = join(sourceDirectory, `${figureName}.html`);
  const html = await readFile(sourcePath, "utf8");
  const match = html.match(/<svg\b[\s\S]*?<\/svg>/u);
  if (!match) {
    throw new Error(`SVG element was not found in ${basename(sourcePath)}`);
  }

  const outputPath = join(outputDirectory, `${figureName}${extname("figure.svg")}`);
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n${match[0]}\n`;
  await writeFile(outputPath, svg, "utf8");
}
