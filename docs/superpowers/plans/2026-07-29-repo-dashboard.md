# Repository Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a GitHub repository entry open as a five-section dashboard —
Overview, Code, Development, Releases, Activity — instead of a bare README.

**Architecture:** Entirely client-side, inside `index.html`. Sections are
routes shaped like github.com's own URLs. Four REST calls on arrival feed
every section; all filtering is client-side slicing of one `/issues`
payload. A new pure-function region in the script is extracted and tested by
a `node --test` harness.

**Tech Stack:** Vanilla ES2020 in one HTML file. Node 20 `node:test` +
`node:vm` for tests. No dependencies, no build step.

## Global Constraints

- **No third-party requests.** Only `api.telegra.ph`, `raw.githubusercontent.com`,
  `api.github.com`, and same-origin assets. No CDN, no fonts, no analytics.
- **Nothing durable is stored.** `sessionStorage` only, keyed `tp:`, dies with the tab.
- **No new dependencies.** `requirements-dev.txt` and the repo's zero-dependency
  front end stay as they are. Tests use Node's built-in `node:test`.
- **One HTML file.** No second script file is served. `hljs.min.js` remains the
  only separate script, loaded only on code pages.
- **`--col` is the only width control.** Nothing may set `padding-inline` or
  `margin-inline` on a `.col` element (index.html:88–93).
- **The lamp (`--lamp`) is reserved** for live and active states only (index.html:10).
- **`bot.py` is not modified.** The entry format is unchanged.
- **Two spaces indent, `const` arrow functions, comments in the project's voice**
  (explain *why*, not *what*).
- **Metered budget:** four `api.github.com` calls on arrival, tree on demand.
  Never add a fifth without removing one.

---

## File Structure

| File | Responsibility |
|---|---|
| `index.html` | Everything user-facing. New pure region + new render code. |
| `tests/site/extract.mjs` | Slices the pure region out of `index.html` and evaluates it. |
| `tests/site/routing.test.mjs` | Section routes, round-trips, legacy links. |
| `tests/site/issues.test.mjs` | Issue splitting, section derivation, filtering. |
| `tests/site/activity.test.mjs` | Activity merge, contributor derivation. |
| `.github/workflows/test.yml` | Gains a `node --test` step. |
| `README.md` | Documents the dashboard. |

The JS tests live under `tests/site/` so `pytest`'s `testpaths = tests` is
unaffected — pytest collects `test_*.py` only and ignores `.mjs`.

---

### Task 1: The pure region and its test harness

Nothing can be tested until the pure functions are reachable. The script is
an IIFE (`index.html:642`), so evaluating it whole exposes nothing and throws
on `matchMedia` at module scope. Instead one marked region is sliced out and
evaluated alone.

**Files:**
- Modify: `index.html:688–721` (move gh helpers into the new region)
- Modify: `index.html:910–911` (move `isGh`/`isTree` up into the region)
- Create: `tests/site/extract.mjs`
- Create: `tests/site/routing.test.mjs`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: `loadPure()` → object with every function defined in the pure
  region. Every later task adds its functions to this region and gets them
  from `loadPure()` for free.

- [ ] **Step 1: Write the failing test**

Create `tests/site/extract.mjs`:

```javascript
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

  const context = vm.createContext({});
  vm.runInContext(
    '"use strict";\n' + source + "\n;__out = {" + names.join(",") + "};",
    context,
    { filename: "index.html#pure" }
  );

  return context.__out;
}
```

Create `tests/site/routing.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { ghFromParts, ghToParts } = loadPure();

test("a bare repository is the overview", () => {
  assert.equal(ghFromParts(["github.com", "o", "r"]), "gh:o/r");
});

test("a blob is a file", () => {
  assert.equal(
    ghFromParts(["github.com", "o", "r", "blob", "HEAD", "bot.py"]),
    "gh:o/r/bot.py"
  );
});

test("a tree is a directory", () => {
  assert.equal(
    ghFromParts(["github.com", "o", "r", "tree", "HEAD", "docs"]),
    "ght:o/r/docs"
  );
});

test("anything that is not github is not a resource", () => {
  assert.equal(ghFromParts(["some-telegraph-path"]), null);
  assert.equal(ghFromParts([]), null);
});

test("a resource round-trips through the URL and back", () => {
  for (const id of ["gh:o/r", "gh:o/r/bot.py", "ght:o/r/docs"]) {
    assert.equal(ghFromParts(ghToParts(id)), id, id);
  }
});

test("prefixed ids already in the wild still parse", () => {
  assert.equal(ghFromParts(["gh:o/r/docs/a.md"]), "gh:o/r/docs/a.md");
  assert.equal(ghFromParts(["ght:o/r", "docs"]), "ght:o/r/docs");
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `node --test tests/site/`
Expected: FAIL — `pure region markers not found in index.html`

- [ ] **Step 3: Create the region**

In `index.html`, replace lines 688–721 (from `const GH_HOST = "github.com";`
through `const isResource = path => isGh(path) || isTree(path);`) with the
region below. It is the same code, fenced, plus `isGh`/`isTree` moved up
from lines 910–911 so the region stands alone.

```javascript
/* ---------- pure: github ---------- */
/* Everything between these markers is pure: no DOM, no fetch, no state. It
   is sliced out and evaluated on its own by tests/site/extract.mjs, which is
   only possible while that stays true. Anything needing a document or a
   network belongs below the closing marker. */

const GH_HOST = "github.com";

const isGh = path => typeof path === "string" && path.startsWith("gh:");
const isTree = path => typeof path === "string" && path.startsWith("ght:");
const isResource = path => isGh(path) || isTree(path);

// URL segments (after the master) -> internal resource id, else null.
function ghFromParts(parts) {
  // Links written before this change arrive either whole or, if something
  // decoded the escaped slashes, already split. Either way, rejoining is
  // right: no Telegraph path begins "gh:".
  const first = parts[0] || "";
  if (first.startsWith("gh:") || first.startsWith("ght:")) return parts.join("/");

  if (first !== GH_HOST || parts.length < 3) return null;
  const owner = parts[1], repo = parts[2];
  const kind = parts[3];                  // "blob", "tree", or nothing
  const rest = parts.slice(5).join("/");  // parts[4] is the git ref

  if (kind === "tree") return "ght:" + owner + "/" + repo + (rest ? "/" + rest : "");
  if (kind === "blob" && rest) return "gh:" + owner + "/" + repo + "/" + rest;
  return "gh:" + owner + "/" + repo;      // bare repository
}

/* Internal resource id -> URL segments. The ref is spelled out as HEAD so
   that putting "https://" in front of the result is a working github.com
   address — the same page, at the source. */
function ghToParts(resource) {
  if (isTree(resource)) {
    const [owner, repo, ...rest] = resource.slice(4).split("/");
    return [GH_HOST, owner, repo, "tree", "HEAD", ...rest];
  }
  const [owner, repo, ...rest] = resource.slice(3).split("/");
  return rest.length ? [GH_HOST, owner, repo, "blob", "HEAD", ...rest]
                     : [GH_HOST, owner, repo];
}

/* ---------- end pure ---------- */
```

Then delete the now-duplicated `const isGh` and `const isTree` at their old
position (was index.html:910–911).

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/site/`
Expected: PASS, 6 tests.

Also confirm nothing regressed in the browser contract:

Run: `python -m pytest && node --check <(python -c "import re,pathlib; print(re.search(r'^<script>\n(.*?)\n</script>', pathlib.Path('index.html').read_text(), re.S|re.M).group(1))")`
Expected: pytest passes; `node --check` silent.

- [ ] **Step 5: Add the tests to CI**

In `.github/workflows/test.yml`, after the `check the site's script parses`
step, add:

```yaml
      - name: the site's pure functions
        run: node --test tests/site/
```

- [ ] **Step 6: Commit**

```bash
git add index.html tests/site/ .github/workflows/test.yml
git commit -m "Fence the pure half, so it can be tested at all"
```

---

### Task 2: Section routes

**Files:**
- Modify: `index.html` — the pure region (extend `ghFromParts`/`ghToParts`, add `ghSection`)
- Modify: `tests/site/routing.test.mjs`

**Interfaces:**
- Consumes: `ghFromParts`, `ghToParts` from Task 1.
- Produces:
  - resource ids gain a section suffix: `gh:o/r@issues`, `gh:o/r@issues/144`,
    `gh:o/r@releases`, `gh:o/r@pulse`. A bare `gh:o/r` is Overview.
  - `ghSection(id)` → `{repo, section, arg}` where `repo` is `"o/r"`,
    `section` is one of `"overview" | "issues" | "issue" | "releases" | "pulse"`,
    and `arg` is the issue number as a string, or `null`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/site/routing.test.mjs`:

```javascript
const { ghSection } = loadPure();

test("sections are read from github's own paths", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "issues"]), "gh:o/r@issues");
  assert.equal(ghFromParts(["github.com", "o", "r", "issues", "144"]), "gh:o/r@issues/144");
  assert.equal(ghFromParts(["github.com", "o", "r", "releases"]), "gh:o/r@releases");
  assert.equal(ghFromParts(["github.com", "o", "r", "pulse"]), "gh:o/r@pulse");
});

test("a section round-trips", () => {
  for (const id of ["gh:o/r@issues", "gh:o/r@issues/144", "gh:o/r@releases", "gh:o/r@pulse"]) {
    assert.equal(ghFromParts(ghToParts(id)), id, id);
  }
});

test("a section URL is a real github.com address", () => {
  assert.deepEqual(ghToParts("gh:o/r@issues/144"), ["github.com", "o", "r", "issues", "144"]);
});

test("blob and tree are untouched by sections", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "blob", "HEAD", "bot.py"]), "gh:o/r/bot.py");
  assert.equal(ghFromParts(["github.com", "o", "r", "tree", "HEAD", "docs"]), "ght:o/r/docs");
});

test("ghSection splits a resource id", () => {
  assert.deepEqual(ghSection("gh:o/r"), { repo: "o/r", section: "overview", arg: null });
  assert.deepEqual(ghSection("gh:o/r@issues"), { repo: "o/r", section: "issues", arg: null });
  assert.deepEqual(ghSection("gh:o/r@issues/144"), { repo: "o/r", section: "issue", arg: "144" });
  assert.deepEqual(ghSection("gh:o/r@pulse"), { repo: "o/r", section: "pulse", arg: null });
});

test("a file is not a section", () => {
  assert.equal(ghSection("gh:o/r/bot.py"), null);
  assert.equal(ghSection("ght:o/r/docs"), null);
});

test("an unknown github path is not invented into a section", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "settings"]), "gh:o/r");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/site/routing.test.mjs`
Expected: FAIL — `ghSection is not a function`.

- [ ] **Step 3: Implement**

In the pure region, replace `ghFromParts` and `ghToParts` and add `ghSection`:

```javascript
/* The sections of a repository, spelled the way github.com spells them, so
   that putting "https://" in front of any of these routes lands on the same
   thing at the source. There is deliberately no "readme": github has no such
   path, and the README lives beneath Overview as it does there. */
const GH_SECTIONS = ["issues", "releases", "pulse"];

function ghFromParts(parts) {
  const first = parts[0] || "";
  if (first.startsWith("gh:") || first.startsWith("ght:")) return parts.join("/");

  if (first !== GH_HOST || parts.length < 3) return null;
  const owner = parts[1], repo = parts[2];
  const base = "gh:" + owner + "/" + repo;
  const kind = parts[3];

  if (kind === "tree") {
    const rest = parts.slice(5).join("/");
    return "ght:" + owner + "/" + repo + (rest ? "/" + rest : "");
  }
  if (kind === "blob") {
    const rest = parts.slice(5).join("/");
    return rest ? base + "/" + rest : base;
  }

  // A section carries no git ref, so nothing is skipped: "issues/144" is
  // the section and its argument, not a ref and a path.
  if (GH_SECTIONS.includes(kind)) {
    const arg = parts[4];
    return base + "@" + kind + (arg ? "/" + arg : "");
  }

  // Any other github path — /settings, /actions, /wiki — is not something
  // this site renders. Landing on the repository is better than a dead page.
  return base;
}

function ghToParts(resource) {
  if (isTree(resource)) {
    const [owner, repo, ...rest] = resource.slice(4).split("/");
    return [GH_HOST, owner, repo, "tree", "HEAD", ...rest];
  }

  const at = resource.indexOf("@");
  if (at >= 0) {
    const [owner, repo] = resource.slice(3, at).split("/");
    return [GH_HOST, owner, repo, ...resource.slice(at + 1).split("/")];
  }

  const [owner, repo, ...rest] = resource.slice(3).split("/");
  return rest.length ? [GH_HOST, owner, repo, "blob", "HEAD", ...rest]
                     : [GH_HOST, owner, repo];
}

/* A resource id -> which repository, which section, and its argument.
   Returns null for anything that is not a repository page: a file or a
   directory is content, not a section of the dashboard. */
function ghSection(resource) {
  if (!isGh(resource)) return null;

  const at = resource.indexOf("@");
  const head = at < 0 ? resource.slice(3) : resource.slice(3, at);
  if (head.split("/").length !== 2) return null;   // a file path

  if (at < 0) return { repo: head, section: "overview", arg: null };

  const [name, arg = null] = resource.slice(at + 1).split("/");
  const section = name === "issues" && arg ? "issue" : name;
  return { repo: head, section, arg };
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/site/`
Expected: PASS, 13 tests.

- [ ] **Step 5: Commit**

```bash
git add index.html tests/site/routing.test.mjs
git commit -m "Address a repository's sections the way github addresses them"
```

---

### Task 3: What GitHub is asked for

**Files:**
- Modify: `index.html` — below the pure region, beside `ghTree` (index.html:932)
- Create: `tests/site/token.test.mjs`

**Interfaces:**
- Consumes: `ghSection` from Task 2.
- Produces:
  - `looksLikeGhToken(text)` → `boolean` (pure, in the region)
  - `ghTokenKind(text)` → `"fine" | "broad" | null` (pure, in the region)
  - `ghApi(path)` → `Promise<any>` — fetches `api.github.com` + `path`,
    adds the token when there is one, caches, throws `RateLimited` on 403.
  - `ghRepoData(repo)` → `Promise<{repo, issues, releases, commits}>` —
    the four calls, in parallel, each independently allowed to fail.

- [ ] **Step 1: Write the failing tests**

Create `tests/site/token.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { looksLikeGhToken, ghTokenKind } = loadPure();

test("a token is recognised by shape, not by position", () => {
  assert.ok(looksLikeGhToken("ghp_" + "A".repeat(36)));
  assert.ok(looksLikeGhToken("gho_" + "A".repeat(36)));
  assert.ok(looksLikeGhToken("github_pat_" + "A".repeat(60)));
});

test("surrounding whitespace does not stop it being a token", () => {
  assert.ok(looksLikeGhToken("  ghp_" + "A".repeat(36) + "\n"));
});

test("things that are not tokens are not tokens", () => {
  assert.equal(looksLikeGhToken("hello"), false);
  assert.equal(looksLikeGhToken(""), false);
  assert.equal(looksLikeGhToken(null), false);
  assert.equal(looksLikeGhToken("ghp_short"), false);
  // A Telegraph token is 60 hex characters and must never be mistaken for one.
  assert.equal(looksLikeGhToken("a".repeat(60)), false);
});

test("the fine-grained token is told apart from the broad one", () => {
  assert.equal(ghTokenKind("github_pat_" + "A".repeat(60)), "fine");
  assert.equal(ghTokenKind("gho_" + "A".repeat(36)), "broad");
  assert.equal(ghTokenKind("ghp_" + "A".repeat(36)), "broad");
  assert.equal(ghTokenKind("nonsense"), null);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/site/token.test.mjs`
Expected: FAIL — `looksLikeGhToken is not a function`.

- [ ] **Step 3: Implement the pure half**

In the pure region:

```javascript
/* A GitHub token is recognised by its shape, the same way the bot
   recognises a pasted Telegraph token. gho_ is what `gh auth token` hands
   out and carries write access to private repositories; github_pat_ is the
   fine-grained kind that can be scoped to public reads. The difference is
   worth saying out loud to whoever pastes one. */
const GH_TOKEN = /^(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})$/;

const looksLikeGhToken = text =>
  typeof text === "string" && GH_TOKEN.test(text.trim());

function ghTokenKind(text) {
  if (!looksLikeGhToken(text)) return null;
  return text.trim().startsWith("github_pat_") ? "fine" : "broad";
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `node --test tests/site/token.test.mjs`
Expected: PASS, 4 tests.

- [ ] **Step 5: Implement the fetching half**

Below the pure region, after `ghTree` (index.html:932), add:

```javascript
/* The token raises the ceiling from 60 requests an hour to 5,000. It does
   not change what is asked for: the same four calls are made either way.
   sessionStorage, so it dies with the tab, and it is sent to api.github.com
   and nowhere else. */
const GH_TOKEN_KEY = "ghtoken";

const ghToken = () => {
  try { return sessionStorage.getItem(KEEP + GH_TOKEN_KEY) || null; }
  catch (err) { return null; }
};

class RateLimited extends Error {
  constructor() {
    super("GitHub is rate limiting this browser — try again in an hour, " +
          "or paste a token to raise the limit");
  }
}

async function ghApi(path) {
  const key = "api:" + path;
  const kept = cached(key, true);
  if (kept) return kept;

  const token = ghToken();
  const res = await fetch("https://api.github.com" + path,
    token ? { headers: { Authorization: "Bearer " + token } } : undefined);

  // 403 and 429 both mean the budget is gone; 401 means the token is bad,
  // and saying so is more use than saying "rate limited".
  if (res.status === 401) throw new Error("that token was refused by GitHub");
  if (res.status === 403 || res.status === 429) throw new RateLimited();
  if (!res.ok) throw new Error("GitHub had nothing at " + path);

  const data = await res.json();
  keep(key, data, true);
  return data;
}

/* The four calls a repository page costs, in parallel. Each is allowed to
   fail on its own: a rate-limited reader still gets every section whose
   data arrived, and the README always, because it never touches the API. */
async function ghRepoData(repo) {
  const ask = path => ghApi("/repos/" + repo + path).catch(err => ({ error: err }));

  const [meta, issues, releases, commits] = await Promise.all([
    ask(""),
    ask("/issues?state=all&per_page=100"),
    ask("/releases?per_page=100"),
    ask("/commits?per_page=100")
  ]);

  return { meta, issues, releases, commits };
}
```

- [ ] **Step 6: Verify the script still parses**

Run: `node --test tests/site/ && python -m pytest`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add index.html tests/site/token.test.mjs
git commit -m "Four calls, in parallel, each allowed to fail alone"
```

---

### Task 4: What the issues mean

**Files:**
- Modify: `index.html` — the pure region
- Create: `tests/site/issues.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces (all pure):
  - `splitIssues(list)` → `{issues, pulls}`
  - `deriveSections(issues)` → `[{name, key, items}]` — purpose-named groups
  - `filterIssues(issues, {state, labels, milestone, text})` → filtered array
  - `facetCounts(issues, filter)` → `{state:{}, labels:{}, milestones:{}}`

- [ ] **Step 1: Write the failing tests**

Create `tests/site/issues.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { splitIssues, deriveSections, filterIssues, facetCounts } = loadPure();

const issue = (n, o = {}) => ({
  number: n,
  title: o.title || ("issue " + n),
  state: o.state || "open",
  labels: (o.labels || []).map(name => ({ name })),
  milestone: o.milestone ? { title: o.milestone } : null,
  pull_request: o.pull ? { url: "x" } : undefined,
  updated_at: o.updated || "2026-07-01T00:00:00Z"
});

const SAMPLE = [
  issue(144, { title: "Recognise a pasted token by shape", labels: ["idea"] }),
  issue(141, { title: "Tree API budget on a cold reader", labels: ["bug"] }),
  issue(138, { title: "Byline modes on hand-written indexes", labels: ["docs"], milestone: "v1" }),
  issue(127, { title: "Escaped slash splits the route", labels: ["bug"], milestone: "v1" }),
  issue(94,  { title: "One token, several collections", labels: ["idea"], state: "closed" }),
  issue(145, { title: "Read the README name from the tree", labels: [], pull: true })
];

test("a pull request is an issue wearing a key", () => {
  const { issues, pulls } = splitIssues(SAMPLE);
  assert.equal(pulls.length, 1);
  assert.equal(pulls[0].number, 145);
  assert.equal(issues.length, 5);
  assert.ok(issues.every(i => !i.pull_request));
});

test("splitting survives an empty list", () => {
  assert.deepEqual(splitIssues([]), { issues: [], pulls: [] });
});

test("sections are named by purpose, not by query", () => {
  const { issues } = splitIssues(SAMPLE);
  const names = deriveSections(issues).map(s => s.key);
  assert.ok(names.includes("bugs"));
  assert.ok(names.includes("ideas"));
  assert.ok(names.includes("completed"));
});

test("a section with nothing in it is not shown", () => {
  const { issues } = splitIssues(SAMPLE);
  const sections = deriveSections(issues);
  assert.ok(sections.every(s => s.items.length > 0));
});

test("a repository whose labels do not match still gets sections", () => {
  const plain = [issue(1), issue(2, { state: "closed" })];
  const sections = deriveSections(plain);
  const keys = sections.map(s => s.key);
  assert.deepEqual(keys.sort(), ["completed", "open"].sort());
});

test("filtering by state", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { state: "open" }).length, 4);
  assert.equal(filterIssues(issues, { state: "closed" }).length, 1);
  assert.equal(filterIssues(issues, { state: "all" }).length, 5);
});

test("filtering by label, and by two things at once", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { labels: ["bug"] }).length, 2);
  assert.equal(
    filterIssues(issues, { state: "open", labels: ["bug"], milestone: "v1" }).length,
    1
  );
});

test("the text filter reads titles and labels", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "route" }).length, 1);
  assert.equal(filterIssues(issues, { text: "TOKEN" }).length, 2, "case is ignored");
  assert.equal(filterIssues(issues, { text: "docs" }).length, 1, "matches a label");
});

test("is: and label: are understood but never required", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "is:closed" }).length, 1);
  assert.equal(filterIssues(issues, { text: "label:bug" }).length, 2);
  assert.equal(filterIssues(issues, { text: "label:bug route" }).length, 1);
});

test("a filter matching nothing returns nothing, not everything", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "zzzz" }).length, 0);
});

test("no filter at all is every issue", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, {}).length, 5);
});

test("facet counts follow the filter, and zeroes are kept", () => {
  const { issues } = splitIssues(SAMPLE);
  const counts = facetCounts(issues, { labels: ["bug"] });
  assert.equal(counts.labels.bug, 2);
  assert.equal(counts.labels.idea, 0, "a facet that matches nothing must still be listed");
  assert.ok("idea" in counts.labels);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/site/issues.test.mjs`
Expected: FAIL — `splitIssues is not a function`.

- [ ] **Step 3: Implement**

In the pure region:

```javascript
/* In GitHub's REST API a pull request is an issue carrying a pull_request
   key, so one call answers both and the split happens here rather than in a
   second request. */
function splitIssues(list) {
  const all = Array.isArray(list) ? list : [];
  return {
    issues: all.filter(i => !i.pull_request),
    pulls: all.filter(i => !!i.pull_request)
  };
}

const labelsOf = i => (i.labels || []).map(l => (typeof l === "string" ? l : l.name));

/* Sections are named for what somebody wants — bugs, ideas, what is done —
   rather than for the query that finds them. A repository whose labels do
   not match simply shows fewer of them; Open and Completed always work,
   because state exists everywhere. */
const SECTION_RULES = [
  { key: "roadmap",   name: "Roadmap",      label: "roadmap", state: "open" },
  { key: "bugs",      name: "Bugs",         label: "bug",     state: "open" },
  { key: "features",  name: "Features",     label: "feature", state: "open" },
  { key: "ideas",     name: "Ideas",        label: "idea",    state: "open" },
  { key: "docs",      name: "Documentation", label: "docs",   state: "open" },
  { key: "open",      name: "Open",         label: null,      state: "open" },
  { key: "completed", name: "Completed",    label: null,      state: "closed" }
];

function deriveSections(issues) {
  const all = Array.isArray(issues) ? issues : [];

  return SECTION_RULES
    .map(rule => ({
      key: rule.key,
      name: rule.name,
      label: rule.label,
      items: all.filter(i =>
        i.state === rule.state &&
        (rule.label === null || labelsOf(i).includes(rule.label)))
    }))
    .filter(section => section.items.length > 0);
}

/* "is:open", "label:bug" and bare words in one field. The prefixes are
   understood so that somebody who knows them is not slowed down; nobody is
   ever required to type one. */
function parseFilterText(text) {
  const out = { state: null, labels: [], words: [] };

  for (const term of String(text || "").trim().split(/\s+/).filter(Boolean)) {
    const [head, ...tail] = term.split(":");
    const value = tail.join(":");

    if (value && head.toLowerCase() === "is") out.state = value.toLowerCase();
    else if (value && head.toLowerCase() === "label") out.labels.push(value.toLowerCase());
    else if (value && head.toLowerCase() === "milestone") out.milestone = value;
    else out.words.push(term.toLowerCase());
  }

  return out;
}

function filterIssues(issues, filter) {
  const all = Array.isArray(issues) ? issues : [];
  const f = filter || {};
  const typed = parseFilterText(f.text);

  const state = typed.state || f.state || "all";
  const labels = [...(f.labels || []), ...typed.labels].map(l => l.toLowerCase());
  const milestone = typed.milestone || f.milestone || null;

  return all.filter(i => {
    if (state !== "all" && i.state !== state) return false;

    const mine = labelsOf(i).map(l => l.toLowerCase());
    if (labels.length && !labels.every(l => mine.includes(l))) return false;

    if (milestone && (!i.milestone || i.milestone.title !== milestone)) return false;

    if (typed.words.length) {
      const hay = (i.title + " " + mine.join(" ")).toLowerCase();
      if (!typed.words.every(w => hay.includes(w))) return false;
    }

    return true;
  });
}

/* Both the facets and the field narrow the same set, so a facet's count is
   what would remain if it were also applied. A facet that falls to zero is
   still listed — the rail keeps its shape, and the reader can see what their
   typing excluded rather than watching options vanish. */
function facetCounts(issues, filter) {
  const all = Array.isArray(issues) ? issues : [];
  const f = filter || {};

  const countWith = extra => filterIssues(all, { ...f, ...extra }).length;

  const labels = {};
  for (const i of all) for (const l of labelsOf(i)) labels[l] = 0;
  for (const l of Object.keys(labels)) {
    labels[l] = countWith({ labels: [...(f.labels || []), l] });
  }

  const milestones = {};
  for (const i of all) if (i.milestone) milestones[i.milestone.title] = 0;
  for (const m of Object.keys(milestones)) milestones[m] = countWith({ milestone: m });

  return {
    state: {
      open: countWith({ state: "open" }),
      closed: countWith({ state: "closed" }),
      all: countWith({ state: "all" })
    },
    labels,
    milestones
  };
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/site/`
Expected: PASS, 25 tests.

- [ ] **Step 5: Commit**

```bash
git add index.html tests/site/issues.test.mjs
git commit -m "One payload, sliced by purpose rather than queried"
```

---

### Task 5: Activity, and who has been here

**Files:**
- Modify: `index.html` — the pure region
- Create: `tests/site/activity.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces (all pure):
  - `mergeActivity({commits, issues, releases})` → `[{kind, when, id, title}]`,
    newest first, where `kind` is `"commit" | "issue" | "pull" | "release"`.
  - `deriveContributors(commits)` → `[{name, count}]`, busiest first.
  - `countSince(commits, iso)` → number of commits at or after that instant.

- [ ] **Step 1: Write the failing tests**

Create `tests/site/activity.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { mergeActivity, deriveContributors, countSince } = loadPure();

const COMMITS = [
  { sha: "9be2aaa", commit: { message: "Sites and Web\n\nbody", author: { name: "Morgen", date: "2026-07-29T09:00:00Z" } } },
  { sha: "d0efbbb", commit: { message: "Stop serving a stale index", author: { name: "Morgen", date: "2026-07-28T09:00:00Z" } } },
  { sha: "a4aaccc", commit: { message: "A monogram", author: { name: "Ada", date: "2026-06-01T09:00:00Z" } } }
];

const ISSUES = [
  { number: 144, title: "Recognise a pasted token", created_at: "2026-07-28T12:00:00Z" },
  { number: 145, title: "Read the README name", created_at: "2026-07-27T12:00:00Z", pull_request: { url: "x" } }
];

const RELEASES = [
  { tag_name: "v0.4", name: "A cable in the gutter", published_at: "2026-07-28T18:00:00Z" }
];

test("everything lands on one timeline, newest first", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: ISSUES, releases: RELEASES });
  assert.equal(feed.length, 6);
  const times = feed.map(e => e.when);
  assert.deepEqual(times, [...times].sort().reverse());
});

test("each kind keeps its identity", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: ISSUES, releases: RELEASES });
  const kinds = new Set(feed.map(e => e.kind));
  assert.deepEqual([...kinds].sort(), ["commit", "issue", "pull", "release"]);
});

test("a commit is titled by its first line only", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: [], releases: [] });
  assert.equal(feed[0].title, "Sites and Web");
  assert.equal(feed[0].id, "9be2aaa".slice(0, 7));
});

test("missing sources are simply absent", () => {
  assert.deepEqual(mergeActivity({}), []);
  assert.equal(mergeActivity({ commits: COMMITS }).length, 3);
  assert.equal(mergeActivity({ commits: { error: new Error("x") } }).length, 0);
});

test("contributors are counted from authorship, busiest first", () => {
  const who = deriveContributors(COMMITS);
  assert.deepEqual(who, [{ name: "Morgen", count: 2 }, { name: "Ada", count: 1 }]);
});

test("a commit with no author does not become a contributor", () => {
  assert.deepEqual(deriveContributors([{ sha: "x", commit: { message: "m" } }]), []);
});

test("commits since an instant", () => {
  assert.equal(countSince(COMMITS, "2026-07-01T00:00:00Z"), 2);
  assert.equal(countSince(COMMITS, "2020-01-01T00:00:00Z"), 3);
  assert.equal(countSince([], "2026-07-01T00:00:00Z"), 0);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `node --test tests/site/activity.test.mjs`
Expected: FAIL — `mergeActivity is not a function`.

- [ ] **Step 3: Implement**

In the pure region:

```javascript
/* Each of the four calls may have failed on its own, so every source is
   checked for shape before it is read. A section missing from the timeline
   is better than a timeline that is not there. */
const listOf = value => (Array.isArray(value) ? value : []);

/* One chronological stream instead of four lists. Commits, issues, pull
   requests and releases are the same kind of event to somebody asking what
   has been happening. */
function mergeActivity(sources) {
  const s = sources || {};
  const out = [];

  for (const c of listOf(s.commits)) {
    const info = c.commit || {};
    out.push({
      kind: "commit",
      id: String(c.sha || "").slice(0, 7),
      title: String(info.message || "").split("\n")[0],
      when: (info.author || {}).date || ""
    });
  }

  for (const i of listOf(s.issues)) {
    out.push({
      kind: i.pull_request ? "pull" : "issue",
      id: "#" + i.number,
      title: i.title || "",
      when: i.created_at || ""
    });
  }

  for (const r of listOf(s.releases)) {
    out.push({
      kind: "release",
      id: r.tag_name || "",
      title: r.name || r.tag_name || "",
      when: r.published_at || r.created_at || ""
    });
  }

  return out.filter(e => e.when).sort((a, b) => (a.when < b.when ? 1 : -1));
}

/* /contributors would be a fifth call for one line of the facts rail. The
   authors of the commits already fetched answer the question well enough,
   and the rail says "recent" so the number is not claimed to be more. */
function deriveContributors(commits) {
  const tally = new Map();

  for (const c of listOf(commits)) {
    const name = ((c.commit || {}).author || {}).name;
    if (name) tally.set(name, (tally.get(name) || 0) + 1);
  }

  return [...tally.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function countSince(commits, iso) {
  return listOf(commits).filter(c => {
    const when = ((c.commit || {}).author || {}).date;
    return when && when >= iso;
  }).length;
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `node --test tests/site/`
Expected: PASS, 32 tests.

- [ ] **Step 5: Commit**

```bash
git add index.html tests/site/activity.test.mjs
git commit -m "One timeline, and contributors counted rather than fetched"
```

---

### Task 6: The chrome — width, rail, strip

**Files:**
- Modify: `index.html` — CSS after the `.bar` rules (index.html:95–130 area)
- Modify: `index.html` — `show()` (index.html:2574)

**Interfaces:**
- Consumes: `ghSection` (Task 2).
- Produces:
  - `document.body.classList.toggle("wide", …)` set on every route change.
  - `sectionRail(repo, active, counts)` → `HTMLElement`
  - `healthStrip(meta, issues, releases)` → `HTMLElement`

- [ ] **Step 1: Add the CSS**

After the `.bar` block, add:

```css
/* A repository page is a denser thing than an article and wants more room.
   --col is the only width control on the site, so this changes that one
   value rather than introducing a second column: every .col element still
   resolves to an identical inline box, and the bar and the content still
   share one left edge. Nothing here sets padding-inline or margin-inline. */
body.wide{--col:68rem}

/* The sections of a repository. Mono uppercase like every other small label
   here, and the lamp marks the section you are in — a live state, which is
   the only thing it is allowed to mark. */
.rail{
  display:flex;gap:1.25rem;
  border-bottom:1px solid var(--hair);
  padding-block:.45rem;
  overflow-x:auto;
  scrollbar-width:none;
  -webkit-mask-image:linear-gradient(90deg,#000 92%,transparent);
  mask-image:linear-gradient(90deg,#000 92%,transparent);
}
.rail::-webkit-scrollbar{display:none}
.rail a{
  font-family:var(--mono);font-size:.7rem;
  text-transform:uppercase;letter-spacing:.08em;
  color:var(--graphite);text-decoration:none;white-space:nowrap;
}
.rail a[aria-current]{
  color:var(--ink);
  box-shadow:0 .4rem 0 -.32rem var(--lamp);
}
.rail sup{font-size:.85em;margin-left:.15rem}

.strip{
  font-family:var(--mono);font-size:.65rem;
  text-transform:uppercase;letter-spacing:.07em;
  color:var(--graphite);
  display:flex;gap:1rem;flex-wrap:wrap;
  padding-bottom:.7rem;
}
.strip b{font-weight:400;color:var(--ink)}
.strip .live{color:var(--lamp)}

/* The dashboard's two tracks. Below the width that fits a 15rem rail the
   grid collapses and the rail's contents become a chip row instead. */
.dash{display:grid;grid-template-columns:1fr 15rem;gap:1.6rem}
@media (max-width:48rem){ .dash{grid-template-columns:1fr;gap:1rem} }
```

- [ ] **Step 2: Write the rail and strip**

Below the pure region, near `showIndex` (index.html:1743):

```javascript
const RAIL = [
  { key: "overview",  name: "Overview",    at: "" },
  { key: "code",      name: "Code",        at: null },   // a tree route, not a section
  { key: "issues",    name: "Development", at: "issues" },
  { key: "releases",  name: "Releases",    at: "releases" },
  { key: "pulse",     name: "Activity",    at: "pulse" }
];

function sectionRail(master, repo, active, counts) {
  const nav = el("nav", "rail");

  for (const item of RAIL) {
    const id = item.key === "code" ? "ght:" + repo
             : item.at ? "gh:" + repo + "@" + item.at
             : "gh:" + repo;

    const a = el("a", null, item.name);
    a.href = link(master, id);
    if (item.key === active) a.setAttribute("aria-current", "page");

    const n = counts[item.key];
    if (n != null) a.appendChild(el("sup", null, String(n)));

    nav.appendChild(a);
  }

  return nav;
}

/* Updated, licence, stars, what is open, what is newest. The open count is
   a live state and so is allowed the lamp; nothing else on this line is. */
function healthStrip(meta, open, latest) {
  const strip = el("div", "strip");
  const add = (label, value, live) => {
    if (value == null || value === "") return;
    const span = el("span", live ? "live" : null);
    if (label) span.append(label + " ");
    span.appendChild(el("b", null, String(value)));
    strip.appendChild(span);
  };

  if (meta.pushed_at) add("Updated", ago(meta.pushed_at));
  if (meta.license && meta.license.spdx_id) add("", meta.license.spdx_id);
  if (meta.stargazers_count) add("★", meta.stargazers_count);
  if (open) add("● ", open + " open", true);
  if (latest) add("", latest);

  return strip;
}

/* "2 hours ago" without a library and without Intl.RelativeTimeFormat's
   locale surprises — the site formats its dates by hand elsewhere for the
   same reason (index.html:1006). */
function ago(iso) {
  const then = Date.parse(iso);
  if (!then) return "";

  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 60) return mins + "m ago";
  if (mins < 1440) return Math.round(mins / 60) + "h ago";
  if (mins < 43200) return Math.round(mins / 1440) + "d ago";
  return Math.round(mins / 43200) + "mo ago";
}
```

- [ ] **Step 3: Set the width from the route**

In `show(r)` (index.html:2574), at the top of the function, add:

```javascript
  // A repository is the only thing here that is wider than the reading
  // measure. Set from the route so that leaving one puts it back.
  document.body.classList.toggle("wide", !!ghSection(r.article));
```

- [ ] **Step 4: Check it by eye**

Run: `python3 -m http.server 8000` and open
`http://localhost:8000/#<a-master-path>/github.com/babbworks/telepatch`

Expected: the page is wider than an article, the bar's title and the content
still share a left edge, and the console shows no `[telepatch] left edges
differ` warning from `checkAlign` (index.html:2618).

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "A wider measure for a denser page, from the route"
```

---

### Task 7: Overview

**Files:**
- Modify: `index.html` — near `showIndex` (index.html:1743)

**Interfaces:**
- Consumes: `ghRepoData` (3), `splitIssues`/`deriveSections` (4),
  `mergeActivity`/`deriveContributors`/`countSince` (5), `sectionRail`/`healthStrip` (6).
- Produces: `showRepo(master, repo, data)` → renders Overview into `#view`.

- [ ] **Step 1: Write the facts rail and the blocks**

```javascript
/* The blocks answer "what is happening"; the rail beside them answers "what
   is this". The README runs full width beneath both, where a long one
   cannot push the dashboard off the screen. */
function factsRail(meta, issues, pulls, releases, commits) {
  const rail = el("aside", "facts");
  const row = (label, value) => {
    if (value == null || value === "") return;
    const d = el("div");
    d.append(el("span", null, label), el("b", null, String(value)));
    rail.appendChild(d);
  };

  const latest = listOf(releases)[0];
  if (latest) {
    row("Latest", latest.tag_name);
    row("Released", fmtDate((latest.published_at || "").slice(0, 10)));
  }

  const open = issues.filter(i => i.state === "open");
  const milestone = (open.find(i => i.milestone) || {}).milestone;
  if (milestone) {
    row("Milestone", milestone.title + " · " +
      milestone.closed_issues + "/" + (milestone.open_issues + milestone.closed_issues));
  }

  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString();
  row("Commits 30d", countSince(commits, monthAgo));

  const who = deriveContributors(commits);
  if (who.length) row("Recent contributors", who.length);

  row("Default", meta.default_branch);
  row("Open PRs", pulls.filter(p => p.state === "open").length || null);
  if (meta.topics && meta.topics.length) row("Topics", meta.topics.join(" · "));

  return rail;
}

function overviewBlocks(master, repo, issues, releases, commits) {
  const wrap = el("div");

  const block = (title, href, rows) => {
    if (!rows.length) return;
    const h = el("h3", null, title);
    if (href) {
      const more = el("a", null, "all →");
      more.href = href;
      h.appendChild(more);
    }
    wrap.appendChild(h);

    const list = el("div", "rows");
    for (const [id, text, tag] of rows.slice(0, 4)) {
      const row = el("div", "row");
      row.append(el("span", "n", id), el("span", "t", text));
      if (tag) row.appendChild(el("span", "tag", tag));
      list.appendChild(row);
    }
    wrap.appendChild(list);
  };

  const open = issues.filter(i => i.state === "open");
  block("In progress", link(master, "gh:" + repo + "@issues"),
    open.map(i => ["#" + i.number, i.title, labelsOf(i)[0] || ""]));

  block("Recent", link(master, "gh:" + repo + "@pulse"),
    mergeActivity({ commits }).map(e => [e.id, e.title, ""]));

  block("Releases", link(master, "gh:" + repo + "@releases"),
    listOf(releases).map(r => [r.tag_name, r.name || r.tag_name, ""]));

  return wrap;
}
```

- [ ] **Step 2: Add the CSS for the rows and rail**

```css
.facts div{
  display:flex;justify-content:space-between;gap:.75rem;
  font-family:var(--mono);font-size:.66rem;
  text-transform:uppercase;letter-spacing:.05em;
  color:var(--graphite);
  padding-block:.25rem;border-bottom:1px solid var(--hair);
}
.facts div b{font-weight:400;color:var(--ink);text-align:right}
.rows .row{
  display:flex;gap:.55rem;align-items:baseline;
  padding-block:.3rem;border-bottom:1px solid var(--hair);
}
.rows .row:last-child{border-bottom:0}
.row .n{font-family:var(--mono);font-size:.7rem;color:var(--graphite);flex:none;min-width:3rem}
.row .t{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .tag{
  font-family:var(--mono);font-size:.6rem;flex:none;
  text-transform:uppercase;letter-spacing:.06em;color:var(--graphite);
  border:1px solid var(--hair);border-radius:2px;padding-inline:.25rem;
}
.dash h3{
  font-family:var(--mono);font-size:.65rem;font-weight:400;
  text-transform:uppercase;letter-spacing:.09em;color:var(--graphite);
  display:flex;margin:1rem 0 .35rem;
}
.dash h3 a{margin-left:auto;text-decoration:none}
.dash h3:first-child{margin-top:0}
```

- [ ] **Step 3: Wire it into `show()`**

```javascript
async function showRepo(master, repo, data) {
  const view = $("view");
  const meta = data.meta.error ? {} : data.meta;
  const { issues, pulls } = splitIssues(data.issues.error ? [] : data.issues);
  const releases = data.releases.error ? [] : data.releases;
  const commits = data.commits.error ? [] : data.commits;

  const head = el("header", "col");
  head.appendChild(el("h1", null, repo.split("/")[1]));
  if (meta.description) head.appendChild(el("p", "dek", meta.description));
  head.appendChild(healthStrip(
    meta,
    issues.filter(i => i.state === "open").length,
    (releases[0] || {}).tag_name
  ));
  head.appendChild(sectionRail(master, repo, "overview", {
    code: null,
    issues: issues.filter(i => i.state === "open").length || null,
    releases: releases.length || null
  }));
  view.appendChild(head);

  const dash = el("div", "col dash");
  dash.append(
    overviewBlocks(master, repo, issues, releases, commits),
    factsRail(meta, issues, pulls, releases, commits)
  );
  view.appendChild(dash);

  // The README beneath, full width, exactly as it renders today.
  const readme = await ghFetch("gh:" + repo).catch(() => null);
  if (readme) {
    const prose = el("article", "col");
    renderMarkdown(readme.text, prose, rawBase(repo));
    view.appendChild(prose);
  }
}
```

- [ ] **Step 4: Check it by eye**

Open a repository route. Expected: strip, rail, two tracks, README beneath,
four `api.github.com` requests in the network panel and no more.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Overview: what this is, and what is happening"
```

---

### Task 8: Development

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `filterIssues`, `facetCounts`, `deriveSections` (Task 4).
- Produces: `showDevelopment(master, repo, data)`.

- [ ] **Step 1: Write the pane**

```javascript
/* The facets and the field narrow the same set, so both are read from one
   filter object and both are redrawn whenever either changes. Nothing here
   costs a request: it is all slicing the one payload already fetched. */
function showDevelopment(master, repo, data) {
  const { issues } = splitIssues(data.issues.error ? [] : data.issues);
  const filter = { state: "open", labels: [], milestone: null, text: "" };

  const dash = el("div", "col dash");
  const left = el("div");
  const right = el("aside", "facets");
  dash.append(left, right);

  const field = el("input", "find");
  field.type = "search";
  field.placeholder = "filter";
  field.setAttribute("aria-label", "Filter issues");

  const said = el("p", "active");
  const list = el("div", "rows");

  left.append(field, said, list);

  const draw = () => {
    const shown = filterIssues(issues, filter);
    const counts = facetCounts(issues, filter);

    list.textContent = "";
    for (const i of shown) {
      const row = el("div", "row");
      row.append(el("span", "n", "#" + i.number), el("span", "t", i.title));
      const label = labelsOf(i)[0];
      if (label) row.appendChild(el("span", "tag", label));
      list.appendChild(row);
    }
    if (!shown.length) list.appendChild(el("p", "empty", "Nothing matches that."));

    // One line saying what is showing, because two mechanisms narrowing one
    // list is otherwise easy to lose track of.
    const bits = [];
    if (filter.state !== "all") bits.push(filter.state);
    for (const l of filter.labels) bits.push("label:" + l);
    if (filter.milestone) bits.push("milestone:" + filter.milestone);
    if (filter.text) bits.push('"' + filter.text + '"');

    said.textContent = "";
    said.append("Showing " + shown.length + " of " + issues.length +
                (bits.length ? " — " + bits.join(" · ") : ""));
    if (bits.length) {
      const clear = el("button", "clear", "clear ×");
      clear.onclick = () => {
        filter.state = "all"; filter.labels = []; filter.milestone = null;
        filter.text = ""; field.value = ""; draw();
      };
      said.appendChild(clear);
    }

    drawFacets(right, counts, filter, draw);
  };

  field.addEventListener("input", () => { filter.text = field.value; draw(); });
  draw();

  return dash;
}

/* A facet whose count falls to zero dims rather than disappearing, so the
   rail keeps its shape and the reader can see what their typing excluded. */
function drawFacets(host, counts, filter, redraw) {
  host.textContent = "";

  const group = (title, entries, isOn, toggle) => {
    if (!entries.length) return;
    host.appendChild(el("h4", null, title));

    for (const [name, n] of entries) {
      const a = el("a", n === 0 ? "dim" : null);
      a.href = "#";
      a.append(el("span", null, name), el("span", null, String(n)));
      if (isOn(name)) a.classList.add("on");
      a.onclick = e => { e.preventDefault(); toggle(name); redraw(); };
      host.appendChild(a);
    }
  };

  group("State", Object.entries(counts.state),
    name => filter.state === name,
    name => { filter.state = name; });

  group("Label", Object.entries(counts.labels),
    name => filter.labels.includes(name),
    name => {
      const at = filter.labels.indexOf(name);
      if (at < 0) filter.labels.push(name); else filter.labels.splice(at, 1);
    });

  group("Milestone", Object.entries(counts.milestones),
    name => filter.milestone === name,
    name => { filter.milestone = filter.milestone === name ? null : name; });
}
```

- [ ] **Step 2: CSS, including the narrow-width chip row**

```css
.find{
  width:100%;font-family:var(--mono);font-size:.85rem;
  background:none;color:var(--ink);
  border:0;border-bottom:1px solid var(--ink);
  padding-block:.3rem;
}
.active{
  font-family:var(--mono);font-size:.62rem;
  text-transform:uppercase;letter-spacing:.06em;
  color:var(--graphite);display:flex;gap:.6rem;align-items:baseline;
  margin:.4rem 0 .6rem;
}
.active .clear{
  background:none;border:0;padding:0;cursor:pointer;
  font:inherit;color:var(--lamp);
}
.facets h4{
  font-family:var(--mono);font-size:.62rem;font-weight:400;
  text-transform:uppercase;letter-spacing:.09em;
  color:var(--graphite);margin:.9rem 0 .25rem;
}
.facets h4:first-child{margin-top:0}
.facets a{
  display:flex;justify-content:space-between;
  font-family:var(--mono);font-size:.66rem;
  color:var(--ink);text-decoration:none;
  padding-block:.18rem;border-bottom:1px solid var(--hair);
}
.facets a span:last-child{color:var(--graphite)}
.facets a.on,.facets a.on span:last-child{color:var(--patch)}
.facets a.dim{opacity:.35}

/* Narrow: the facet rail becomes a chip row above the list. It is the same
   markup restyled — one component, not a phone-only second one — because a
   filter nobody can see is a filter nobody uses. */
@media (max-width:48rem){
  .facets{display:flex;flex-wrap:wrap;gap:.35rem;order:-1;margin-bottom:.5rem}
  .facets h4{display:none}
  .facets a{
    border:1px solid var(--hair);border-radius:2px;
    padding:.05rem .35rem;font-size:.62rem;gap:.3rem;
  }
  .facets a.on{background:var(--patch);border-color:var(--patch);color:var(--paper)}
  .facets a.on span:last-child{color:var(--paper);opacity:.6}
}
```

- [ ] **Step 3: Check it by eye**

Open `…/github.com/babbworks/telepatch/issues`. Expected: typing narrows
both list and facet counts; a zeroed facet dims rather than vanishing;
clicking two facets combines them; `clear ×` resets; **no new network
requests** while filtering. Narrow the window past 48rem — the rail becomes
chips above the list.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "Development: two ways to narrow one payload"
```

---

### Task 9: Releases and Activity

**Files:**
- Modify: `index.html`

**Interfaces:**
- Consumes: `mergeActivity` (Task 5).
- Produces: `showReleases(master, repo, data)`, `showActivity(master, repo, data)`.

- [ ] **Step 1: Write both panes**

```javascript
function showReleases(master, repo, data) {
  const wrap = el("div", "col");
  const releases = data.releases.error ? [] : data.releases;

  if (!releases.length) {
    wrap.appendChild(el("p", "empty", "No releases."));
    return wrap;
  }

  for (const r of releases) {
    const head = el("h3", null, r.tag_name + " — " + (r.name || ""));
    head.appendChild(el("span", null, fmtDate((r.published_at || "").slice(0, 10))));
    wrap.appendChild(head);

    if (r.body) {
      const prose = el("div", "notes");
      renderMarkdown(r.body, prose, rawBase(repo));
      wrap.appendChild(prose);
    }

    for (const asset of (r.assets || [])) {
      const row = el("div", "row");
      const a = el("a", "t", asset.name);
      a.href = asset.browser_download_url;
      a.rel = "noopener";
      row.append(a, el("span", "tag", Math.round(asset.size / 1024) + " kB"));
      wrap.appendChild(row);
    }
  }

  return wrap;
}

/* Four lists become one stream, because "what has been happening" is one
   question and GitHub only answers it in four places. */
function showActivity(master, repo, data) {
  const wrap = el("div", "col");
  const feed = mergeActivity({
    commits: data.commits.error ? [] : data.commits,
    issues: data.issues.error ? [] : data.issues,
    releases: data.releases.error ? [] : data.releases
  });

  if (!feed.length) {
    wrap.appendChild(el("p", "empty", "Nothing to show."));
    return wrap;
  }

  let day = null;
  const list = el("div", "rows");

  for (const e of feed) {
    const on = e.when.slice(0, 10);
    if (on !== day) {
      day = on;
      list.appendChild(el("h3", null, fmtDate(on)));
    }

    const row = el("div", "row");
    row.append(
      el("span", "n", e.id),
      el("span", "t", e.title),
      el("span", "tag", e.kind)
    );
    list.appendChild(row);
  }

  wrap.appendChild(list);
  return wrap;
}
```

- [ ] **Step 2: Route to every pane**

In `show(r)`, where a GitHub resource is currently handled, add:

```javascript
  const part = ghSection(r.article);
  if (part) {
    const data = await ghRepoData(part.repo);
    const view = $("view");

    if (part.section === "overview") { await showRepo(r.master, part.repo, data); return; }

    const head = el("header", "col");
    head.appendChild(el("h1", null, part.repo.split("/")[1]));
    head.appendChild(sectionRail(r.master, part.repo, part.section, {}));
    view.appendChild(head);

    if (part.section === "issues")   view.appendChild(showDevelopment(r.master, part.repo, data));
    if (part.section === "releases") view.appendChild(showReleases(r.master, part.repo, data));
    if (part.section === "pulse")    view.appendChild(showActivity(r.master, part.repo, data));
    if (part.section === "issue")    view.appendChild(showIssue(part.arg, data));
    return;
  }
```

And the single-issue pane:

```javascript
function showIssue(number, data) {
  const wrap = el("div", "col");
  const all = data.issues.error ? [] : data.issues;
  const found = all.find(i => String(i.number) === String(number));

  // The list is the last 100. An older issue is simply not in hand, and
  // saying so beats a spinner that never resolves.
  if (!found) {
    wrap.appendChild(el("p", "empty", "Issue #" + number + " is not among the recent hundred."));
    return wrap;
  }

  wrap.appendChild(el("h1", null, found.title));
  const meta = el("p", "strip");
  meta.append(el("b", null, "#" + found.number), " ", found.state, " · ",
              fmtDate((found.created_at || "").slice(0, 10)));
  wrap.appendChild(meta);

  /* An issue body is the one thing here written by somebody the publisher
     did not choose — on a public repository anybody can open one. Rendering
     its images would let a stranger point every reader's browser at a host
     of their choosing, so images become links instead. Release notes are
     different: they are written by people with push access, which is the
     same trust the README already gets. */
  if (found.body) {
    const prose = el("div", "notes");
    renderMarkdown(found.body, prose, "", { images: false });
    wrap.appendChild(prose);
  }

  return wrap;
}
```

`renderMarkdown` gains a fourth argument, defaulting to images on, so every
existing caller is unchanged. In `mdInline` (index.html:1390), where an
image is emitted, add:

```javascript
    // Off for text the publisher did not write. The address still reaches
    // the reader, as a link they choose to follow rather than a request
    // their browser makes for them.
    if (opts && opts.images === false) {
      const a = el("a", null, alt || url);
      a.href = mdUrl(url, base);
      a.rel = "noopener nofollow";
      parent.appendChild(a);
      return;
    }
```

- [ ] **Step 3: Check it by eye**

Visit `/releases`, `/pulse`, and `/issues/144`. Expected: each renders,
the rail marks the right section, and **no further network requests** —
all four panes read the same cached payloads.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "Releases, one timeline, and a single issue"
```

---

### Task 10: The token, degradation, and the docs

**Files:**
- Modify: `index.html`
- Modify: `README.md`
- Modify: `index.html` — remove the `/readme` fallback (index.html:985–995)

**Interfaces:**
- Consumes: `looksLikeGhToken`, `ghTokenKind` (Task 3), `ghTree` (existing).
- Produces: `tokenField()` → `HTMLElement`; `ghFetch` no longer calls `/readme`.

- [ ] **Step 1: The paste field**

```javascript
/* Anonymous readers get 60 requests an hour, which is about twelve
   repository views. A token raises that to 5,000. It is held for the life
   of the tab and sent to api.github.com and nowhere else — but it is still
   a credential in a browser, which is a real exception to this site's one
   rule, so the field says what it is taking. */
function tokenField() {
  const wrap = el("div", "tokenbox");
  const field = el("input", "find");
  field.type = "password";
  field.placeholder = "paste a GitHub token to raise the limit";
  field.setAttribute("aria-label", "GitHub token");

  const note = el("p", "active");
  wrap.append(field, note);

  field.addEventListener("input", () => {
    const kind = ghTokenKind(field.value);

    if (!kind) {
      note.textContent = field.value ? "That is not the shape of a GitHub token." : "";
      return;
    }

    try { sessionStorage.setItem(KEEP + GH_TOKEN_KEY, field.value.trim()); }
    catch (err) { note.textContent = "This browser will not keep it."; return; }

    note.textContent = kind === "fine"
      ? "Kept for this tab only. Reload to use it."
      : "Kept — but this is a broad token: `gh auth token` can write to your " +
        "private repositories. A fine-grained token, public repositories, " +
        "read-only, is the one to use here.";
  });

  return wrap;
}
```

- [ ] **Step 2: Degrade per section**

Wherever a pane reads `data.<x>.error`, render the reason in place:

```javascript
function paneError(err) {
  const p = el("p", "empty");
  p.textContent = err instanceof RateLimited
    ? "GitHub is rate limiting this browser. Read still works — it does not " +
      "touch the API — and a token raises the limit."
    : "GitHub did not answer for this section.";
  return p;
}
```

Append `tokenField()` beneath any `RateLimited` pane error.

- [ ] **Step 3: Read the README name from the tree**

Replace index.html:985–995 with:

```javascript
  let res = await fetch(raw("README.md"));
  if (res.ok) return { text: await res.text(), name: "README.md", owner, repo };

  // Not README.md. The tree already names every file in the repository, so
  // the name is read from there rather than bought from the API — one call
  // either way, and the tree is wanted the moment Code is opened anyway.
  const tree = await ghTree(owner, repo);
  const found = (tree || []).find(e =>
    !e.dir && /^readme(\.|$)/i.test(e.name) && !e.name.includes("/"));
  if (!found) throw new Error("no README in that repository");

  res = await fetch(raw(found.name));
  if (!res.ok) throw new Error("no README in that repository");
  return { text: await res.text(), name: found.name, owner, repo };
```

- [ ] **Step 4: Document it**

In `README.md`, replace the paragraph beginning *"A repository's page leads
with its contents and carries the README underneath"* with:

```markdown
A repository opens as a dashboard. Five sections — Overview, Code,
Development, Releases and Activity — sit behind a rail, and each is
addressed the way GitHub addresses it, so putting `https://` in front of
the second half of any of them gives you the same page at the source:

```
…/#<master-path>/github.com/babbworks/telepatch
…/#<master-path>/github.com/babbworks/telepatch/issues
…/#<master-path>/github.com/babbworks/telepatch/releases
…/#<master-path>/github.com/babbworks/telepatch/pulse
```

Overview carries what GitHub knows about the repository, with the README
beneath it. Development is every issue and pull request, filtered by facets
and by a text field that narrow the same set — none of which costs a
request, because they are slices of one payload already fetched.

Arriving at a repository costs four calls to `api.github.com`; the file
tree is a fifth, spent only when Code is opened. That API allows **60 an
hour per reader**, so about a dozen repository views. Pasting a GitHub
token raises it to 5,000. The token is kept for the life of the tab, sent
to `api.github.com` and nowhere else, and never written anywhere durable —
but it is still a credential in a browser, which is the second exception
this project makes, after the extension. Use a fine-grained token scoped to
public repositories, read-only; **not** what `gh auth token` gives you,
which can write to your private repositories.

A rate-limited reader still gets the README, because that comes from
`raw.githubusercontent.com`, which is not rate limited at all.
```

- [ ] **Step 5: Run everything**

Run: `node --test tests/site/ && python -m pytest`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add index.html README.md
git commit -m "A token raises the ceiling, and says what it is taking"
```

---

## Self-review notes

Checked against `docs/superpowers/specs/2026-07-29-repo-dashboard-design.md`:

- Routing → Task 2. Requests → Task 3. Filtering → Task 4. Activity and
  derived contributors → Task 5. Width and rails → Tasks 6–8. Token → Tasks
  3 and 10. Per-section failure → Task 10. README-from-tree → Task 10.
  Testing → Task 1, extended by every later task.
- The spec's claim that the script can be evaluated whole is wrong — it is an
  IIFE. Task 1 fences a pure region instead. **Update the spec's Testing
  section to match before implementing.**
- Names used across tasks: `ghSection`, `ghRepoData`, `splitIssues`,
  `labelsOf`, `listOf`, `filterIssues`, `facetCounts`, `mergeActivity`,
  `deriveContributors`, `countSince`, `sectionRail`, `healthStrip`, `ago`,
  `link`, `el`, `fmtDate`, `renderMarkdown`, `ghFetch`, `ghTree`, `cached`,
  `keep`, `KEEP`. The last nine already exist in `index.html`.
- `rawBase(repo)` is used by Tasks 7 and 9 and does not exist yet. It is a
  one-line helper — `const rawBase = repo => "https://raw.githubusercontent.com/" + repo + "/HEAD/";`
  — and belongs beside `ghFetch` in Task 7, Step 1.
