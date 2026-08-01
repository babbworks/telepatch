"""
Reading the bot's activity counters.

The bot writes a small JSON file into /run/telepatch, which is tmpfs
created by `RuntimeDirectory=telepatch` in its unit and **deleted by
systemd when the unit stops**. That is the whole persistence story: the
counters cannot outlive the process, because the filesystem they live on
does not. "Nothing survives a restart" is enforced by the init system
rather than promised in prose.

This module only ever reads. If the file is absent - bot stopped, bot too
old to export, tmpfs not mounted - it returns None and the page says
activity is unavailable rather than showing zeros. Zeros would be a lie:
"no commands were run" and "we could not tell" are different claims.

See bot.py's tally() for the writing half, and the closed vocabulary that
makes any of this publishable.
"""

import json
import os

DEFAULT_PATH = "/run/telepatch/counters.json"


def read(path=DEFAULT_PATH):
    """
    The current snapshot as {"since": epoch, "events": {name: count}}, or
    None if there is nothing readable there.

    A partially written file is a real possibility - the bot rewrites this
    on its own timer and we read it on ours, with no lock between them.
    A truncated read is caught as a JSON error and treated as "no snapshot
    this time"; the next tick will find a whole one. This is why the bot
    writes atomically via rename, and why a torn read is rare rather than
    impossible.
    """

    try:
        with open(path, "r") as handle:
            payload = json.load(handle)

    except (OSError, ValueError):
        return None

    events = payload.get("events")

    if not isinstance(events, dict):
        return None

    # Coerce here rather than trusting the file. This is the only place
    # data crosses from another process into the published page, so it is
    # the right place to insist on the shape.
    clean = {
        str(key): int(value)
        for key, value in events.items()
        if isinstance(value, (int, float))
    }

    return {"since": payload.get("since"), "events": clean}


def events(snapshot):
    """The counts alone, or {} - saves the caller a None check per use."""

    return (snapshot or {}).get("events", {})


def available(path=DEFAULT_PATH):
    """
    Whether the bot is exporting at all.

    Distinguished from "exporting zeros" on purpose: the page renders those
    two states differently, and conflating them would let a broken export
    masquerade as a quiet afternoon.
    """

    return os.path.exists(path)
