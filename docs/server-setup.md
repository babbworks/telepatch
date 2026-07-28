# Setting up a server

For a dedicated machine or VM. Written for Debian or Ubuntu; anything with
systemd works with small changes.

Takes about twenty minutes. Nothing here needs a domain, a certificate, or
an open port — Telepatch dials out and listens on nothing.

> **The one rule that matters:** only one process may poll a Telegram token
> at a time. Two bots on one token each see roughly half the updates, so
> the bot appears to ignore messages at random — a miserable thing to
> debug. **Stop the old one before starting the new one.** Cutover is at
> the end of this document.

---

## 0. What the machine needs

Very little. The bot is one Python process that holds no state.

| | |
|---|---|
| RAM | 512 MB is comfortable; the unit caps it there |
| Disk | 1 GB, almost all of it Python |
| CPU | one core |
| Network | **outbound only** — no ports to open |
| OS | anything with systemd 245+ |

A VM on a laptop is fine. So is the smallest VPS anyone sells. The
constraint is that it stays powered on, not that it is fast.

---

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
```

Optional but recommended, because nobody remembers to patch a machine they
never log into:

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 2. A user that owns nothing

The bot writes no files and needs no home directory. Giving it a login
shell or a writable home would only be something to take away later.

```bash
sudo useradd --system --home /opt/telepatch --shell /usr/sbin/nologin telepatch
```

---

## 3. The code

```bash
sudo mkdir -p /opt/telepatch
sudo chown telepatch:telepatch /opt/telepatch

sudo -u telepatch git clone https://github.com/babbworks/telepatch /opt/telepatch
cd /opt/telepatch

sudo -u telepatch python3 -m venv .venv
sudo -u telepatch .venv/bin/pip install -r requirements.txt
```

Check it before it ever runs as a service:

```bash
sudo -u telepatch .venv/bin/pip install -r requirements-dev.txt
sudo -u telepatch .venv/bin/python -m pytest
```

If the tests fail, stop. They cover the functions that rewrite people's
pages, and Telegraph has no undo.

---

## 4. Configuration

```bash
sudo cp /opt/telepatch/.env.example /opt/telepatch/.env
sudo nano /opt/telepatch/.env
```

`TELEGRAM_TOKEN` is the only required setting. **Use a different token
from the one currently running** while you are testing — see cutover.

Then lock it down. This file is the only credential on the machine:

```bash
sudo chown root:telepatch /opt/telepatch/.env
sudo chmod 640 /opt/telepatch/.env
```

Root owns it, the bot may read it, nobody else can. Verify:

```bash
ls -l /opt/telepatch/.env      # -rw-r----- root telepatch
```

### Worth setting on a server, pointless on a laptop

**`OPERATOR_CHAT`** — where unhandled errors are sent, so a failure reaches
a person rather than a log nobody reads. To find your chat id, message the
bot anything and look:

```bash
journalctl -u telepatch-bot -n 50 | grep -i chat
```

or message `@userinfobot`, which replies with it.

**`HEARTBEAT_URL`** — the dead man's switch. Because the bot opens no port,
nothing outside can check whether it is alive; it has to say so itself, and
**silence is the alarm**. Make a free check at healthchecks.io (or Better
Stack, or your own endpoint), set the URL, and set its expected period a
little longer than `HEARTBEAT_SECONDS`.

This is the single highest-value thing on a machine you do not look at.
Without it, "the bot has been down since Tuesday" is something you find out
from a user.

---

## 5. The service

```bash
sudo cp /opt/telepatch/telepatch-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telepatch-bot        # enable, do not start yet
```

**Do not start it yet** if another instance is still polling that token.

What the unit is doing, briefly, because it is worth understanding rather
than copying:

- **`Type=notify` with `WatchdogSec=180`.** A bot that has stopped polling
  looks perfectly healthy to `Restart=always` — the process is still there.
  The bot pings systemd every 90 seconds, and only while its updater
  reports itself running, so a wedged poller stops the pings and gets
  restarted.
- **`KillSignal=SIGINT` and `TimeoutStopSec=30`.** An in-flight `editPage`
  gets to finish. Telegraph has no transactions and no undo, so a write
  torn off halfway is a page left wrong.
- **`MemoryMax=512M`, `TasksMax=64`, `CPUQuota=200%`.** Ceilings, not
  budgets. Hitting one is a bug worth investigating, not a limit to raise.
- **The sandbox.** `ProtectSystem=strict`, an empty
  `CapabilityBoundingSet`, `SystemCallFilter=@system-service`, no writable
  paths at all. The bot writes nothing, so it is given nothing.

---

## 6. Cutover

The careful order. Read it before starting.

```bash
# 1. On the OLD machine — stop it first, always.
systemctl --user stop telepatch-bot        # or: kill the nohup process
systemctl --user disable telepatch-bot

# 2. Confirm nothing is still polling.
pgrep -af bot.py                           # should print nothing

# 3. On the NEW machine — start.
sudo systemctl start telepatch-bot
sudo systemctl status telepatch-bot
```

Then prove it, in the chat, in this order — each step costs one more than
the last:

| | |
|---|---|
| `/privacy` | the bot is receiving updates at all |
| `/pages` | the Telegraph token works — one read |
| `/site` on a **throwaway identity** | a write works |

Do not test writes against a real publication. Make a scratch identity with
`/new` and use that.

---

## 7. Day to day

```bash
systemctl status telepatch-bot
journalctl -u telepatch-bot -f
journalctl -u telepatch-bot -p warning --since today
sudo systemctl restart telepatch-bot
```

Deploying a change:

```bash
./deploy.sh telepatch@your-server
```

It runs the tests locally first, refuses to deploy over uncommitted edits
made on the server, stops before it starts, and shows you the log
afterwards.

[runbook.md](runbook.md) covers what to do when something is wrong.

---

## 8. A staging bot, which is not optional

Make a second bot with @BotFather. Copy the unit to
`telepatch-staging.service`, point it at a second checkout with its own
`.env`, and run both.

The bot stores nothing, so a staging instance costs a token and nothing
else. Given that **every write here is irreversible** — Telegraph has no
`deletePage`, and `editPage` replaces a page wholesale — this is where a
change gets tried. Not production.

---

## What you do not have to do

Worth stating, because their absence looks like an oversight:

- **No inbound firewall rules.** Long polling dials out. Nothing listens.
- **No TLS certificate, no domain, no reverse proxy.** Same reason.
- **No database, and no backups.** There is nothing to back up: the bot
  keeps no state between messages. Every collection lives on Telegraph, in
  a page its publisher owns.
- **No log rotation config.** journald handles it.

The only things worth keeping somewhere safe are the bot token and your
access to the machine. Both belong in a password manager.
