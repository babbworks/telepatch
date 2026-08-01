"""
Asking systemd about the bot.

This is the half of the job that could not be done from inside bot.py: a
process cannot report its own death. Everything here is read-only - the
observer never starts, stops or restarts anything, and nothing in this file
should ever grow the ability to.

`systemctl show` is used rather than the D-Bus API because it needs no
dependency, and rather than `systemctl status` because show is a stable
key=value format meant for machines while status is prose meant for people.
"""

import subprocess

# What we ask for. Every one of these is documented in systemd.directives
# and safe to request from a unit that may not exist - systemctl answers
# with empty values rather than failing.
PROPERTIES = (
    "LoadState",             # loaded | not-found | masked | error
    "ActiveState",           # active | inactive | failed | activating
    "SubState",              # running | dead | start-pre ...
    "NRestarts",             # cumulative, since the unit was last reset
    "MainPID",
    "MemoryCurrent",         # bytes, or a huge sentinel when unaccounted
    "ActiveEnterTimestampMonotonic",   # microseconds since boot
    "ExecMainStatus",        # exit code of the last main process
)

# systemd reports "no value" for MemoryCurrent as 2^64-1 rather than
# omitting the field, and printing 18 exabytes of RAM on a PowerBook would
# be quite the headline.
UNSET = 2 ** 64 - 1


def show(unit, timeout=10):
    """
    Raw `systemctl show` output as a dict, or {} if systemd did not answer.

    A timeout matters more than it looks: on a machine this old, a systemd
    that is itself wedged would otherwise hang the sample tick forever and
    take the observer down with the thing it was supposed to be watching.
    """

    try:
        result = subprocess.run(
            [
                "systemctl", "show", unit,
                "--property=" + ",".join(PROPERTIES),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    except (OSError, subprocess.SubprocessError):
        return {}

    values = {}

    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")

        if key:
            values[key.strip()] = value.strip()

    return values


def integer(values, key):
    try:
        number = int(values.get(key, ""))

    except ValueError:
        return None

    return None if number in (UNSET, 0) and key == "MemoryCurrent" else number


def state(unit, uptime_seconds=None):
    """
    What the bot is doing, in terms the page can print.

    `active_for` is derived from the monotonic timestamp against the
    machine's own uptime rather than from a wall clock, so it stays correct
    across an NTP step - which on hardware with a dying PRAM battery is not
    a hypothetical.
    """

    values = show(unit)

    if not values:
        return {
            "unit": unit,
            "loaded": None,
            "active": None,
            "sub": None,
            "restarts": None,
            "memory": None,
            "active_for": None,
            "reachable": False,
        }

    entered = integer(values, "ActiveEnterTimestampMonotonic")

    # A unit that has never started reports 0 here rather than omitting the
    # field, and `uptime - 0` is the machine's uptime - which would have
    # published the age of the server as the age of a bot that was never
    # running. Zero means unknown, not "since boot".
    active_for = None
    if entered and uptime_seconds:
        active_for = max(0.0, uptime_seconds - entered / 1_000_000)

    return {
        "unit": unit,
        # A unit that was never installed answers ActiveState=inactive,
        # SubState=dead - indistinguishable from a bot that crashed unless
        # LoadState is checked. "Not installed" and "died" deserve very
        # different reactions from whoever is reading the page.
        "loaded": values.get("LoadState") or None,
        "active": values.get("ActiveState") or None,
        "sub": values.get("SubState") or None,
        "restarts": integer(values, "NRestarts"),
        "memory": integer(values, "MemoryCurrent"),
        "exit_status": integer(values, "ExecMainStatus"),
        "active_for": active_for,
        "reachable": True,
    }


def healthy(status):
    """
    One boolean for the headline. Anything that is not cleanly active is
    worth saying loudly, including the case where systemd itself did not
    answer - an observer that cannot see the bot should not imply the bot
    is fine.
    """

    return bool(status.get("reachable")) and status.get("active") == "active"
