# The repository dashboard

A repository entry currently opens as its README with its contents above.
This makes it open as a dashboard: five sections behind a rail, carrying as
much of what GitHub knows about the repository as can be had inside the
reader's request budget.

Nothing about how a repository is *added* changes. `/repo` writes the same
entry line, `/site` reads it back the same way, and the index looks
identical. The whole feature lives in `index.html`.

---

## The one constraint

`raw.githubusercontent.com` is a CDN: cross-origin, unmetered, no token.
`api.github.com` is metered at **60 requests an hour, per reader**. Every
section except Read is on the metered side, and the budget — not the layout
— is what decides how much of a dashboard is possible.

So the design is written backwards from five calls.

---

## Routing

Sections are addressed the way GitHub addresses them, so the existing
invariant holds: put `https://` in front of the second half and you have the
page at the source.

```
…/#<master>/github.com/o/r                   Overview  (README beneath)
…/#<master>/github.com/o/r/tree/HEAD/docs    Code
…/#<master>/github.com/o/r/issues            Development
…/#<master>/github.com/o/r/issues/144        one issue
…/#<master>/github.com/o/r/releases          Releases
…/#<master>/github.com/o/r/pulse             Activity
```

**There are five sections, not six.** Read is not one of them: GitHub has no
`/readme` path, so a separate Read route could not be a real github.com
address, and inventing one would break the invariant this scheme rests on.

Instead the README sits beneath the Overview blocks on the bare repository
route — which is what github.com itself does, and what that URL already does
today. Every link already published therefore lands on a page that still
shows the README, with the dashboard above it.

In `ghFromParts` (index.html:691) these are new values of `kind` alongside
`blob` and `tree`. Unlike those two they carry no git ref, so `parts[4]` is
part of the resource rather than a ref to skip. `ghToParts` reverses it.
`route()` and `link()` need no structural change: a section is still one
article-shaped path, and a heading inside one still uses the second `#`.

Links written before this change continue to resolve, because a bare
`github.com/o/r` path still parses — it simply lands on Overview instead of
the README.

---

## Requests

Four calls when a repository is opened. The tree is spent only if Code is.

| Call | Feeds |
|---|---|
| `/repos/{o}/{r}` | health strip, facts rail |
| `/repos/{o}/{r}/issues?state=all&per_page=100` | every part of Development, PR counts, milestone progress, the issue half of Activity |
| `/repos/{o}/{r}/releases` | Releases, and the latest version in the strip |
| `/repos/{o}/{r}/commits` | Activity, commits in 30 days, and recent contributors |
| `/repos/{o}/{r}/git/trees/HEAD?recursive=1` | Code — **on demand only** |

Two economies are load-bearing:

**Pull requests come free with issues.** In the REST API a pull request *is*
an issue carrying a `pull_request` key. One fetch yields both, and every
section of Development is a client-side slice of it rather than a query.

**Contributors are derived, not fetched.** `/contributors` would be a sixth
call for one line of the facts rail. The authors of the last 30 commits
answer the question well enough, and the rail says *recent contributors* so
the number is not claimed to be something it isn't.

The README stays on `raw`, costing nothing in the ordinary case. The
existing fallback to `/repos/{o}/{r}/readme` (index.html:989) is removed:
when `README.md` is absent, the name is read from the tree instead of bought
from the API. That does mean a repository whose README is named something
else pulls the tree on arrival rather than on demand — one call either way,
and the tree is wanted the moment Code is opened regardless.

### The budget in practice

Anonymous, five metered calls per repository, twelve views in an hour.
That is comfortable for a publication with a few repositories and thin for
browsing. It is the honest ceiling, and the reader is told when they reach
it rather than shown an empty page.

### Failure is per section

A section that cannot be fetched says so in its own pane and leaves the rest
of the dashboard standing. **Read never fails from rate limiting**, because
it is the only section that never touches the API — so a rate-limited reader
still gets what a repository entry gives them today.

Caching is the existing `cached`/`keep` pair over `sessionStorage`
(index.html:816–830): the life of the tab, long enough to survive a reload,
short enough that nobody reads a stale repository tomorrow.

---

## The token

A reader may paste a GitHub token to raise the ceiling from 60 to 5,000 an
hour. It is recognised by shape rather than by position, the same way the
bot recognises a Telegraph token: `gho_`, `ghp_`, `ghu_`, `ghs_`,
`github_pat_`.

It is held in `sessionStorage`, dies with the tab, and is sent to
`api.github.com` and nowhere else. The site still stores nothing durable and
still makes no third-party request.

**The token raises the ceiling. It does not change the request shape.** The
same five REST calls are made either way. GraphQL — which would collapse
them into one, and which is the only route to Discussions and Projects — is
deliberately out of scope here.

`gh auth token` is the convenient way to get one and the wrong token to use:
its default scopes include `repo`, which is full read and write over private
repositories. The paste field says so when the shape is anything other than
`github_pat_`, and points at a fine-grained token scoped to public
repositories, read-only.

---

## Layout

A rail of five sections sits under the publication's own bar, in mono
uppercase at `.08em`, with counts as superscripts. The lamp marks the active
section and live counts, and nothing else — the palette comment at
index.html:10 reserves it for live and active states, and a dashboard is
exactly where that rule stops being decorative.

Above the rail, a health strip: updated, licence, stars, open count, latest
version.

### Width

Repository routes widen the measure from `52rem` to `68rem` by setting
`--col` on a body class, not by introducing a second column class.

This preserves the invariant in the comment at index.html:88 — every element
carrying `.col` still resolves to an identical inline box, and the bar and
the content still share one left edge. The box is simply wider on these
routes. Nothing sets `padding-inline` or `margin-inline` on a `.col`
element, so the warning there stays satisfied.

The frame therefore changes width when a reader moves between an article and
a repository. This is deliberate and happens only on a full route change; it
is not the involuntary mid-page shift that `scrollbar-gutter:stable`
(index.html:76) exists to prevent.

### The rails

Overview carries a **facts rail** on the right: latest release and its date,
milestone progress, commits in 30 days, recent contributors, default branch,
open PRs, size, language proportions, topics. Its blocks — In progress,
Recent, Releases — sit to the left of the rail, and the README runs full
width beneath both, where a long one cannot push the dashboard off screen.

Development carries a **facet rail** in the same position: state, labels,
milestone — combinable, with counts that follow the current filter.

Each section's rail serves that section. There is no rail that persists
across sections.

### Narrow widths

Below the width that fits a 15rem rail:

- the section rail scrolls sideways under a mask
- the facet rail becomes a chip row above the list
- the filter line is unchanged — it costs one row at any width

The chip row is one component, built once, used at both widths.

---

## Filtering

Every filter is a slice of the single `/issues` payload. Nothing a reader
does in Development costs a request.

Two mechanisms narrow one set:

- **the facet rail** — state, label, milestone, combinable
- **the filter line** — live text matching over titles and labels, with
  `is:` and `label:` understood but never required

Because both narrow the same set, facet counts must react to the text and
vice versa. **A facet whose count falls to zero dims; it does not
disappear** — the rail keeps its shape, and the reader can see what their
typing excluded rather than watching options vanish under the cursor.

One line states the current filter and offers to clear it:

```
showing  open · label:bug · "route"        clear ×
```

Sections named by purpose rather than by query are derived from labels and
state: Roadmap, In progress, Needs review, Ideas, Completed, Bugs, Features.
A repository whose labels do not match simply shows fewer sections. The
reader never sees GitHub's search syntax, and never has to.

---

## Testing

`index.html` has no test coverage today; `pytest.ini` and `tests/` cover
`bot.py` only. Five sections of parsing and derivation is more untested
logic than this file should take.

The script cannot be evaluated whole: it is an IIFE (index.html:642), so
nothing inside it is reachable, module scope touches `matchMedia`, and the
last line starts the application.

Instead one region of the script is fenced by banner comments — the file is
already organised that way — and a `node --test` harness slices out that
region and evaluates it alone in a `vm` context. The region is pure by
construction: no DOM, no fetch, no state. Anything reaching for a global
fails loudly in the harness rather than silently in a browser.

This keeps test scaffolding out of the production file entirely: the fence
is two comments, not a flag or an export. The existing gh routing helpers
move into the region so it stands alone. No build step, no second file, no
dependency beyond Node, and the one-HTML-file property is untouched.

CI already extracts the script with `re.search(r"^<script>\n(.*?)\n</script>")`
to run `node --check` on it; the new step runs `node --test tests/site/`
beside it.

Under test:

| Function | Covers |
|---|---|
| `ghFromParts` / `ghToParts` | every section route, round-trips, pre-existing links |
| `filterIssues` | facets, text, `is:`/`label:`, combinations, empty results |
| `deriveSections` | label and state mapping, repositories with no matching labels |
| `splitIssuesAndPulls` | the `pull_request` key |
| `mergeActivity` | chronological merge of commits, issues, releases |
| `deriveContributors` | authorship counting from a commit list |

Rendering and fetching stay untested, as they are today.

---

## Out of scope

- **Community** — a whole request for the thinnest section.
- **Discussions, Projects** — GraphQL only, and GraphQL requires a token
  even for public data.
- **Wiki** — no REST endpoints exist; a wiki is a separate `.wiki.git` with
  no API and nothing on `raw`.
- **GraphQL** — would collapse five calls into one and unlock the two above.
  A later change, on its own merits.
- **Per-entry section tagging** — considered and dropped. Every repository
  gets every section.
- **Any change to `bot.py`** — the entry format is unchanged.

---

## What this exposes

The site talks to no new hosts. `api.telegra.ph`,
`raw.githubusercontent.com`, `api.github.com` and this site's own
`hljs.min.js` are the same four it talks to today. What changes is volume —
four metered calls a repository instead of one — and four things worth
stating plainly.

**Reader addresses reach GitHub more often.** They already did: every
repository view fetched the tree. Four calls give GitHub a somewhat better
view of who reads a publication's repository pages.

**A pasted token identifies the reader to GitHub.** These requests are
anonymous today. A token attaches them to a named account, so pasting one
trades away the anonymity of your own browsing. This is not obvious and the
field should not pretend otherwise.

**A credential lives in the browser.** Session-scoped, never written to
disk, sent to one host. It is the second exception to *store nothing*, after
the extension. What makes it survivable is the property the site already
has: with no third-party requests at all, there is no path by which it
reaches anywhere unintended.

**Third-party text renders on the publisher's site.** This is a change in
kind, not degree, and the most important of the four.

Everything the site renders today was chosen by the publisher — their
articles, their README, their files. **On a public repository, anyone can
open an issue.** An issue body rendered as markdown turns an image URL into
an `<img>`, so a stranger can file an issue containing an image on a server
they control and every reader of that section fetches it, leaking addresses
and user-agents to a host neither the publisher nor Telepatch chose.

The renderer builds real elements rather than assigning HTML, so this is not
script injection; it is a passive beacon. But a README's images are the
publisher's decision and an issue's images are not.

**Therefore: issue and pull-request bodies do not render images.** An image
URL in one becomes a link, which a reader follows deliberately or not at
all. Everything else about the body renders normally.

Release notes keep their images. They are written by people with push access
to the repository — the same hands that write the README, and the same trust
the site already extends to it.

## Risks

**The ceiling is low for browsing.** Twelve repository views an hour is
adequate for a publication with a few repositories and inadequate for a
reader following links between several. The token is the answer and most
readers will not paste one. If this proves to be the binding problem, the
fix is GraphQL, not more caching.

**A token in a browser is a credential in a browser.** Telepatch is
unusually well placed to hold one — no third-party requests at all, so the
ordinary exfiltration path does not exist — but the field must steer people
away from `gh auth token` and toward a read-only fine-grained token, and
must be honest that this is a real exception to a rule the project has
otherwise kept absolutely.

**Derived sections depend on a repository's label conventions.** A
repository with no `bug` label has no Bugs section. This is correct
behaviour but will look like a bug to somebody. The empty state should say
which label it looked for.
