# Telepatch, in the browser

Save the page you are on into a Telepatch collection. It appears on your
site immediately, because the collection *is* the site — the extension
writes to the same master post `/site` writes.

```
click the T  →  pick a collection  →  Save
```

## Install

Chrome or any Chromium browser, unpacked:

1. `chrome://extensions` → turn on **Developer mode**
2. **Load unpacked** → choose this `extension/` folder
3. Open any page, click the **T** in the bottom-right corner
4. Paste the access token from your identity message in Telegram

Pasting the token is the only setup. The extension calls `getPageList`,
reads each page, and recognises a collection by the marker line `/site`
leaves at the foot of an index — so it finds your collections rather than
asking you to name them. An account with several indexes connects all of
them at once.

## What it is doing

| | |
|---|---|
| Reads | `getAccountInfo`, `getPageList`, `getPage` |
| Writes | `editPage` — one entry spliced to the top of the list |
| Stores | `{label, token, path}` per collection, in `chrome.storage.local` |
| Sends anywhere else | nothing |

An entry is written in the same shape the bot writes, so `/site` keeps it
on the next rebuild and the website reads it as an ordinary item:

```
A saved page — 2026-07-28 · reading, research
The note you typed in the panel.
```

The masthead, the footer, the byline mode and anything else recorded on
the index are read first and written back untouched. `editPage` replaces a
page wholesale; anything not handed back is destroyed.

## Two things it does differently from the bot

**It stores your token.** The bot never does — the token round-trips
through Telegram's own message payloads, which is why there is nothing to
leak. An extension has nobody to hand it to between clicks, so it keeps it
in `chrome.storage.local`. That is a real change in posture and worth
knowing: the token is on that machine, in that browser profile, until you
disconnect the collection. It is never in the page, never in the DOM, and
never in a variable a website could reach.

**It runs on every page you visit.** That is what a persistent layer is.
Chrome will say so plainly when you install it.

## How it is put together

```
manifest.json    permissions: storage, and api.telegra.ph
background.js    every network call and the only code that sees a token
content.js       the floating button and panel, in a closed shadow root
```

Two decisions carry the design:

**All fetching happens in the service worker.** A content script runs in
the host page's origin, so its requests answer to that page's
Content-Security-Policy — and plenty of sites set a `connect-src` that
would block `api.telegra.ph`. Saving would then fail on exactly the sites
worth saving from, for a reason no reader could diagnose. The worker has
the extension's own origin and its declared host permissions, so it always
reaches Telegraph.

**The panel lives in a closed shadow root** with every rule starting from
`all: initial`. A layer that sits on top of the whole web has to survive
any stylesheet underneath it and disturb none of them.

## Known edges

- **Last write wins.** Telegraph has no version or ETag on `editPage`. Two
  devices saving to one collection at the same moment: the second
  overwrites the first. Rare in practice for one person, and unfixable
  without a server.
- **Connecting is slow on a large account.** Recognising collections means
  reading each page, done sequentially rather than in a burst.
- **The toolbar button is best-effort.** The floating button always works;
  clicking the toolbar icon messages the tab, which some builds decline
  without broad host permissions.
- Chromium only so far. Firefox needs a manifest with
  `background.scripts` rather than a service worker.
