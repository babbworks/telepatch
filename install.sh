#!/usr/bin/env bash
#
# First-time install of Telepatch and telepatch-observer as system services.
#
#   sudo git clone https://github.com/babbworks/telepatch.git /opt/telepatch
#   cd /opt/telepatch
#   sudo cp .env.example .env && sudo nano .env      # add your tokens
#   sudo ./install.sh
#
# This is a bootstrap, not a deploy. deploy.sh updates an install that
# already exists; this is what creates one. Run it once per machine.
#
# It installs from whatever directory it lives in. If that is not
# /opt/telepatch it copies itself there first, so cloning to a home
# directory and running it from there also works.
#
# Idempotent apart from the venv, which is rebuilt every time.
#
# Pass a profile name to also layer machine-specific systemd overrides from
# deploy/<profile>/ on top of the base units - e.g. `sudo ./install.sh
# powerbook` applies deploy/powerbook/*.service.d/*.conf. Optional; omit it
# for a plain install. See deployment-details.md for what each profile is.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DST="${TELEPATCH_DIR:-/opt/telepatch}"
SVC_USER="${TELEPATCH_USER:-telepatch}"
PROFILE="${1:-${TELEPATCH_PROFILE:-}}"

say() { printf '\n==> %s\n' "$*"; }

# ---------------------------------------------------------------- preflight

[ "$(id -u)" -eq 0 ] || { echo "run me with sudo" >&2; exit 1; }

# Only one process may poll a Telegram token at a time. Two pollers do not
# error - they silently split the updates between them, which reads as
# random message loss. Refuse rather than create that.
if pgrep -f "[b]ot\.py" >/dev/null 2>&1; then
  echo "something is already running bot.py - stop it first:" >&2
  pgrep -af "[b]ot\.py" >&2
  exit 1
fi

# ------------------------------------------------------------------- code

if [ "$HERE" != "$DST" ]; then
  say "copying $HERE -> $DST"

  mkdir -p "$DST"

  # .env is handled separately below, with permissions that matter. The
  # venv is rebuilt for the destination path. Caches are noise.
  rsync -a \
    --exclude '.env' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    "$HERE"/ "$DST"/

  # If the tokens were configured at the source, bring them along.
  [ -f "$HERE/.env" ] && [ ! -f "$DST/.env" ] && cp "$HERE/.env" "$DST/.env"
else
  say "installing in place at $DST"
fi

chown -R root:root "$DST"
chmod 755 "$DST"

# ------------------------------------------------------------------- user

if id -u "$SVC_USER" >/dev/null 2>&1; then
  say "service user $SVC_USER already exists"
else
  say "creating system user $SVC_USER"
  useradd --system --shell /usr/sbin/nologin --home-dir "$DST" \
          --no-create-home "$SVC_USER"
fi

# -------------------------------------------------------------------- env

if [ ! -f "$DST/.env" ]; then
  install -o root -g "$SVC_USER" -m 640 "$DST/.env.example" "$DST/.env"

  cat >&2 <<NOTE

  No .env was found, so one was created from .env.example:

      $DST/.env

  It has no tokens in it yet, so nothing will start. Fill in
  TELEGRAM_TOKEN (and OBSERVER_TOKEN / OBSERVER_PAGE_PATH if you want the
  observer), then run this script again.

NOTE
  exit 1
fi

# 0640 root:$SVC_USER, NOT 0600 root:root.
#
# THE TRAP THIS AVOIDS: systemd reads EnvironmentFile= as root and injects
# it before dropping privileges, so 0600 root:root looks correct and is
# what every instinct about a secrets file tells you to use. But bot.py
# ALSO calls load_dotenv() at module scope (bot.py:52), which runs after
# privileges are dropped, walks up from WorkingDirectory, finds this file,
# and cannot read it as $SVC_USER.
#
# The result is PermissionError before main(), which Restart=always turns
# into a crash loop reporting "activating (auto-restart)" with nothing in
# the journal explaining why. The environment was already loaded correctly;
# it is the redundant second read that dies.
#
# The observer does not show this, because it runs as root and reads the
# same file happily. A working observer is not evidence the bot's
# permissions are right.
say "securing .env (root:$SVC_USER 0640)"

chown "root:$SVC_USER" "$DST/.env"
chmod 640 "$DST/.env"

for key in TELEGRAM_TOKEN; do
  grep -q "^${key}=" "$DST/.env" || {
    echo "$key is not set in $DST/.env - the bot will not start" >&2
    exit 1
  }
done

if grep -q '^OBSERVER_TOKEN=' "$DST/.env"; then
  WANT_OBSERVER=yes
else
  WANT_OBSERVER=no
  echo "    no OBSERVER_TOKEN; installing the bot only"
fi

# ------------------------------------------------------------------- venv

say "building venv at $DST/.venv"

rm -rf "$DST/.venv"
python3 -m venv "$DST/.venv"
"$DST/.venv/bin/pip" install --quiet --upgrade pip
"$DST/.venv/bin/pip" install --quiet -r "$DST/requirements.txt"
"$DST/.venv/bin/python" -c "import telegram, requests, dotenv; print('    deps ok')"

# ------------------------------------------- retire any --user unit

# A machine that ran Telepatch as a --user service before must not keep
# doing so alongside the system unit: two pollers on one token is silent
# message loss.
for home in /home/*; do
  owner="$(basename "$home")"
  id -u "$owner" >/dev/null 2>&1 || continue

  runtime="/run/user/$(id -u "$owner")"
  [ -d "$runtime" ] || continue

  if runuser -u "$owner" -- env "XDG_RUNTIME_DIR=$runtime" \
       systemctl --user is-enabled telepatch-bot >/dev/null 2>&1; then
    say "retiring $owner's --user telepatch-bot unit"
    runuser -u "$owner" -- env "XDG_RUNTIME_DIR=$runtime" \
      systemctl --user disable --now telepatch-bot || true
  fi
done

# ------------------------------------------------------------------ units

say "installing systemd units"

install -m 644 "$DST/telepatch-bot.service" /etc/systemd/system/
UNITS="telepatch-bot"

if [ "$WANT_OBSERVER" = yes ]; then
  install -m 644 "$DST/telepatch-observer.service" /etc/systemd/system/
  UNITS="$UNITS telepatch-observer"
fi

# ------------------------------------------------------------- profile

if [ -n "$PROFILE" ]; then
  PROFILE_DIR="$DST/deploy/$PROFILE"

  if [ -d "$PROFILE_DIR" ]; then
    say "applying '$PROFILE' profile overrides"

    for d in "$PROFILE_DIR"/*.service.d; do
      [ -d "$d" ] || continue
      unit_dir="/etc/systemd/system/$(basename "$d")"
      mkdir -p "$unit_dir"
      install -m 644 "$d"/*.conf "$unit_dir/"
      echo "    $(basename "$unit_dir")"
    done
  else
    echo "    no deploy/$PROFILE directory - skipping profile overrides" >&2
  fi
fi

systemctl daemon-reload
# shellcheck disable=SC2086
systemctl enable --now $UNITS

# ----------------------------------------------------------------- verify

say "waiting for things to settle"
sleep 8

for unit in $UNITS; do
  systemctl --no-pager --lines=0 status "$unit" || true
done

if [ "$WANT_OBSERVER" = yes ]; then
  say "counters export (bot -> observer)"
  if [ -f /run/telepatch/counters.json ]; then
    cat /run/telepatch/counters.json; echo
  else
    echo "    not there yet - the bot writes it on a 60s timer"
  fi
fi

say "installed"
cat <<NOTE

  journalctl -u telepatch-bot -f
  journalctl -u telepatch-observer -f
  ls -la /var/log/telepatch/

  The observer publishes about two minutes after start, then every thirty.
  Activity counts appear only once a full clock hour has elapsed - until
  then it says so rather than showing a partial hour as a whole one.

  Updates from here on: ./deploy.sh local

NOTE
