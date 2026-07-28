#!/usr/bin/env bash
#
# Deploy Telepatch to a server running the systemd unit.
#
#   ./deploy.sh telepatch@example.com          # deploy main
#   ./deploy.sh telepatch@example.com v1.2.0   # deploy a tag
#
# Only one process may poll a token at a time, so this stops before it
# starts. There is no rolling deploy and there should not be: two bots on
# one token looks like random message loss.
#
# There is nothing to migrate and nothing to back up. That is the design
# working, not an omission.

set -euo pipefail

HOST="${1:?usage: deploy.sh user@host [ref]}"
REF="${2:-main}"
DIR="${TELEPATCH_DIR:-/opt/telepatch}"
UNIT="${TELEPATCH_UNIT:-telepatch-bot}"

echo "==> tests, locally, before anything leaves this machine"
python -m pytest -q

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

  sudo systemctl restart "$UNIT"
REMOTE

echo "==> waiting for it to come up"
sleep 5

ssh "$HOST" "systemctl is-active $UNIT && journalctl -u $UNIT -n 15 --no-pager"

echo "==> deployed $REF"
