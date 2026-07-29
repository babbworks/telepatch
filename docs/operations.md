# Running this properly

**Living document.** Last pass: 2026-07-28. Phases carry a status; a phase
is not done until its exit criterion is met, and the criterion is the part
worth arguing about.

Companion to [performance.md](performance.md), which holds the numbered
findings this plan works through.

---

## The risk that sets the order

Every write is irreversible. Telegraph has no `deletePage`, and `editPage`
replaces a page wholesale. A bug shipped here does not cause an outage —
it permanently destroys somebody's masthead, footer or index, and there is
nothing to restore from.

So the order is not "host it properly, then tidy the code". It is **make
change safe first**, because everything after that is a change.

---

## Phase 0 — Make change safe · done

The pure functions are the whole risk surface: `split_master`,
`kept_marker`, `claimed_paths`, `build_index`, `compose`, `find_token`,
`token_for`. No I/O, easiest thing here to test, most expensive to get
wrong.

- `tests/` with fixtures taken from real pages — a live index, a curated
  collection, a retired one, and a legacy index written before `byline=`
  existed.
- **The test that matters most:** read → rebuild → write is byte-identical
  when nothing changed. One property, and it guards every command that
  touches an index.

**Exit:** `pytest` green, and red if a marker field is dropped.

## Phase 1 — Resilience · done

Sequenced, because the order is load-bearing:

| | | |
|---|---|---|
| F2 | thread-hop inside `telegraph()` | first, or the rest is theatre |
| F1 | `.concurrent_updates(True)` | pointless before F2 |
| F3 | one `requests.Session` | helps every call |
| F14 | retries with backoff | only affordable after F2 |
| F4, F5 | incremental and parallel scan | the big win |

Plus two things no bot should ship without:

- **A global error handler.** An unhandled exception currently leaves the
  user staring at nothing.
- **A redacting log filter.** Tokens travel in message payloads, so they
  reach exception text eventually. Strip them at the logging layer, not at
  twenty-eight call sites.

**Exit:** two people can act at once; a transient 5xx does not fail a
command; nothing secret can reach a log.

## Phase 2 — Configuration · done

- Environment comes from the host. `.env` stays outside the repo tree and
  is never the deployment mechanism.
- **Fail fast at startup** on missing or malformed config, not on first
  use.

## Phase 3 — Hosting · running under systemd here; VM pending

**A small VPS, systemd, long polling.** About $5 a month.

The decisive fact: polling is **outbound only**. No inbound ports, no TLS
certificate, no domain, no reverse proxy, nothing exposed. Webhooks would
buy latency and scale this has no use for, in exchange for a public
endpoint to secure. Not worth it.

Two units, because the two cases are genuinely different:

- **`telepatch-bot.user.service`** — a machine you already log into. No
  root anywhere; `loginctl enable-linger` is what makes it start at boot
  and survive logout. This is what runs today.
- **`telepatch-bot.service`** — a dedicated machine. Its own user, the
  full sandbox, an `.env` owned by root. See
  [server-setup.md](server-setup.md).

Both are hardened for access already, and both have `MemoryMax`, task
limits and a watchdog.
- **Only one process may poll a token at a time.** No rolling deploys —
  stop, then start. Two bots on one token looks like random message loss,
  which is a miserable thing to debug.
- `WatchdogSec` with `sd_notify`, because a bot that has stopped polling
  looks perfectly healthy to `Restart=always`.

## Phase 4 — Deployment · done

- **A staging bot.** A second BotFather token. The bot is stateless, so a
  staging instance costs a token and nothing else — and given Phase 0's
  risk, it is where you find out a change eats a masthead.
- `deploy.sh`: stop, pull, install, migrate nothing, start, verify.
- CI runs the tests on every push. Dependencies are pinned exactly;
  Dependabot keeps them moving.

## Phase 5 — Observability · done

- **Structured logs**: update id, command, duration, outcome. Enough to
  answer "why was that slow" without a reproduction.
- **A dead-man's-switch.** You cannot health-check a process with no
  inbound port, so the bot pings a URL every few minutes and silence is
  the alert. Inverts the problem correctly.
- **Errors reach a person.** The error handler messages the operator's
  chat, if one is configured.

## Phase 6 — Operations · done

See [runbook.md](runbook.md): restart, logs, token rotation, what to do
when Telegraph is down (nothing — it is not your outage, but say so).

There is nothing to back up. That is the design working. The only secrets
are the bot token and server access, and they belong in a password
manager.

## Phase 7 — The other two surfaces · open

- **Website** — already professionally served. A real CSP needs headers
  GitHub Pages cannot set, so it waits on the custom-domain decision.
- **Extension** — "serviced" means the Chrome Web Store: a privacy policy,
  a listing, and a slower review for broad host permissions. Decide
  whether it is a public product or an internal tool before paying that.

---

## Open, and not blocking

**The bot is operating.** It runs under systemd, restarts itself, has a
watchdog proving it is still polling, and every finding in
[performance.md](performance.md) is closed. Nothing below stops it working
today — each is a thing that would matter later, or on a machine nobody is
sitting at.

Kept here so they are not carried around in somebody's head.

| | What | When it starts mattering |
|---|---|---|
| 1 | **`OPERATOR_CHAT` unset** — unhandled errors go to the journal and nowhere else | The day nobody is reading the journal |
| 2 | **`HEARTBEAT_URL` unset** — no dead man's switch | Same day. A bot with no inbound port cannot be checked from outside; silence has to be the alarm |
| 3 | **No staging bot** — changes are tried against the live one | Before the next change that touches a write path |
| 4 | **The VM** — [server-setup.md](server-setup.md) is written and waiting | When this laptop needs to close its lid |
| 5 | **Custom domain** — deferred deliberately | It gates the website's CSP, which needs headers GitHub Pages cannot set |
| 6 | **Extension not published** — unpacked only | Only if it becomes something other people install |

Items 1 and 2 are ten minutes together and are the two that convert "it is
running" into "I would know if it stopped". They are worth doing on the
same day as item 4, and not really before it: on a machine you are sitting
at, the journal *is* the alarm.

**Item 3 is the one I would rank higher than the rest**, and only because
of the property this whole document opens with: writes here cannot be
undone. A second BotFather token costs nothing, since the bot stores
nothing. That is a judgement, not a blocker — it is recorded and it is
your call.

---

## Deliberately not done

- **Splitting `bot.py`.** It is ~3,400 lines and that will eventually
  limit how fast this can change. But refactoring is exactly the activity
  Phase 0 exists to protect, and the tests are new. Split it after they
  have caught something real.
- **Webhooks.** See Phase 3.
- **Any database.** See performance.md.

---

## Changelog

- **2026-07-28** — plan written; Phases 0–2 and 4–6 built, Phase 3 ready
  to migrate.
- **2026-07-28** — running under systemd as a user unit, watchdog verified
  against a real 180-second window. Every performance finding closed. Six
  items left open above, none of them blocking.
