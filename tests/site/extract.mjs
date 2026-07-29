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

  /* A function body rather than a vm context, deliberately. A vm gets its
     own Array and Object, so anything the region returns fails a strict
     deep-equal against a value built in the test — same shape, different
     prototype. This runs in the one realm, and isolation is not lost: the
     region names no global, and one that did would throw here exactly as
     it would in a browser. */
  return new Function('"use strict";\n' + source +
    "\nreturn {" + names.join(",") + "};")();
}
