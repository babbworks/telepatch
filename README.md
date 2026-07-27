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
third-party requests at all — system fonts only, and `api.telegra.ph` is the
sole network call.

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

### Entries that are not Telegraph pages

An index entry may point at GitHub. A repository link means "the README is
the content"; a file link means that file. It is fetched when a reader opens
it, so the article is whatever the repository says today rather than a copy
taken once — the one thing a Telegraph article cannot be.

```
How this site is built — 2026-07-27 · code, live
https://github.com/babbworks/telepatch
```

`raw.githubusercontent.com` allows cross-origin reads and is not rate
limited, so this needs no server. GitHub's API is touched only to learn a
README's filename when it is not `README.md`.

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

Only the marker line `Index generated by Telepatch.` is structural, and it
exists so `/site` can find the page again rather than creating a second one.

---

## The website

```
https://babbworks.github.io/telepatch/#<master-path>
https://babbworks.github.io/telepatch/#<master-path>/<article-path>
```

The path lives in the **hash**, so it never reaches the server and appears in
no access log. One `index.html` serves every publication.

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

### As a service

`telepatch-bot.service` is a systemd unit with the paths and hardening
already set. Because the bot is stateless, one instance serves any number of
publishers with no per-user storage and nothing to back up.

### The site

GitHub Pages, deployed from `main` at the repository root. A push is the
whole deploy. Set `SITE_URL` in `.env` if you host it elsewhere, so `/site`
hands out the right links.

---

## Licence

MIT. See [LICENSE](LICENSE).
