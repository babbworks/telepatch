# Where this runs

Two machines. The laptop is the current host; the PowerBook is where this
is headed.

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

## PowerBook G4 — intended

```
Machine       PowerBook G4, Debian ports (32-bit PowerPC)
Install       /opt/telepatch
Environment   /opt/telepatch/.env
```

Not yet installed. Two things to expect there and nowhere else:

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
