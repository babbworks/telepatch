#!/usr/bin/env bash
#
# Deploy Telepatch to whatever is running the systemd unit.
#
#   ./deploy.sh                                # this machine, /opt/telepatch
#   ./deploy.sh local v1.2.0                   # this machine, a tag
#   ./deploy.sh telepatch@example.com          # a server, main
#   ./deploy.sh telepatch@example.com v1.2.0   # a server, a tag
#
# Only one process may poll a token at a time, so this stops before it
# starts. There is no rolling deploy and there should not be: two bots on
# one token looks like random message loss.
#
# There is nothing to migrate and nothing to back up. That is the design
# working, not an omission.
#
# This UPDATES an install. install.sh is what creates one.

set -euo pipefail

HOST="${1:-local}"
REF="${2:-main}"
UNIT="${TELEPATCH_UNIT:-telepatch-bot}"

# The observer is restarted alongside the bot when it is installed. It
# reads no state from the bot beyond a counters file, so the order does not
# matter and neither does a gap between them.
OBSERVER_UNIT="${TELEPATCH_OBSERVER_UNIT:-telepatch-observer}"

DIR="${TELEPATCH_DIR:-/opt/telepatch}"

echo "==> tests first, always"
python -m pytest -q

# ---------------------------------------------------------------- local

if [ "$HOST" = "local" ]; then
  echo "==> deploying $REF to $DIR, as system services"

  # These used to be --user units running straight out of a development
  # checkout. They are system units now, installed from a separate clone at
  # $DIR, so a local deploy updates that clone rather than this one.
  if [ ! -d "$DIR/.git" ]; then
    echo "$DIR is not a git checkout. Run install.sh first." >&2
    exit 1
  fi

  if ! sudo git -C "$DIR" diff --quiet ||
     ! sudo git -C "$DIR" diff --cached --quiet; then
    echo "working tree at $DIR is dirty; someone edited production" >&2
    exit 1
  fi

  sudo git -C "$DIR" fetch --tags --prune origin
  sudo git -C "$DIR" checkout --detach "origin/$REF" 2>/dev/null ||
    sudo git -C "$DIR" checkout --detach "$REF"

  sudo "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"

  # Prove the new code at least parses before it becomes the running one.
  sudo "$DIR/.venv/bin/python" -c "import ast; ast.parse(open('$DIR/bot.py').read())"

  UNITS="$UNIT"
  systemctl list-unit-files "$OBSERVER_UNIT.service" --no-legend |
    grep -q . && UNITS="$UNITS $OBSERVER_UNIT"

  # shellcheck disable=SC2086
  sudo systemctl restart $UNITS
  sleep 5

  for unit in $UNITS; do
    systemctl is-active "$unit"
    journalctl -u "$unit" -n 10 --no-pager || true
  done

  echo "==> deployed $REF"
  exit 0
fi

# --------------------------------------------------------------- remote

echo "==> deploying $REF to $HOST:$DIR"

ssh "$HOST" bash -euo pipefail <<REMOTE
  cd "$DIR"

  # Refuse to deploy over uncommitted edits made on the server. Someone
  # debugging in production should not lose their work to a deploy.
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "working tree is dirty on the server; refusing" >&2
    exit 1
  fi

  git fetch --tags --prune origin
  git checkout --detach "origin/$REF" 2>/dev/null || git checkout --detach "$REF"

  .venv/bin/pip install -q -r requirements.txt

  # Prove the new code at least imports before it becomes the running one.
  .venv/bin/python -c "import ast,sys; ast.parse(open('bot.py').read())"

  UNITS="$UNIT"
  systemctl list-unit-files "$OBSERVER_UNIT.service" --no-legend |
    grep -q . && UNITS="\$UNITS $OBSERVER_UNIT"

  sudo systemctl restart \$UNITS
REMOTE

echo "==> waiting for it to come up"
sleep 5

ssh "$HOST" "systemctl is-active $UNIT && journalctl -u $UNIT -n 15 --no-pager"

echo "==> deployed $REF"
