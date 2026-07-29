# Telepatch

Publishing with [Telegraph](https://telegra.ph), from Telegram.

Write a post in a Telegram chat. It appears on telegra.ph. A single static
page turns your Telegraph articles into a small website.

**Live:** <https://babbworks.github.io/telepatch/>

---

## The one design rule

**Telepatch stores nothing.**

No database, no file written, nothing kept in memory between messages. A
Telegraph `access_token` is the whole identity, and the bot never keeps a
copy — it round-trips through Telegram's own message payloads:

| Carrier | Holds | Limit |
|---|---|---|
| Deep link `t.me/<bot>?start=<token>` | the token | 64 bytes — a token is 60 |
| `callback_data` on a button | `<action>:<token>` | 64 bytes — this uses 62 |
| A hidden `text_link` in a ForceReply prompt | token, page path, per-post byline | none |

Every action therefore starts from a message already in your chat. That is
not a limitation worked around; it is the reason there is nothing to leak.

The website inherits the same property. It is one HTML file that fetches one
public Telegraph page. No account, no cookies, no analytics, and no
third-party requests at all — system fonts only. A publication of Telegraph
articles calls `api.telegra.ph` and nothing else; a repository entry also
calls `api.github.com` and `raw.githubusercontent.com`, which is what
reading a repository live means. Opening a code file additionally loads
`hljs.min.js`, which is served from this site, not a CDN.

### What it does not protect you from

Telegram sees every message in the chat, including your token, and keeps your
history. Telegraph sees whatever you publish. Images in posts are hotlinked,
so whoever hosts them sees your readers' IP addresses. Telepatch cannot change
any of that, and says so in `/privacy`.

---

## Commands

Once you have an identity its message is pinned in the chat. Reply to that
pinned message with any command and the token is picked up automatically —
you should never need to paste it.

| Command | Does |
|---|---|
| `/new` | Create an identity. `short name, author name, author url` |
| `/post` | Publish. First line title, second line categories, then the body |
| `/pages` | List what this identity has published |
| `/repo` | Add a GitHub repository — its files, and its README |
| `/revise` | Rewrite a post — reply to its **Published** message |
| `/site` | Build or refresh the public index |
| `/about` | Set the introduction shown above your index |
| `/footer` | Set the footer shown at the bottom of every page |
| `/byline` | How bylines show: `linked`, `separate` or `plain` |
| `/manage` | Byline, author URL, revoke |
| `/views <url>` | Title, byline and views for any Telegraph page — **no token needed** |
| `/privacy` | What the bot keeps, and what it cannot protect |
| `/telepatch` | About Telepatch |

### Writing a post

```
On the price of tin
tin, industry, longform

> What the ledgers say, against the usual account.

The price held steady for most of the decade, then moved sharply.

## What moved it

https://example.com/photo.jpg a sample, photographed against white

Three things drove it, none of them obvious at the time.

### The Cornish mines

Detail that belongs under the section above.
```

- **Line one** is the title.
- **Line two** is read as categories when it looks like a list — one word, or
  comma-separated short items, and no sentence punctuation. Otherwise it is
  body text. It is stored as an `<aside>`, which Telegraph renders as a
  centred subtitle and the website reads back as tags.
- **A `>` line immediately after the categories** is the article's intro,
  shown under the title as a standfirst. It is stored as a `<blockquote>`,
  so setting one with the quote button in the Telegraph editor does the same
  thing.
- An **image URL alone on a line** becomes a picture; words after it become
  the caption. YouTube, Vimeo and Twitter links become embeds.
- **`#` or `##` starts a heading**, `###` a subheading. Telegraph allows
  only `h3` and `h4`, and the page title already occupies the level above.
  Two or more headings give the article a contents list on the website.
- Bold, italics and links you type in Telegram survive into the article.

Telegraph's upload endpoint is closed to third parties, so images must be
hotlinked. `/manage` → **Upload image** gives a five-minute signed-in link to
the Telegraph editor, where uploads do work; copy the resulting
`telegra.ph/file/…` address into your post.

### The master post

`/site` enumerates your pages, reads each one's categories, and writes a
single **master post** — an ordinary Telegraph page listing your articles as

```
Title — 2026-07-27 · 6 min · tin, industry
The price held steady for most of the decade, then moved sharply…
```

The date, the reading time and the opening excerpt are all recorded there, so
the website needs one request rather than one per article.

That page is the entire website. `getPageList` requires a token, so a visitor
can never enumerate an account; publishing an index has to be a deliberate
act.

The master post is also the only durable record Telepatch has. Telegraph
exposes no publication date, so `/site` writes one and reads it back before
each rebuild. Prose typed above the list — your site's introduction, set with
`/about` — and prose typed below it, your footer, set with `/footer` — are
preserved the same way. Nothing is remembered by the bot; the
page itself is the memory, and the publisher owns it.

Running `/site` again rewrites that page rather than creating another.
Telegraph has no `deletePage`, so a stray index would be permanent.

A page tagged `nav` becomes a top-bar link instead of an index entry.

### Pointing at other sites

An entry tagged **`site`** or **`web`** leaves the index and joins the
menu behind the globe at the right of the top bar — `site` for another
Telepatch publication, `web` for anywhere else worth reaching. Add one
with `/link`:

```
https://babbworks.github.io/telepatch/#Another-Site-07-29
The other publication
site
```

The globe is always in the bar. It is dim and inert, with the divider
beside it barely visible, until a publication actually points somewhere —
so the bar says whether the menu is worth opening before it is opened.

The site recognises its own address, so a link to another Telepatch
publication changes the route rather than leaving the page; everything
else opens outward in a new tab.

These links are **authored, never discovered.** A reader cannot enumerate
somebody's collections — `getPageList` needs the token — so the only way
one site can point at another is for its publisher to say so. That is the
same property that makes publishing an index a deliberate act.

### Entries that are not Telegraph pages

An index entry may point at GitHub. A repository link opens that
repository; a file link means that file. It is fetched when a reader opens
it, so the article is whatever the repository says today rather than a copy
taken once — the one thing a Telegraph article cannot be.

```
How this site is built — 2026-07-27 · code, live
https://github.com/babbworks/telepatch
```

`/repo` adds a whole repository. Give it `owner/repo` and nothing else and
the title and description come from GitHub; add more lines to write them
yourself.

A repository opens as a dashboard. Five sections sit behind a rail, and
each is addressed the way GitHub addresses it — put `https://` in front of
the second half and you have the same page at the source:

```
…/#<master-path>/github.com/babbworks/telepatch
…/#<master-path>/github.com/babbworks/telepatch/tree/HEAD/docs
…/#<master-path>/github.com/babbworks/telepatch/issues
…/#<master-path>/github.com/babbworks/telepatch/issues/144
…/#<master-path>/github.com/babbworks/telepatch/releases
…/#<master-path>/github.com/babbworks/telepatch/pulse
```

**Overview** carries what GitHub knows — when it was last touched, its
licence, stars, what is open, what was released, how many commits in
thirty days — with the README beneath it. **Code** is the file tree.
**Development** is every issue and pull request. **Releases** carries the
notes and the assets. **Activity** merges commits, issues, pull requests
and releases into one chronological stream, because "what has been
happening" is one question that GitHub answers in four places.

There is deliberately no Readme section: GitHub has no `/readme` address to
mirror, so the README sits under Overview, where GitHub puts it too.

In Development the facets and the filter field narrow the same set, and
neither costs a request — they are slices of one payload already fetched.
A facet whose count falls to zero dims rather than disappearing, so the
rail holds its shape and you can see what you excluded. `is:` and `label:`
are understood if you type them and never required.

Folders open in place and files open as their own pages, so the repository
is readable without leaving the site. One request to GitHub's tree API
returns the whole structure — even CPython's 6,435 entries come back
untruncated — and it is cached, so every folder after the first costs
nothing at all. File contents come from `raw.githubusercontent.com`, which
allows cross-origin reads and is not rate limited.

### What a repository costs, and the token

Arriving at a repository spends **four** calls on `api.github.com`: the
repository, its issues, its releases and its commits. The file tree is a
fifth, spent only when Code is opened. Everything else — the README, every
file — comes from `raw.githubusercontent.com`, which is not metered.

That API allows **60 requests an hour to a browser that has not identified
itself**, which is about a dozen repository views. Past that, each section
says so and offers a box to paste a GitHub token, which raises the limit to
5,000. The token is kept for the life of the tab, sent to `api.github.com`
and nowhere else, and never written anywhere durable.

It is still a credential in a browser — the second exception this project
makes, after the extension. Use a **fine-grained token, public
repositories, read-only**. Not what `gh auth token` hands you: that one can
write to your private repositories, and the box says so when it recognises
the shape.

A reader who has run out still gets the README, because that never touches
the API at all.

### What a stranger may put on your page

On a public repository anybody can open an issue, which makes an issue body
the one thing here the publisher did not choose. Rendering its images would
let a stranger point every reader's browser at a host nobody here picked,
so **images in issue and pull-request bodies become links** — the address
still reaches the reader, as something they may follow rather than
something their browser fetches for them.

Release notes keep their images. Those are written by hands that already
have push access, which is the trust the README already gets.

Markdown files render as prose. Anything else is shown as code, highlighted
by [highlight.js](https://highlightjs.org) 11.11.1 (BSD-3-Clause), vendored
here as `hljs.min.js` — 128 kB, 43 kB over the wire — rather than loaded from
a CDN, so the no-third-party-requests promise survives. It is fetched the
first time somebody opens a code file and never on the index. It wears this
site's palette instead of its own theme, and its output is copied across a
span-and-text whitelist rather than assigned as HTML. If the script does not
arrive, a small lexer written for this project takes over: comments,
strings, numbers and keywords. Images are displayed; other binaries and
anything over 400 kB are linked to rather than pulled in.

`/site` reads these back before rewriting the list, so a hand-added entry
survives a rebuild and keeps its place by date.

### Writing either page by hand

Nothing here is a private format. Everything the website reads is ordinary
Telegraph markup, so a page written in the telegra.ph editor works exactly
as one published through the bot:

| Element | What the site reads |
|---|---|
| Article categories | the first `<aside>` — a comma-separated line |
| Article intro | a `<blockquote>` immediately after it |
| Article sections | `<h3>` and `<h4>`, which build the contents list |
| Index entries | links inside the `<ul>`, as `Title — date · N min · categories` |
| A GitHub entry | a github.com link in that list — the README, read live |
| Index introduction | any prose above that list |
| Index footer | any prose below it |
| Byline mode | `byline=` on the marker line |

Only the marker line is structural. **Typing it is how a hand-written page
becomes an index** — there is no registration step and nothing to tell the
bot. `/site` reads the account, and any page carrying the line is one:

```
Index generated by Telepatch. byline=separate
Index generated by Telepatch. byline=linked collection=extra
Retired Telepatch index.
```

The first is a primary index, the second a curated collection, the third
is out of service. `byline=` may be `linked`, `separate` or `plain`.

Everything else on an entry line is punctuation, not syntax. A dot, a
bullet, a comma or a plain space all read the same:

```
Title — 2026-07-29 · 6 min · tin, industry
Title — 2026-07-29, 6 min, tin, industry
```

The date is the only part the bot needs, because it is the only part that
exists nowhere else.

---

## The website

```
https://babbworks.github.io/telepatch/#<master-path>
https://babbworks.github.io/telepatch/#<master-path>/<article-path>
https://babbworks.github.io/telepatch/#<master-path>/<article-path>/<section>
```

The path lives in the **hash**, so it never reaches the server and appears in
no access log. One `index.html` serves every publication.

A GitHub resource is addressed the way GitHub addresses it — put `https://`
in front of the second half and you have the page at the source:

```
…/#<master-path>/github.com/babbworks/telepatch
…/#<master-path>/github.com/babbworks/telepatch/tree/HEAD/docs
…/#<master-path>/github.com/babbworks/telepatch/blob/HEAD/bot.py
…/#<master-path>/github.com/babbworks/telepatch/issues
…/#<master-path>/github.com/babbworks/telepatch/releases
…/#<master-path>/github.com/babbworks/telepatch/pulse
```

A section carries no git ref, unlike `blob` and `tree`, so nothing is
skipped in `issues/144`: the number is the section's argument rather than a
path under a ref. Any other GitHub path — `/settings`, `/actions`,
`/wiki` — resolves to the repository rather than a dead page.

Separators are real `/` characters rather than escapes. An earlier version
packed the resource into one segment with the slashes percent-encoded, which
broke the moment anything in the chain decoded `%2F` — a terminal, a chat
client, a URL normaliser — because the route then split in the wrong places.

Articles are rebuilt from Telegraph's content nodes as real elements rather
than iframed, so they take the site's typography and dark mode, and links
between your own articles stay inside the site.

---

## Running it

```bash
git clone https://github.com/babbworks/telepatch
cd telepatch
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # add your BotFather token
.venv/bin/python bot.py
```

There is no server to expose. `run_polling()` makes outbound requests to
`api.telegram.org`, so it works behind NAT with no port forwarding. Only one
process may poll a given token at a time.

Tests:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

### As a service

`telepatch-bot.service` is a systemd unit with the paths, hardening,
resource ceilings and watchdog already set; `./deploy.sh user@host` stops,
updates and restarts it. Because the bot is stateless, one instance serves
any number of publishers with no per-user storage and nothing to back up.

Long polling dials out and listens on nothing, so there is no port to
expose, no certificate to renew and no domain required. **Only one process
may poll a token at a time** — a deploy stops before it starts, and two
bots on one token looks like random message loss.

### The site

GitHub Pages, deployed from `main` at the repository root. A push is the
whole deploy. Set `SITE_URL` in `.env` if you host it elsewhere, so `/site`
hands out the right links.

---

## Notes

- [Running this properly](docs/operations.md) — the staged plan, and what
  is done.
- [Setting up a server](docs/server-setup.md) — a VM or a VPS, start to
  finish, in about twenty minutes.
- [Runbook](docs/runbook.md) — restart, logs, token rotation, and what to
  do when something was written wrong.
- [Performance](docs/performance.md) — where the requests go, what they
  cost, and a register of what to tighten next.
- [More than one collection](docs/multiple-collections.md) — one token,
  several collections, and the way back out of it.

---

## In the browser

`extension/` is a Chromium extension that saves the page you are on into a
collection: a floating button, a panel, and one `editPage` call. It writes
the same entry format the bot writes, to the same master post, so a page
saved while browsing lands on the site next to everything else.

It is the one place Telepatch stores a token, because an extension has
nobody to hand it to between clicks. [extension/README.md](extension/README.md)
says what that changes.

---

## Licence

MIT. See [LICENSE](LICENSE).
