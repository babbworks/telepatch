# Runbook

What to do when. Written before it was needed, which is the only time it
can be written calmly.

---

## First principle

**There is nothing to restore.** The bot stores nothing, so there is no
backup to lose and no state to recover — but Telegraph also cannot delete
a page, and `editPage` replaces one wholesale. Every incident here is
either "it is not running" (harmless, fix it) or "it wrote something
wrong" (permanent, stop it immediately).

If you suspect the second, **stop the service first and ask questions
after.** A bot that is down has broken nothing; a bot that is looping over
`/site` can strip a masthead off every collection an account owns.

```bash
sudo systemctl stop telepatch-bot
```

---

## Everyday

```bash
systemctl status telepatch-bot          # is it up
journalctl -u telepatch-bot -f          # follow the log
journalctl -u telepatch-bot -p warning  # only what went wrong
sudo systemctl restart telepatch-bot    # restart
```

Deploy:

```bash
./deploy.sh telepatch@example.com          # main
./deploy.sh telepatch@example.com v1.2.0   # a tag
```

The script runs the tests locally first and refuses to deploy over
uncommitted edits on the server.

---

## It is not responding

In order, because each step rules out the one before.

1. **Is the process there?** `systemctl status telepatch-bot`.
   If it is restarting in a loop, `journalctl -u telepatch-bot -n 50` will
   say why. A bad `TELEGRAM_TOKEN` exits immediately with a plain message,
   by design.

2. **Is something else polling the same token?** This is the most common
   cause and the least obvious symptom: two processes on one token means
   each sees roughly half the updates, so the bot appears to ignore
   messages at random. Check the laptop. Check for a stray `screen` or
   `nohup`. **Only one may poll.**

3. **Is Telegram reachable?**
   `curl -s -o /dev/null -w '%{http_code}\n' https://api.telegram.org`

4. **Is Telegraph up?**
   `curl -s 'https://api.telegra.ph/getPage?path=Life-of-Leibniz-07-27' | head -c 80`
   If this fails, it is not your outage. Say so and wait — the bot retries
   reads on its own, and refuses to retry writes that could duplicate.

5. **Has the watchdog been firing?** Repeated restarts with no crash in
   the log means the poller wedged and systemd killed it. That is the
   watchdog doing its job; if it happens often, raise `WatchdogSec` and
   look at network stability.

---

## Rotating the bot token

The bot token is the only credential the service holds. Users' Telegraph
tokens are never stored, so nothing else needs rotating.

1. `/revoke` in @BotFather, then `/token` for the new one.
2. Edit the `.env` on the server (root, mode 0600).
3. `sudo systemctl restart telepatch-bot`.

The old token stops working the moment BotFather issues the new one, so
there is a gap of a few seconds. Nothing queues up: `drop_pending_updates`
means a restart does not replay whatever arrived while it was down.

## A user's Telegraph token is compromised

Not your incident to fix, but the answer people will ask for: `/manage` →
**Revoke**, which calls `revokeAccessToken` and issues a new one. Their
pages survive; the old token stops working.

Telegram keeps chat history, so a token pasted into a chat stays in that
chat. `/privacy` says so.

---

## Something was written wrong

1. **Stop the service.** Above.
2. **Work out what.** `journalctl -u telepatch-bot --since '30 min ago'`.
   Every Telegraph call over 1.5s is logged, and every failure.
3. **Fix by hand if you can.** An index is an ordinary Telegraph page and
   the publisher owns it. Masthead, footer and the marker line can all be
   retyped in the telegra.ph editor —
   [multiple-collections.md](multiple-collections.md) documents the marker
   format exactly for this reason.
4. **A stray index cannot be deleted.** Retire it: add the line
   `Retired Telepatch index.` to the page. Everything then ignores it.

---

## Moving to another server

There is no data to move.

1. Clone the repo, make the venv, install `requirements.txt`.
2. Copy the `.env`.
3. Install the unit, `daemon-reload`, `enable --now`.
4. **Stop the old one first.** Only one process may poll a token.

---

## Staging

A second BotFather token and a second unit, on the same box or a laptop.
The bot is stateless, so a staging instance costs a token and nothing
else. Point `SITE_URL` at the same site — reading it is harmless — and use
a throwaway Telegraph identity for anything that writes.

Given that every write here is irreversible, **this is where a change gets
tried, not production.**

---

## What to check after any deploy

- `systemctl is-active telepatch-bot`
- The startup line in the log: `telepatch.started watchdog=… heartbeat=…`
- `/pages` in the chat — one Telegraph read, proves the token works
- `/site` on a throwaway identity — proves a write works

If the heartbeat is configured, silence for more than
`HEARTBEAT_SECONDS × 2` is the real alarm, and it will reach you without
anyone having to look.
