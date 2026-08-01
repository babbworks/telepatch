# Telepatch Observer — design

**Status:** agreed 2026-08-01. Written before the target machine was
reachable, so every hardware assumption is marked and every probe is
written to fail soft. See [../../observer.md](../../observer.md) for the
install runbook and the list of things to verify on the box.

---

## What this is

A second service, `telepatch-observer`, that publishes the health of the
machine running Telepatch to a single public Telegraph page, and keeps a
local copy of everything it publishes.

It is deliberately *not* part of `bot.py`.

## Why a separate service

A status page hosted inside the process it monitors cannot report that
process being down — which is the most important thing a status page ever
says. If the observer were a ticker inside `bot.py`, a crashed bot would
leave a silently stale page, and staleness is ambiguous: it reads the same
as a network fault or a Telegraph outage.

A separate unit asks systemd about `telepatch-bot.service` and can say
*"inactive (failed), 4 minutes"* — and keep saying it.

There is a second, harder reason. `bot.py:101` reads `TELEGRAM_TOKEN` at
**module scope** with `required=True`. Importing `bot` from the observer
would make the observer refuse to start without a Telegram token it has no
use for. The observer is therefore standalone, including its own small
Telegraph client. That duplication is the price of two independently
startable services, and it is worth paying.

## Two clocks

| Clock | Period | Does |
|---|---|---|
| sample | 120 s | read sensors → ring buffer (15 slots) → raw line to local log |
| publish | 1800 s | aggregate buffer → render → `editPage` → mirror to local log |

Sampling at 2 minutes and publishing at 30 gives a 30-minute **mean** of
load, temperature and fan speed rather than an instantaneous reading that
happened to land on the tick. It is both better data and fewer API calls.

Two aggregation rules, by metric type:

- **gauges** (load, temp, fan, memory, CPU%) → mean, min, max over the block
- **counters** (commands, publishes, API calls) → sum over the period

An average of a counter is meaningless, so the distinction is structural,
not stylistic.

## Rate discipline

Telegraph publishes no rate limits and none could be found documented, so
the numbers below are reasoned rather than sourced.

48 `editPage` calls a day. For scale: `bot.py` sets `SCAN_WORKERS = 8` over
`INDEX_LIMIT = 200`, so a **single** `/site` rebuild can fire ~200 calls in
a burst. A full day of observer traffic is a quarter of one index rebuild,
spread evenly. The observer is not the noisy neighbour here.

Shape matters more than volume: the abuse pattern is unbounded
`createPage`. This service only ever calls `editPage`, on a path supplied
by configuration, so it is structurally incapable of minting a second page
however many times it restarts. `bot.py:414` already encodes the same
reasoning — `createPage` is never retried, `editPage` is freely repeatable
because writing the same content twice equals writing it once.

The observer account (`telepatch-ops`, `page_count: 1`) is separate from any
user's publishing account. If it is ever throttled, no user is affected.

## Privacy

`/privacy` currently promises users that Telepatch keeps nothing, writes no
file, and holds nothing in memory between messages. Publishing activity
statistics makes parts of that untrue, so the guarantee is rebuilt as
something narrower that stays true — and, importantly, stays *checkable*,
which is how `bot.py:1344` describes the existing claims.

**1. Lossy at capture, not filtered later.** `counter += 1` destroys
everything about the event that caused it. Anonymisation applied after
collection is a filter, and filters fail silently one refactor later.

**2. Closed vocabulary.** `tally()` takes one argument, which must be a
name from a fixed frozenset. No token, chat id, user id, title, path or
category can cross that boundary. `tests/test_observer_tally.py` walks the
AST of `bot.py`, finds every `tally()` call site, and fails if any argument
is not a string literal in the allowed set. A future edit that interpolates
a variable fails the suite, not code review.

**3. One dimension, low cardinality.** The leak is never a big number; it
is a small one. `pages published: 1,204` says nothing. `pages published ·
category "birdwatching" · 03:00–04:00: 1` is one person's record. Counters
carry a single dimension drawn from a closed set of ~20 values. Free text
never becomes a key.

**4. Publishing cadence is part of the threat model.** A counter refreshed
every 30 minutes leaks 30-minute-resolution activity to anyone who polls
the page and diffs it. On a quiet bot most windows contain zero or one
event, and a delta of 1 correlates trivially against the page that just
appeared on that person's Telegraph account.

So the two blocks on the page run on different boundaries. **Hardware
re-renders every 30 minutes** — it contains nothing user-derived and can be
as live as we like. **Activity shows the last completed hour** and does not
move between rollovers, so all edits within an hour carry byte-identical
activity figures. Counts below 5 render as `<5`.

**5. Nothing survives a restart.** Counters live in `/run/telepatch`, a
tmpfs created by `RuntimeDirectory=telepatch` and **deleted by systemd when
the unit stops**. "Nothing persists" becomes a property of the deployment
rather than a promise in prose.

**6. Not counted, deliberately.** Distinct users, returning users, per-author
anything, titles, paths, categories, per-post word counts, per-event
timestamps. A HyperLogLog sketch could give distinct-user counts without
retaining reversible identity, but it requires touching the identifier, and
that is not worth spending the strongest claim on.

Note that hashing a Telegram user id is **not** anonymisation — the id space
is ~10¹⁰ and enumerable, making a hash a brute-forceable lookup rather than
a one-way door.

**7. The local log is the more sensitive artifact.** It holds 2-minute
samples; the page holds 30-minute means. It stays on the machine.

`/privacy` will need rewording from "no file is ever written" to a claim
about nothing surviving a restart and nothing being attributable. That
wording is not part of this spec.

## Modules

Each is independently testable, and most are pure functions over fixture
text — which is how the hardware parsing gets tested without the hardware.

| File | Does | Depends on |
|---|---|---|
| `observer/probe.py` | parse `/proc`, `/sys` → readings | filesystem |
| `observer/service.py` | `systemctl show` → bot state, restarts | subprocess |
| `observer/counters.py` | read `/run/telepatch/counters.json` | filesystem |
| `observer/aggregate.py` | samples → block | pure |
| `observer/render.py` | block → Telegraph nodes | pure |
| `observer/publish.py` | Telegraph `editPage` client | requests |
| `observer/logfile.py` | local log append and trim | filesystem |
| `observer/__main__.py` | wiring, tickers, sd_notify | all |

## Failing soft

The target is a PowerBook G4 on Debian ports, unreachable at design time.
Which sensors it exposes is genuinely unknown: PowerPC thermal data may
come from `therm_adt746x` under `/sys/devices/temperatures/`, from
`windfarm` under `/sys/devices/platform/`, or from `hwmon` — it varies by
model and kernel.

So every probe tries a **list of candidate paths**, returns `None` rather
than raising when none match, and records which path succeeded. A missing
fan sensor means the fan line is absent from the page, not a dead service.

The page prints a `sensors` line naming what resolved and what did not, so
the first look at the published page is also the diagnostic.

## Running as root

Root is not required — `/proc` and `/sys` reads, `systemctl show` and
`LogsDirectory` all work unprivileged. It is chosen because it sidesteps
group permissions on the bot's `/run/telepatch` counters and on the journal,
on a machine that is awkward to reach.

The unit compensates: `CapabilityBoundingSet=` and `AmbientCapabilities=`
empty drop every capability, alongside the same `ProtectSystem=strict`
hardening block `telepatch-bot.service` uses. Root with no capabilities is
much closer to the bot's posture than plain root. The dedicated-user
alternative is commented inline in the unit.

## Configuration

Everything that varies lives in `/opt/telepatch/.env`:

```
OBSERVER_TOKEN=            # telepatch-ops Telegraph token
OBSERVER_PAGE_PATH=telepatch-server-performance-08-01
OBSERVER_SAMPLE_SECONDS=120
OBSERVER_PUBLISH_SECONDS=1800
OBSERVER_LOG=/var/log/telepatch/observer.log
OBSERVER_UNIT=telepatch-bot.service
```

The page path being configuration rather than state is what makes a second
page impossible. There is no `--create-page`; the page already exists.

## Testing

Pure modules get fixture-driven tests in the existing `tests/` style —
`/proc/cpuinfo` text captured from a PowerBook G4, aggregate arithmetic
including all-`None` sensors, render output shape, counter-reset handling.

The test that matters most is the AST walk over `tally()` call sites. One
property, and it guards the entire privacy claim.
