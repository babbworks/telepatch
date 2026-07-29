# Performance

**Living document.** Last pass: 2026-07-28. Nothing here is done until its
status says so, and a finding that turns out to be wrong should be struck
through rather than deleted — knowing what was measured and dismissed is
worth as much as the list of what to fix.

---

## The shape of the problem

Telepatch stores nothing, so every question is answered by asking Telegraph
again. **Reading is expensive, writing is cheap.** That is the trade the
whole design accepts on purpose; these notes are about paying it well, not
about escaping it.

Three constraints will not change, and every finding below is downstream of
one of them:

- `getPageList` needs the token, so nobody can enumerate an account — and
  there is no search, no filter, and no way to fetch part of a page.
- `editPage` replaces a page wholesale, so every write is preceded by a
  read.
- Telegraph cannot delete, so nothing can be cleaned up, only marked.

---

## How to measure

Repeatable enough that two passes can be compared.

```bash
# Telegraph calls per surface
grep -c 'telegraph(' bot.py
grep -c 'await telegraph(' extension/background.js

# No blocking call may sit in an async handler. Every telegraph() is now
# awaited; _post is the blocking form and belongs only to pooled workers.
grep -n '[^_a-z]telegraph(' bot.py | grep -v await   # should be empty
grep -c '_post(' bot.py                              # workers only

# Are updates handled concurrently?
python -c "from telegram.ext import Application; \
a=Application.builder().token('1:x').concurrent_updates(True).build(); \
print(a.update_processor.max_concurrent_updates)"

# What a rebuild actually cost, from the log
journalctl -u telepatch-bot | grep scan.done | tail -5

# One scan, timed, against a real account
time curl -s "https://api.telegra.ph/getPageList?access_token=$TOK&limit=200" \
  | python -c "import json,sys; print(json.load(sys.stdin)['result']['total_count'])"
```

For the website: DevTools → Network, hard reload, count requests and bytes.
The index should be **two** requests; a repo page **two or three**.

---

## Budgets

What "good" means, so a regression is recognisable.

| | Target |
|---|---|
| Command that only needs an index path | 1–2 Telegraph calls |
| `/site`, steady state | 3–4 calls |
| `/site`, first run or forced refresh | 1 + N, concurrent |
| Website first paint | 2 requests |
| Repo page | 2–3, at most one rate-limited |
| Any single handler blocking the event loop | under ~50 ms |

---

## Cost inventory

Measured by reading the code, 2026-07-28. **N** = pages on the account.

| Command | Telegraph | Telegram | Notes |
|---|---|---|---|
| `/pages` | 1 | 1 | `getPageList`, limit 50 |
| `/views` | 1 | 1 | no token involved |
| `/new` | 1 | 2 | `createAccount`, then a pin |
| `/post` (prompt) | **0** | 1 | the editor link needs only the token |
| `/post` (reply) | 2 | 1 | 4 when writing into a collection |
| `/revise` | 2 | 1 | read-before-write |
| `/newsite` | 2 | 2 | plus a pin |
| `/about` `/footer` `/byline` `/link` `/repo` `/unfile` `/retire` | 2, or **1 + N + 2** | 1–3 | the scan only when nothing carries a path |
| `/collections` | 1 + N | 1 + M | one message each, paced a second apart |
| `/site`, steady state | **3–4** | 3–4 | index, list, whatever is new, write |
| `/site refresh`, first run | 1 + N + 2 | 3–4 | concurrent, 8 at a time |

---

## Findings

Status: `open` · `in progress` · `done` · `rejected`

### F1 — Updates are processed one at a time · **done**

`Application.builder()` is used without `.concurrent_updates()`, and the
default is a `SimpleUpdateProcessor` with `max_concurrent_updates = 1`.
Every update is handled to completion before the next is dispatched.

The README says one instance serves any number of publishers. Today a
single `/site` freezes everyone else's `/post` for its whole duration.

**Fix:** `.concurrent_updates(True)`. Do it *with* F2, not before — raising
concurrency while the calls still block the loop changes nothing.

### F2 — Blocking HTTP inside async handlers · **done**

`telegraph()` is synchronous `requests.post` with a 10-second timeout.
**Four of ~28 call sites** are wrapped in `asyncio.to_thread`; the rest run
inline and stop the event loop.

**Fix:** put the thread hop inside `telegraph()` so no call site has to
remember. Same move as `kept_marker()` — when a rule has 28 places to be
forgotten, move it somewhere it cannot be.

### F3 — No connection reuse · **done**

No `requests.Session` anywhere: every call is a fresh TCP and TLS handshake
to `api.telegra.ph`. On a 13-call scan, that is 13 handshakes.

**Fix:** one module-level `Session`. Two lines, helps every call, and
compounds with F5.

### F4 — `/site` re-derives what it already wrote down · **done**

`build_index` fetches every page to compute title, date, reading time,
categories and excerpt — then writes all five into the master post. The
next rebuild fetches everything again to recompute them. Dates are already
read back (`read_index_dates`); the other four are not.

**Fix:** a page already listed in the index needs no fetch. Fetch only what
the index does not list. `/site refresh` keeps the full pass for when an
article was edited outside the bot.

**Effect:** 1 + N becomes 2–3 on a steady account.

### F5 — The scan is sequential · **done**

`scan_pages` is a `for` loop of `getPage` calls. 13 pages is 13 round trips
in series.

**Fix:** a pool of about 8. Not 200 — an unbounded burst at a free API on
someone's behalf is rude, and the limits are not documented.

### F6 — `/post` spends a round trip on a link most posts never use · **done**

`prompt_post` calls `getAccountInfo` solely to build the five-minute
`auth_url` editor link, blocking, before anything has been typed.

**Fix:** offer it on demand, or in a second message.

### F7 — `/collections` sends one message per collection · **done**

1 + M sends in a burst. Telegram's sustained limit is about one message per
second per chat, so this risks a flood wait as collections accumulate.

The one-message-each shape is deliberate — `callback_data` is 64 bytes and
an action plus a token already uses 62, so a path cannot ride in a button.
But the *burst* is not deliberate.

**Fix:** pace the sends, or cap the list and paginate.

### F8 — Progress notices cost two Telegram calls each · **done**

Several commands send "Reading your pages…" then delete it. Editing the
notice into the result instead would halve that, and would stop the chat
flickering.

### F9 — `ghTree` moved from opt-in to mandatory · **done**

**A regression introduced by "files first".** The repo page now fetches the
tree on every view; before, it only did so when someone clicked *Browse all
files*. That is the only rate-limited call on the site — 60/hour per reader
— and the cache is a per-page-load `Map`, so a reload spends another one.

**Fix:** persist the tree to `sessionStorage`.

### F10 — Website cache does not survive a reload · **done**

`cache` is an in-memory `Map`. Reloading refetches the master post every
time. `sessionStorage` would hold it for the tab's life.

### F11 — Highlighting a large file blocks the main thread · **done, measured**

`MAX_FILE` is 400 kB. highlight.js on a file that size, plus building one
DOM node per token, will visibly freeze a phone. Untested at the limit.

Measured, on this laptop, Python through highlight.js:

| file | tokenise | spans | HTML out |
|---|---|---|---|
| 50 kB | 56 ms | 1,673 | 112 kB |
| 200 kB | 114 ms | 6,699 | 449 kB |
| 400 kB | 203 ms | 13,499 | 901 kB |

So the lexer was never the problem. Building and laying out **13,500 DOM
nodes** is, and the whitelist walker rebuilds every one of them.

**Fixed:** above 150 kB a file is shown as plain text — one text node,
instant, still perfectly readable. Colour is a convenience; response is
not.

### F12 — The extension's `discover()` is `scan_pages` again · **done**

Sequential `getPage` per page on connect. Its own README already admits
this is slow on a large account, and it is the first thing anyone
experiences.

### F13 — Draft autosave writes every 400 ms of typing · **done**

Continuous typing means up to 150 `chrome.storage.local` writes a minute.
Harmless in principle, wasteful in practice.

**Fix:** 1 second, plus a write on blur and on panel close.

### F14 — No retries anywhere · **done**

A transient 5xx from Telegraph fails the command outright. Not a
performance bug, but it sets the latency budget: retries only make sense
once F2 stops them from blocking everyone.

### F15 — `scan_pages` holds every page's content in memory · **mostly done**

Bounded by `INDEX_LIMIT` at 200 pages, but 200 long articles is tens of
megabytes held at once. F4 mostly removes the need.

### F16 — The systemd unit sets no resource limits · **done**

`telepatch-bot.service` is well hardened for *access* but has no
`MemoryMax` or `CPUQuota`. F15 is the reason that matters.

---

## Rejected

Kept so they are not rediscovered and re-argued.

- **Marker line at the top of an index**, so `getPageList`'s auto-generated
  `description` identifies every collection in one request. Verified to
  work — `description` is the opening text of the page. Rejected because it
  puts `Index generated by Telepatch. byline=linked` as the first thing
  anyone sees on the raw telegra.ph page and displaces the masthead, for a
  gain F4 and F5 already deliver.

- **Caching the list of collections** anywhere. It mirrors a fact that
  lives in an authoritative source, and drifts the moment somebody makes a
  collection by hand in the Telegraph editor. Derive, do not mirror.

- **A local database, of any kind.** It would end the property the whole
  product is built on. Not a performance decision.

---

## Changelog

- **2026-07-28** — first pass. F1–F16 recorded, three optimisations
  rejected with reasons.
- **2026-07-28** — F1, F2, F3, F4, F5, F14, F16 fixed; F15 mostly follows
  from F4.
- **2026-07-28** — F6 to F13 fixed. **Every finding in this register is
  now closed.** F11 was measured before it was fixed, and the measurement
  is kept above because it says something the fix does not: the lexer was
  never the cost.

Next pass should start by re-running the measurements at the top rather
than by reading this list. A register with nothing open is a register
that has stopped being looked at.
