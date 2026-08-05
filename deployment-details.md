# Where this runs

Two machines, both live: `deb` is the day-to-day host, the PowerBook runs
the same units plus one machine-specific override. See
[Profiles](#profiles) below for how that override is kept in the repo
instead of only existing on the machine.

---

## deb — current, since 2026-08-01

Running `telepatch-bot` and `telepatch-observer` as **system** services,
both enabled at boot.

```
Install       /opt/telepatch              root:root 0755
Units         /etc/systemd/system/telepatch-bot.service
              /etc/systemd/system/telepatch-observer.service
Bot user      telepatch                   (system account, nologin)
Observer user root                        (all capabilities dropped)
Python        /opt/telepatch/.venv
Environment   /opt/telepatch/.env         root:telepatch 0640
Counters      /run/telepatch/counters.json  tmpfs, dies with the unit
Logs          /var/log/telepatch/           observer.log, samples.log
```

**`.env` must be 0640 root:telepatch, not 0600 root:root.** systemd reads
`EnvironmentFile=` as root, so 0600 looks right and starts nothing —
`bot.py:52` also calls `load_dotenv()` after privileges are dropped, and
dies with `PermissionError` before `main()`. `Restart=always` turns that
into a crash loop reporting "activating" with nothing in the journal to
explain it. See [docs/observer.md](docs/observer.md).

The `--user` unit that previously ran here is **disabled**. It must stay
that way: two processes polling one Telegram token do not error, they split
the updates between them, which reads as random message loss. `morgen` has
`Linger=yes`, so a re-enabled user unit would start at boot and conflict.

Installed with `sudo ./install.sh`. Updates via
`sudo systemctl restart telepatch-bot telepatch-observer`, or `./deploy.sh
local` once a change is pushed.

---

## PowerBook G4 — since 2026-08-05

```
Machine       PowerBook5,4, Debian ports (32-bit PowerPC), 1 CPU core
Install       /opt/telepatch              root:root 0755
Units         /etc/systemd/system/telepatch-bot.service
              /etc/systemd/system/telepatch-observer.service
              /etc/systemd/system/telepatch-observer.service.d/override.conf
Bot user      telepatch                   (system account, nologin)
Observer user root                        (all capabilities dropped)
Python        /opt/telepatch/.venv
Environment   /opt/telepatch/.env         root:telepatch 0640
Observer page telegra.ph/telepatch-server-performance-08-01, account telepatch-ops
```

Installed with `sudo ./install.sh powerbook` — see [Profiles](#profiles).

**Single core, and more tools are planned for this machine.** Rather than
shrink the observer's resource ceilings further (`MemoryMax=128M` /
`CPUQuota=25%` are already modest), the `powerbook` profile deprioritizes
it *relative* to everything else — `Nice=10`, `CPUWeight=20`, best-effort
I/O at the lowest priority — so it yields the one core under real
contention instead of competing evenly with the bot or whatever gets added
next. Give any future service on this box the same treatment unless it is
the priority workload.

**Sensor paths are guesses.** PowerPC thermal support moved between
`therm_adt746x`, `windfarm` and `hwmon` over the years, and which binds
depends on the exact model and kernel. Every probe fails soft, and the
published page prints a `Sensors:` line naming what resolved. See the
module docstring in `observer/probe.py` for the read-only commands that
reveal the real paths.

**Prefer distribution packages to building wheels.** There is no reason to
make a 1.5GHz G4 compile anything:

```sh
apt-get install python3-requests python3-dotenv
```

---

## Profiles

Different machines need different systemd tuning — a shared laptop-class
host and a single-core 2005 PowerPC box do not want the same resource
priorities. Rather than branch `install.sh` or the unit files themselves
per machine, a profile is just a directory of **drop-in overrides** layered
on top of the base units:

```
deploy/
  powerbook/
    telepatch-observer.service.d/
      override.conf
```

`sudo ./install.sh <profile>` installs the base units as usual, then — if
`deploy/<profile>/` exists — copies every `*.service.d/*.conf` under it
into the matching `/etc/systemd/system/*.service.d/` before the final
`daemon-reload`. No profile argument means a plain install, identical to
before profiles existed.

This only holds *differences* from the base unit, on purpose. The base
`telepatch-bot.service` / `telepatch-observer.service` stay the single
source of truth for what the service fundamentally is; a profile only ever
narrows or reprioritizes within that, via systemd's own drop-in mechanism
(`systemctl cat <unit>` shows the merged result). A machine that needs a
genuinely different unit, not just an override, is a sign the base unit
should grow a knob (an environment variable, most likely) rather than the
profile mechanism growing the ability to replace whole files.

Adding a profile for a new machine class: create `deploy/<name>/`, add
whatever `*.service.d/override.conf` files it needs, and document the
machine in a new section above like the two already here.
