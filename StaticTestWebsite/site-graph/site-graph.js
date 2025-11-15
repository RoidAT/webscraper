import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { JSDOM } from "jsdom";
import { glob } from "glob";

// Damit __dirname funktioniert in ESM:
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Pfad zu deinem Website-Verzeichnis:
const rootDir = path.resolve(__dirname, "../");

// Alle HTML-Dateien finden:
const htmlFiles = await glob(`${rootDir}/**/*.html`);
const links = [];

for (const file of htmlFiles) {
  const html = fs.readFileSync(file, "utf8");
  const dom = new JSDOM(html);
  const document = dom.window.document;
  const anchors = [...document.querySelectorAll("a[href]")];

  for (const a of anchors) {
    const href = a.getAttribute("href");
    if (href && !href.startsWith("http") && href.endsWith(".html")) {
      const source = path.relative(rootDir, file);
      const target = path.normalize(
        path.relative(rootDir, path.join(path.dirname(file), href))
      );
      links.push({ source, target });
    }
  }
}

let dot = "digraph Website {\n  rankdir=LR;\n  node [shape=box, style=filled, fillcolor=lightgray];\n";
for (const { source, target } of links) {
  dot += `  "${source}" -> "${target}";\n`;
}
dot += "}\n";

fs.writeFileSync("site.dot", dot);
console.log("✅ Site-Graph erstellt: site.dot");

// Optional automatisch PNG erzeugen (falls Graphviz installiert)
try {
  const { execSync } = await import("child_process");
  execSync('dot -Tpng site.dot -o site.png');
  console.log("✅ site.png wurde erstellt");
} catch {
  console.warn("⚠️ Graphviz nicht installiert – .dot-Datei wurde erstellt, PNG nicht generiert.");
}
