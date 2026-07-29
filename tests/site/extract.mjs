/* The site is one HTML file whose script is an IIFE, so it cannot be
   imported and cannot be evaluated whole — module scope touches matchMedia
   and the last line starts the application.

   One region of it is pure: no DOM, no fetch, no state. That region is
   fenced by banner comments and evaluated on its own here. Keeping the
   fence in the file rather than a flag in the code means production never
   carries test scaffolding. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const OPEN = "/* ---------- pure: github ---------- */";
const SHUT = "/* ---------- end pure ---------- */";

export function loadPure() {
  const html = readFileSync(join(root, "index.html"), "utf8");

  const from = html.indexOf(OPEN);
  const to = html.indexOf(SHUT);
  if (from < 0 || to < 0) throw new Error("pure region markers not found in index.html");
  if (to < from) throw new Error("pure region markers are the wrong way round");

  const source = html.slice(from + OPEN.length, to);

  // Every top-level binding in the region is collected and handed back. The
  // region is pure by construction, so a bare context is enough — anything
  // reaching for a global fails loudly here rather than silently in a browser.
  const names = [...source.matchAll(/^(?:const|function)\s+([A-Za-z_$][\w$]*)/gm)]
    .map(m => m[1]);
  if (!names.length) throw new Error("pure region defines nothing");

  // The script's completion value is its last expression, so the bindings
  // come back without assigning to a global — which strict mode would
  // refuse anyway, and which would put test scaffolding in the context.
  return vm.runInContext(
    '"use strict";\n' + source + "\n;({" + names.join(",") + "});",
    vm.createContext({}),
    { filename: "index.html#pure" }
  );
}
