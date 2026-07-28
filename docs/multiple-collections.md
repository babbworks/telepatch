# More than one collection

**Status: written down, not decided. Nothing here has been built.**
Recorded 2026-07-28 so the reasoning survives until it is wanted.

Today a Telegraph token owns exactly one index. A second collection means a
second identity: `/new`, a new token, a new short name. This note is about
what it would take to let one token own several, and what that would cost.

---

## What already works

`find_site()` — the function behind `/about`, `/footer`, `/byline`, `/link`
and `/repo` — already prefers a path carried in the message and only falls
back to guessing:

```
reply carries site=<path>   →  use it
no carrier                  →  pick_master()
```

So replying to a particular **Site** message already edits a particular
index. The per-collection editing path needs no redesign. This is the
carrier design paying off: because the path travels in the message rather
than in the bot's memory, the code was never allowed to assume a singular
current index, and most of it does not.

The one broken case is the fallback, where nothing carries a path.
`pick_master()` returns the newest page bearing the marker. With several
indexes that is no longer an answer, it is a coin toss — and for `/about`
and `/footer`, which overwrite prose, a wrong guess destroys writing.

---

## What genuinely breaks

Not a plumbing problem. `/site` enumerates **every page on the account**
and lists them all, skipping only pages that carry an index marker.

Put two collections on one token, run `/site` on each, and both list every
article on the account. Two identical collections. Nothing in an article
says which collection it belongs to, so nothing can tell them apart.

Multiple indexes per token therefore forces a decision about what an index
*is*:

| Model | Consequence |
|---|---|
| Keep auto-enumeration | One collection per token forever. Today's design. |
| Tag each article with a collection | Needs a marker inside every post and a filter in `/site`. Pollutes the visible category line unless a reserved prefix is invented. |
| Indexes become curated only | `/site` stops enumerating; entries arrive only through `/link`, `/repo` and an explicit add. Loses "publish and it appears," which is most of why the bot is pleasant. |
| **Primary plus curated extras** | One auto-enumerating index per token, and additional hand-built ones alongside it. |

**Leaning: primary plus curated extras.** It keeps publishing effortless
for the collection that matters most, and treats the others as what they
actually are in practice — curated sets, not dumps of everything. It is
also the only option that changes no existing behaviour for anyone who
never asks for a second collection.

---

## Command impact

**Unaffected.** Account-scoped rather than index-scoped:

`/new` · `/manage` · `/views` · `/privacy` · `/telepatch` · `/howto` · `/revise`

**Need a "which one?" answer when invoked bare.** Replying to a Site
message already works; it is the bare invocation that currently picks the
newest index silently:

`/about` · `/footer` · `/byline` · `/link` · `/repo`

**Change meaningfully:**

- **`/site`** — no longer *the* index. Bare invocation has to list
  collections rather than assume one, and needs a way to distinguish
  "make a new one" from "rebuild an existing one."
- **`/pages`** — should say which collection each page appears in, or it
  stops being useful for deciding what to curate.
- **`/post`** — unchanged if a primary index keeps auto-enumerating. Its
  **Published** message could grow *Add to…* buttons.

**New commands:**

- **`/collections`** — list them with site links; set the default
- **create** — either `/newsite` or `/site new <title>`
- **`/retire`** — now genuinely necessary. Telegraph cannot delete a page,
  so with several indexes there has to be a way to take one out of
  service.

---

## Two hard constraints

### `callback_data` is full

Telegram caps it at 64 bytes. It currently holds `<action>:<token>` — one
character, a colon, and a 60-character token. **62 bytes. Two to spare.**
A collection path cannot travel alongside the token in a button.

The workaround already exists in the codebase: buttons carry action and
token as now, and the *message* they are attached to carries the path in a
hidden `text_link`, which has no length limit. Both are read together. It
is how `/revise` already carries a page path.

This is the third time the same limit has produced the same answer — move
the data into a carrier with no ceiling, and keep the constrained channel
for the minimum that must be there. The deep link, the buttons, and now
collection paths.

### The pinned message becomes plural

The whole interaction model is *reply to the pinned message*. One
identity, one anchor. Several collections means several Site messages to
reply to, and replying to the wrong one silently edits the wrong site.

A `/collections` message with one button per collection is the fix, but it
means the anchor concept itself becomes plural. That is the part users
would actually feel, and it is a bigger change than any single command.

---

## An accident of foresight

`RETIRED_MARK` — "Retired Telepatch index." — is defined in `bot.py`, and
`pick_master()` already refuses to rewrite a page carrying it.

**Nothing has ever written it.** It is an escape hatch: add that line by
hand in the Telegraph editor and the page stops being the master.

`/retire` is the feature it was waiting for. Worth noticing that the
reason it is needed — Telegraph has no `deletePage` — is the same
constraint that made `/site` rewrite in place rather than create, which is
exactly what makes multiple collections awkward in the first place. One
missing verb, three consequences.

---

## The extension

`extension/` supports both shapes already, and they are complementary
rather than alternatives:

| | |
|---|---|
| **Several tokens** | Works today. Paste each; they stack in the dropdown. Hard isolation — one token leaking does not touch the others. |
| **Several indexes per token** | `discover()` already keeps every marked page rather than stopping at the first. |

Whichever way the bot goes, the extension needs no structural change. Two
small things would want doing:

- **Honour the retired marker.** The extension matches a paragraph
  starting with `Index generated by Telepatch.` and does not check for
  `RETIRED_MARK`. A hand-retired page would still appear as a live
  collection. A real divergence between the two front-ends, small and
  only reachable by retiring something manually.
- **Order the dropdown** once there are more than a handful.

---

## Open questions

1. Is a collection a *view* of an account's pages, or a *thing pages
   belong to*? Everything above follows from the answer.
2. If articles get tagged with a collection, where does the tag live so
   that a page written by hand in the Telegraph editor still works?
3. Should `/new` stay the recommended way to separate concerns? Separate
   tokens give real isolation that separate indexes on one token do not.
4. What happens to a collection when its identity is revoked?
