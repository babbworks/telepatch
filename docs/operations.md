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

## Phase 3 — Hosting · ready, not yet migrated

**A small VPS, systemd, long polling.** About $5 a month.

The decisive fact: polling is **outbound only**. No inbound ports, no TLS
certificate, no domain, no reverse proxy, nothing exposed. Webhooks would
buy latency and scale this has no use for, in exchange for a public
endpoint to secure. Not worth it.

- `telepatch-bot.service` is hardened for access already; it now also has
  `MemoryMax`, `CPUQuota` and a watchdog.
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
