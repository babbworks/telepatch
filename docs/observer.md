# telepatch-observer

Publishes what the PowerBook is doing to
[telegra.ph/telepatch-server-performance-08-01](https://telegra.ph/telepatch-server-performance-08-01),
and keeps a local copy of everything it publishes.

Samples every 2 minutes, publishes the 30-minute mean. 48 edits a day.

Design and the reasoning behind the privacy rules:
[specs/2026-08-01-observer-design.md](superpowers/specs/2026-08-01-observer-design.md).

---

## Written blind

**This was written without access to the PowerBook.** The `/proc` parsing
is safe — those formats are stable and ancient. The **sensor paths are
educated guesses**, because PowerPC thermal support moved between three
drivers over the years and which one binds depends on the exact model and
kernel.

Nothing here fails hard because of it: a sensor that does not resolve is
simply left off the page. But the first published page will tell you what
this machine actually has, and you may want to add real paths afterwards.

---

## Install

On a fresh machine, `install.sh` does all of this for you:

```sh
sudo git clone https://github.com/babbworks/telepatch.git /opt/telepatch
cd /opt/telepatch
sudo cp .env.example .env && sudo nano .env    # tokens go here
sudo ./install.sh
```

The rest of this section is what that script does, for when it has to be
done by hand or checked afterwards. Everything below runs as root.

### 1. Get the code and confirm the venv

```sh
cd /opt/telepatch
git pull
```

The observer needs `requests` and `python-dotenv`, both already in
`requirements.txt` for the bot. If the venv predates this, refresh it:

```sh
/opt/telepatch/.venv/bin/pip install -r /opt/telepatch/requirements.txt
```

On Debian ports for 32-bit PowerPC, prefer the distribution packages over
building wheels — there is no reason to make a 1.5GHz G4 compile anything:

```sh
apt-get install python3-requests python3-dotenv
```

### 2. Add the settings

Append to `/opt/telepatch/.env`:

```sh
OBSERVER_TOKEN=<the telepatch-ops Telegraph token>
OBSERVER_PAGE_PATH=telepatch-server-performance-08-01
```

Everything else has a working default. The full list with explanations is
in `.env.example`.

**Permissions matter here, and 0600 is wrong.** The file must be readable
by the bot's service account:

```sh
chown root:telepatch /opt/telepatch/.env
chmod 640 /opt/telepatch/.env
```

systemd reads `EnvironmentFile=` as root, so `0600 root:root` looks correct
and starts nothing. But `bot.py:52` calls `load_dotenv()` at module scope,
which walks up from `WorkingDirectory`, finds this file, and raises
`PermissionError` as `User=telepatch` — before `main()` runs. The symptom is
a crash loop with `status=1/FAILURE` and no log line explaining why.

The observer does not show this because it runs as root and can read the
file regardless. A working observer is not evidence that the bot's
permissions are right.

### 3. Let the bot export counters

The bot now writes activity counts to `/run/telepatch/counters.json`, which
needs one addition to its unit. That change is already in the repo copy:

```sh
cp /opt/telepatch/telepatch-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart telepatch-bot
```

Confirm it landed:

```sh
cat /run/telepatch/counters.json
```

You should see `{"since": ..., "events": {...}}` within about a minute of
the restart. If the file never appears, the observer will say so on the
page rather than showing zeros — but check `RuntimeDirectory=telepatch` is
in the installed unit.

**Note:** the installed unit may not match the repo copy. `deployment-details.md`
records `User: mp` while `telepatch-bot.service` says `User=telepatch`.
Check before copying over the top of a working service:

```sh
diff /etc/systemd/system/telepatch-bot.service /opt/telepatch/telepatch-bot.service
```

### 4. Start the observer

```sh
cp /opt/telepatch/telepatch-observer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now telepatch-observer
journalctl -u telepatch-observer -f
```

A healthy start logs the account it authenticated as, then the machine it
detected:

```
observer.account short_name=telepatch-ops author=Telepatch Operations pages=1
observer.started machine=PowerBook5,6 sample=120s publish=1800s ...
```

**The first publish lands about two minutes after start**, not thirty — so
you find out quickly whether it works. After that it settles into the
30-minute cadence.

---

## Confirming the sensors

The published page carries a line like:

```
Sensors: fan_rpm=no, temperature=yes
```

Anything reading `no` did not resolve on this machine. To find the real
paths:

```sh
cat /proc/cpuinfo
ls -l /sys/devices/temperatures/       # therm_adt746x, the G4-era driver
ls -l /sys/class/hwmon/*/              # generic hwmon
ls -d /sys/devices/platform/windfarm*  # later PowerMacs
ls -l /sys/class/power_supply/         # battery and AC
cat /proc/pmu/info                     # PMU, PowerPC only
```

Then add whatever exists to `TEMPERATURE_CANDIDATES` or `FAN_CANDIDATES` in
`observer/probe.py`. They are plain tuples in priority order; adding a path
is a one-line change, and the module docstring says the same thing again
next to the code.

```sh
systemctl restart telepatch-observer
```

---

## When something is wrong

**The page says "systemd did not answer."**
Almost certainly the hardening. `ProtectSystem=strict` mounts everything
read-only except `/dev`, `/proc` and `/sys` — including `/run` — and
connecting to a unix socket needs write permission on the socket inode, so
`systemctl show` cannot reach systemd. The unit already carries
`ReadWritePaths=-/run/systemd` and `-/run/dbus` for this. If it still
fails, comment out `ProtectSystem=strict` and confirm that is the cause
before looking anywhere else.

**The page says the bot is not exporting counters.**
Either the bot has not been restarted since the `RuntimeDirectory=` change,
or it is an older build. Check `/run/telepatch/counters.json` exists.
Hardware reporting is unaffected and carries on.

**The service exits immediately.**
It refuses to start on a missing or rejected token rather than failing
silently half an hour later. `journalctl -u telepatch-observer -n 20` will
name which setting.

**Activity says "hour ending unknown".**
Normal for the first hour after a start. Activity reports the last
*completed* hour, so there is nothing to show until one has passed.

**Nothing on the page changes.**
Check the local log first — `/var/log/telepatch/observer.log` is written
even when Telegraph is unreachable, so if it is current the problem is the
network or Telegraph, not the observer.

---

## The local copy

```
/var/log/telepatch/observer.log   what was published, every 30 minutes
/var/log/telepatch/samples.log    every 2-minute reading, one JSON per line
```

Both self-trim by line count — no logrotate config to install. Defaults
hold roughly three weeks of published blocks and one week of raw samples.

`samples.log` holds the readings the page only shows as means, which makes
it the more detailed artifact of the two, and the one to think about before
sharing.

---

## What is published about people

Nothing that identifies one.

The counters the page shows are a fixed list, defined as `COUNTED` at the
top of `bot.py`. `tally()` takes one argument and it must be a literal from
that set — no token, chat id, user id, title, path or category can reach
it. This is enforced rather than intended:
`tests/test_observer_tally.py` walks the AST of `bot.py` and fails if any
call site passes anything else.

Counts below 5 publish as `<5`, and activity advances once an hour rather
than every 30 minutes, so that no short window can be singled out by
diffing the page.

The counters live in `/run/telepatch`, which is tmpfs, and systemd deletes
it when the bot stops. Nothing survives a restart because the filesystem
does not.

**`/privacy` in the bot still says "no file is ever written", which is no
longer true.** Rewording it is not done yet and should be, before this is
publicised.

---

## Cadence

| | |
|---|---|
| sample | every 120 s |
| publish | every 1800 s (48/day) |
| activity boundary | top of each hour |

Telegraph documents no rate limits. For scale, one `/site` rebuild in the
bot can fire ~200 API calls in a burst (`SCAN_WORKERS = 8` over
`INDEX_LIMIT = 200`), so a full day of observer traffic is a quarter of a
single index rebuild, spread evenly. The observer only ever calls
`editPage` on a path from configuration — there is no `createPage` anywhere
in it, so it cannot mint a second page however often it restarts.

To change the cadence, set `OBSERVER_PUBLISH_SECONDS` and restart. Raising
it is safe; lowering it below a few minutes is untested against whatever
undocumented limit Telegraph enforces.
