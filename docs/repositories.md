# Reading a repository

How a GitHub repository becomes five pages of a Telepatch publication, and
why each part is the way it is. Everything here lives in `index.html`; the
bot has no part in it.

The reader-facing version of this is in the README. This is for whoever
changes the code next.

---

## The shape of it

An index entry pointing at `github.com/owner/repo` opens a dashboard rather
than a README. Five sections sit behind a rail:

| Section | Route | Built from |
|---|---|---|
| Overview | `github.com/o/r` | repo, issues, releases, commits — plus the README |
| Code | `github.com/o/r/tree/HEAD/…` | the tree, on demand |
| Development | `github.com/o/r/issues` | the issues call, sliced |
| Releases | `github.com/o/r/releases` | the releases call |
| Activity | `github.com/o/r/pulse` | commits + issues + releases, merged |

A single issue is `github.com/o/r/issues/144`, and belongs to Development —
the rail keeps Development lit on it.

**Every route is a real github.com path.** Put `https://` in front of
everything after the master and you land on the same thing at the source.
This is the constraint that decides the design, and it is why there is no
Readme section: GitHub has no `/readme` address to mirror, so the README
sits beneath Overview, which is where GitHub puts it too.

It also rejected the first plan for this feature. A separate Read route
would have been an invented URL, and inventing one breaks the only promise
the addressing makes.

---

## Where the code is

Routing and the derivations are pure and live behind fences. Rendering and
fetching are not.

| Concern | Functions |
|---|---|
| Routing | `ghFromParts`, `ghToParts`, `ghSection`, `isGh`, `isTree`, `isRepoPath` |
| Token shape | `GH_TOKEN`, `looksLikeGhToken`, `ghTokenKind` |
| Issues | `splitIssues`, `deriveSections`, `parseFilterText`, `filterIssues`, `facetCounts` |
| History | `mergeActivity`, `deriveContributors`, `countSince` |
| Addresses | `mdUrl` |
| Fetching | `ghApi`, `ghRepoData`, `ghTree`, `ghFetch`, `ghToken`, `ghAuth`, `RateLimited` |
| Chrome | `RAIL`, `sectionRail`, `healthStrip`, `ago`, `paneError`, `tokenField` |
| Panes | `overview`, `factsRail`, `blockOf`, `development`, `drawFacets`, `releases`, `activity`, `oneIssue` |
| Dispatch | `showArticle` → `showSection` or `showGithub`, `show` |
| Shape guards | `listOf`, `labelsOf`, `okList`, `okMeta` |

### Two dispatch paths, which looks wrong and is not

`showArticle` sends a section to `showSection` and everything else on to
`showGithub`. Overview is *not* a section for this purpose: it is the bare
repository route, and it stays in `showGithub` so it inherits the back link,
the title, the byline, the share button and the category tags that every
other page on the site has. Writing a second set of those for one page
would be the wrong kind of tidy.

The dispatch is not optional. `showGithub` reads a repository with
`resource.slice(3).split("/")`, so handing it `gh:o/r@pulse` yields a
repository called `telepatch@pulse` — which is exactly what happened before
the dispatch existed, and what the browser check caught.

---

## What a repository costs

Arriving spends **four** calls, asked for at once by `ghRepoData`:

```
/repos/{o}/{r}
/repos/{o}/{r}/issues?state=all&per_page=100
/repos/{o}/{r}/releases?per_page=100
/repos/{o}/{r}/commits?per_page=100
```

`git/trees/HEAD?recursive=1` is a fifth, spent only when Code is opened.
The README and every file come from `raw.githubusercontent.com`, which is
not metered.

`api.github.com` allows **60 requests an hour to a browser that has not
identified itself** — about a dozen repository views. Measured on a cold
load: four calls, no more.

Two economies hold that number down, and both are load-bearing:

**Pull requests arrive with the issues.** In GitHub's REST API a pull
request *is* an issue carrying a `pull_request` key. `splitIssues` separates
them, so PR counts, the review sections and Activity's PR entries all cost
nothing extra.

**Contributors are counted, not fetched.** `/contributors` would be a fifth
call for one line of the facts rail. `deriveContributors` tallies the
authors of the commits already in hand, and the rail says *recent hands* so
the number does not claim to be the whole roll.

**Do not add a fifth call without removing one.** If the budget ever has to
grow, the answer is GraphQL — one authenticated query returns everything
these four do — not more caching.

### Reading the README's name

`ghFetch` tries `raw(README.md)` first, which costs nothing. When that
misses it reads the name from the tree rather than from `/repos/{o}/{r}/readme`,
because the tree is wanted the moment Code is opened anyway. Only the root
is considered: a readme inside a folder is that folder's, not the
repository's.

---

## Caching

`ghApi` keys on `api:` + path and goes through the same `cached`/`keep`
pair everything else uses: an in-memory `Map` first, then `sessionStorage`
under the `tp:` prefix.

Two consequences worth knowing before debugging anything here:

- **`sessionStorage.clear()` does not empty the cache.** The `Map` outlives
  it. A true cold measurement needs a full reload.
- **`remember` skips anything over 512 kB.** A busy repository's hundred
  issues can exceed that, so it lives in memory for the life of the page
  but not across a reload — and a reload re-spends all four calls. This is
  the existing cap, not something added here.

The lifetime is deliberate: the tab. Long enough to survive a reload, short
enough that nobody reads a stale repository tomorrow.

---

## When a call fails

Each of the four is caught on its own inside `ghRepoData` and comes back as
`{error}` rather than throwing. That is why every reader of the payloads
goes through `okList` or `okMeta` — they turn a failed call into an empty
list or an empty object, so one dead call empties one pane and leaves the
rest of the dashboard standing.

`RateLimited` is its own type so a pane can tell *the budget is gone* from
*GitHub had nothing*. Only the first has a remedy, and `paneError` offers
`tokenField` for it and not for the other.

**A rate-limited reader still gets the README**, because that never touches
the API. This is the reason Read was folded into Overview rather than
dropped: the one section that always works should be on the page you land
on.

---

## The token

Held in `sessionStorage` under `tp:ghtoken`, attached by `ghAuth` as
`Authorization: Bearer` to every `api.github.com` request including the
tree, and sent nowhere else. It raises the ceiling from 60 to 5,000 an hour
and **changes nothing about what is asked for** — the same four calls
either way.

Recognised by shape, the way the bot recognises a pasted Telegraph token:

```
gho_ ghp_ ghu_ ghs_ ghr_   →  "broad"
github_pat_                →  "fine"
```

`ghTokenKind` exists for one reason. `gh auth token` hands out exactly the
broad kind, and its default scopes include write access to private
repositories. Nothing here wants that, and the paste is the last moment
anybody can be told, so `tokenField` says so in the box.

This is the second place Telepatch holds a credential, after the extension.
What makes it survivable is a property the site already had: with no
third-party requests, there is no path by which it reaches anywhere
unintended.

### What a token costs the reader

Anonymous requests are anonymous. A token attaches them to a named GitHub
account, so pasting one trades away the anonymity of your own repository
browsing. Anyone changing this text should keep saying so.

---

## What a stranger may put on the page

Everything else the site renders was chosen by its publisher: their
articles, their README, their files. **On a public repository anybody can
open an issue**, which makes an issue body the one thing here nobody here
chose.

An image in markdown becomes an `<img>`, and an `<img>` is a request every
reader's browser makes on load. So a stranger could file an issue
containing an image on a server they control and collect the addresses of
everyone who read that section.

**Issue and pull-request bodies therefore render images as links.** The
address still reaches the reader, as something they may follow rather than
something fetched for them. Release notes keep their images: those are
written by hands that already have push access, which is the trust the
README already gets.

The mechanism is a fourth argument to `renderMarkdown`:

```js
renderMarkdown(found.body, prose, "", { images: false });
```

which sets the module-level `mdImages` for the duration of the call and
restores it in a `finally`. It is module state rather than an argument
threaded through six call sites because rendering is synchronous from the
first node to the last, so two of these can never interleave. If rendering
ever becomes asynchronous, this becomes wrong and must be threaded properly.

### mdUrl is the boundary

Every address that reaches an `href` or a `src` passes `mdUrl` first, and
anything outside `http:`, `https:` and `mailto:` leaves as `""` — which
every caller treats as *render the text, make no link*. `javascript:` and
`data:` die there.

The bypass that defeats a scheme check on its own is worth knowing about:
the URL parser strips tabs and newlines, so `jav<tab>ascript:` parses as
`javascript:`. It cannot arrive, because the markdown pattern captures an
address with `[^)\s]+` and the whitespace ends the capture first. **Both
halves are pinned by `tests/site/urls.test.mjs`**, including the pattern,
because that is where the second protection actually lives.

An automated review once read the issue-body link as an injection. It was
not, but it was right that the function had no test.

---

## Layout

`--col` is the site's only width control. A repository route sets
`body.wide`, which changes that one value from `52rem` to `68rem`:

```css
body.wide{--col:68rem}
```

This preserves the invariant in the comment above `.col`: every element
carrying `.col` still resolves to an identical inline box, so the bar's
title and the content still share one left edge. Measured on a repository
page: both at 156px. **Nothing here may set `padding-inline` or
`margin-inline` on a `.col` element** — that note is not decoration, it
describes a rule that has already been broken once.

`show()` sets the class from the route, so leaving a repository puts the
measure back. A tree counts as a repository page; it is the Code section.

The frame therefore changes width between an article and a repository. That
is deliberate, and happens only on a full route change — not the
involuntary mid-page shift that `scrollbar-gutter:stable` exists to prevent.

### The lamp

The palette comment reserves `--lamp` for live and active states. On a
dashboard that stops being a stylistic note and starts doing work: it marks
the active section in the rail, the open count in the health strip, an
open issue's state, and nothing else. A dense page with a free hand on the
lamp becomes a scoreboard.

### Narrow widths

- the rail scrolls sideways under a gradient mask below `40rem`
- the two-track grid collapses below `48rem`
- the facet rail becomes a chip row above the list — **the same markup
  restyled**, not a second component, because a filter nobody can see is a
  filter nobody uses

---

## Filtering

Everything in Development is a slice of the one issues payload. Nothing a
reader does there costs a request.

Two mechanisms narrow the same set: the facet rail (state, label,
milestone, combinable) and the filter field. `filterIssues` merges both,
with `parseFilterText` understanding `is:`, `label:` and `milestone:` so
that anybody who knows them is not slowed down, and nobody is required to
type one.

Because both narrow one set, `facetCounts` recomputes every facet as *what
would remain if this were applied too*. **A facet that falls to zero dims
rather than disappearing.** The rail keeps its shape, and the reader can
see what their typing excluded instead of watching options vanish under the
cursor. This is the one interaction detail most worth not regressing.

Purpose sections come from `SECTION_RULES` — Roadmap, Bugs, Features,
Ideas, Documentation, Open, Completed — matched on a label and a state. A
repository whose labels do not match shows fewer of them. Open and
Completed always work, because state exists everywhere.

---

## Tests

`index.html` had no test coverage before this feature, and this feature
added a great deal of logic to it.

Pure code sits inside **named fences**:

```js
/* ---------- pure: github ---------- */
…
/* ---------- end pure ---------- */
```

`tests/site/extract.mjs` finds every such region, concatenates them,
evaluates the result as a function body, and hands back every top-level
binding. `node --test tests/site/` runs in CI beside `node --check`.

Three things about this are deliberate:

- **Fences, not exports or a debug flag.** Nothing about testing ships to
  a reader.
- **Regions are named**, so a fence sits beside the code it fences instead
  of everything pure being herded into one place.
- **A function body, not a `vm` context.** A `vm` has its own `Array` and
  `Object`, so every value the region returned failed a strict deep-equal
  against one built in the test — same shape, different prototype.
  Isolation is not lost: the region names no global, and one that did
  would throw in the harness exactly as it would in a browser.

**Anything placed inside a fence must stay pure.** Reach for `document`,
`fetch` or module state and CI fails. That is the point.

Rendering and fetching stay untested, as they were before. They were
checked by hand against live repositories — `babbworks/telepatch`,
`astral-sh/ruff`, `rust-lang/mdBook` — including a forced 403 to see the
rate-limited pane, and a seeded issue body to confirm an image beacon
produces no request.

---

## Known limits

- **A single issue is read from the hundred most recent.** An older one says
  so rather than costing a fifth call. Fixing it properly means a request
  the budget does not have.
- **No Discussions or Projects.** GraphQL only, and GraphQL needs a token
  even for public data.
- **No Wiki.** No REST endpoints exist at all; a wiki is a separate
  `.wiki.git` with nothing on `raw`.
- **No Community section.** A whole request for the thinnest pane.
- **A nested image inside a link** — `[![badge](img)](href)` — renders with
  `![` leaking into the link text. A pre-existing quirk of the inline
  pattern, unchanged by this work, and harmless: no `<img>` results.

---

## Adding a sixth section

1. Add its name to `GH_SECTIONS` — it must be a path github.com really has.
2. Add a row to `RAIL`.
3. Write `yourSection(pane, repo, data)`, reading payloads through `okList`
   or `okMeta` and returning early with `paneError` when its call failed.
4. Dispatch it in `showSection`.
5. If it needs data the four calls do not carry, **remove a call or use a
   token-only path.** Do not quietly make it five.
6. If it renders text somebody outside the project wrote, pass
   `{ images: false }`.
7. Add routing tests to `tests/site/routing.test.mjs` — a round-trip and a
   `ghSection` case at minimum.
