"""
Turning a block into a page.

Pure: everything this needs arrives as arguments, including the time, so
the whole page is testable by calling one function and comparing strings.

THE STRUCTURE THAT KEEPS THE LOG HONEST
---------------------------------------
The local log is supposed to duplicate the published page. The fragile way
to do that is two renderers - one making Telegraph nodes, one making text -
which agree on the day they are written and drift by the second change.

So render() returns neither. It returns a list of (kind, text) sections,
and to_nodes() and to_text() are two thin projections of that same list.
The mirror is exact by construction rather than by discipline, and a new
section appears in both places or in neither.

Telegraph's allowed tags are listed at bot.py:224. `pre` is among them,
which is the whole reason this page can use aligned columns instead of
prose - a status board should be scannable, and monospace does that work
for free.
"""

# Width of the label column in a pre block, dots included. Chosen so the
# longest label below still leaves room for a value on an 80-column
# terminal reading the local log.
LEADER = 34


def leader(label, value):
    """`load ............... 0.41` - a dot leader, as in a table of contents."""

    if value is None:
        return None

    text = str(value)
    dots = "." * max(1, LEADER - len(label) - 1)

    return f"{label} {dots} {text}"


def block(lines):
    """Drop the Nones and join. A sensor that did not answer has no line."""

    return "\n".join(line for line in lines if line)


# -------------------------------------------------------------- formatting


def human_bytes(value):
    """
    Bytes as something a person reads. Deliberately coarse - this is a
    status page, and '388M' answers the question that '407,896,064' does
    not.
    """

    if value is None:
        return None

    for unit, size in (("T", 1 << 40), ("G", 1 << 30), ("M", 1 << 20), ("K", 1 << 10)):

        if abs(value) >= size:
            scaled = value / size

            return f"{scaled:.1f}{unit}" if scaled < 10 else f"{scaled:.0f}{unit}"

    return f"{value:.0f}B"


def human_seconds(value):
    """
    Duration at two units of precision. '12d 3h' rather than
    '12d 3h 14m 9s', because nobody reading an uptime wants the seconds.
    """

    if value is None:
        return None

    value = int(value)

    days, rest = divmod(value, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)

    if days:
        return f"{days}d {hours}h"

    if hours:
        return f"{hours}h {minutes}m"

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def gauge(summary, key, unit="", digits=1):
    """
    A mean with its range: `0.41  (0.22-0.88)`.

    The range is what makes a 30-minute mean trustworthy. A load average of
    0.41 could be a machine idling steadily or one alternating between
    asleep and on fire, and those deserve different reactions.

    The range is dropped when it is degenerate, because `47.0 (47.0-47.0)`
    is three copies of one fact.
    """

    entry = (summary or {}).get(key)

    if not entry:
        return None

    mean = f"{entry['mean']:.{digits}f}{unit}"

    if abs(entry["max"] - entry["min"]) < 10 ** -digits:
        return mean

    return f"{mean}  ({entry['min']:.{digits}f}-{entry['max']:.{digits}f}{unit})"


# ------------------------------------------------------------------ page


def machine_section(machine):
    """
    Static identity. On PowerPC this is the interesting part - `machine`,
    `motherboard` and `detected as` are fields x86 simply does not have,
    and 'PowerBook5,6 MacRISC3 Power Macintosh' is a better opening line
    than any status page running on a VPS can manage.
    """

    return block([
        leader("cpu", machine.get("cpu")),
        leader("clock", machine.get("clock")),
        leader("board", machine.get("motherboard")),
        leader("detected as", machine.get("detected")),
        leader("l2 cache", machine.get("cache")),
        leader("generation", machine.get("generation")),
        leader("kernel", machine.get("kernel")),
        leader("arch", machine.get("arch")),
    ])


def health_section(summary, memory_total, disk_used, disk_total,
                   uptime, battery_status):
    return block([
        leader("load", gauge(summary, "load", digits=2)),
        leader("cpu busy", gauge(summary, "cpu_percent", "%", digits=0)),
        leader("memory", (
            f"{human_bytes(summary['memory_used']['mean'])} / "
            f"{human_bytes(memory_total)}"
            if summary.get("memory_used") and memory_total else None
        )),
        leader("swap", (
            human_bytes(summary["swap_used"]["mean"])
            if summary.get("swap_used") else None
        )),
        leader("disk", (
            f"{human_bytes(disk_used)} / {human_bytes(disk_total)}"
            if disk_used and disk_total else None
        )),
        leader("temperature", gauge(summary, "temperature", "C", digits=1)),
        leader("fan", gauge(summary, "fan_rpm", " rpm", digits=0)),
        leader("battery", (
            f"{summary['battery_percent']['mean']:.0f}%"
            + (f"  ({battery_status})" if battery_status else "")
            if summary.get("battery_percent") else battery_status
        )),
        leader("uptime", human_seconds(uptime)),
    ])


def service_section(status):
    """
    The bot, as systemd sees it.

    When systemd did not answer at all we say so rather than leaving the
    section blank: an observer that cannot see the bot must not read as an
    observer reporting a healthy bot.
    """

    if not status.get("reachable"):
        return "systemd did not answer. The state of the bot is unknown."

    # A unit that was never installed reports inactive/dead, which reads as
    # a bot that crashed. Say what actually happened instead.
    if status.get("loaded") == "not-found":
        return (
            f"{status.get('unit')} is not installed on this machine.\n"
            "Nothing is being reported about the bot."
        )

    state = status.get("active") or "unknown"

    if status.get("sub"):
        state = f"{state} ({status['sub']})"

    return block([
        leader("state", state),
        leader("active for", human_seconds(status.get("active_for"))),
        leader("restarts", status.get("restarts")),
        leader("memory", human_bytes(status.get("memory"))),
        leader("last exit", status.get("exit_status")),
    ])


# The labels the page prints, and the order it prints them in. Keys are the
# tally() vocabulary from bot.py; anything the bot reports that is not
# listed here is not published. That is deliberate - the page shows a fixed
# set of lines, so a new counter cannot reach the public page just by being
# added to the bot.
ACTIVITY_LABELS = (
    ("command.total", "commands"),
    ("page.published", "pages published"),
    ("index.rebuilt", "indexes rebuilt"),
    ("telegraph.call", "telegraph calls"),
    ("telegraph.failed", "telegraph errors"),
    ("error", "errors"),
)


def activity_section(counts, suppress, restarted, exporting):
    """
    The last completed hour.

    Not the current 30-minute block, on purpose. A count that advances
    every half hour hands anyone who polls this page a 30-minute-resolution
    activity log, and on a quiet bot most windows hold zero or one event -
    a delta of 1 correlates trivially against the page that just appeared
    on somebody's Telegraph account. An hourly figure that does not move
    between rollovers gives that observer nothing.
    """

    if not exporting:
        return (
            "The bot is not exporting counters, so activity is unknown "
            "for this period. This is not the same as no activity."
        )

    lines = [
        leader(label, suppress(counts.get(key, 0)))
        for key, label in ACTIVITY_LABELS
    ]

    if restarted:
        lines.append("")
        lines.append("The bot restarted during this hour. Counters live in")
        lines.append("tmpfs and reset with it, so these are a partial count.")

    return block(lines)


PRIVACY = (
    "These numbers are counts and nothing else. No identifier of any kind "
    "reaches them: not a Telegraph token, a chat, a user, a title, a path "
    "or a category. Counts under 5 are shown as a bound rather than a "
    "number, and activity advances once an hour, so that no short window "
    "can be singled out. The counters live in memory that is destroyed "
    "when the service stops."
)


def render(now, machine, summary, status, counts, sources,
           memory_total=None, disk_used=None, disk_total=None,
           uptime=None, battery_status=None, restarted=False,
           exporting=True, activity_hour=None, suppress=str,
           sample_count=0):
    """
    The whole page as (kind, text) sections.

    `now` and `activity_hour` arrive as arguments rather than being read
    from a clock so that this function is pure and the tests can pin a
    time. Everything user-visible is decided here.
    """

    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    title = machine.get("machine") or machine.get("arch") or "server"

    resolved = ", ".join(
        f"{name}={'yes' if path else 'no'}"
        for name, path in sorted(sources.items())
    )

    return [
        ("aside", "server, operations"),

        ("h3", title),
        ("pre", machine_section(machine)),

        ("h3", f"Machine - 30 minutes to {stamp}"),
        ("pre", health_section(
            summary, memory_total, disk_used, disk_total,
            uptime, battery_status,
        )),
        ("p", (
            f"Mean of {sample_count} samples taken two minutes apart. "
            f"Sensors: {resolved}."
        )),

        ("h3", "telepatch-bot.service"),
        ("pre", service_section(status)),

        ("h3", f"Activity - hour ending {activity_hour or 'unknown'}"),
        ("pre", activity_section(counts, suppress, restarted, exporting)),

        ("p", PRIVACY),

        ("p", (
            "Published by telepatch-observer every 30 minutes from the "
            "machine it describes."
        )),
    ]


# ------------------------------------------------------------ projections


def to_nodes(sections):
    """Telegraph's content format: a list of node dicts."""

    nodes = []

    for kind, text in sections:

        if not text:
            continue

        nodes.append({"tag": kind, "children": [text]})

    return nodes


def to_text(sections):
    """
    The same page for the local log. Headings get underlined so the file
    is readable in a pager, and pre blocks pass through unchanged - they
    were already monospace-aligned for exactly this.
    """

    out = []

    for kind, text in sections:

        if not text:
            continue

        if kind in ("h3", "h4"):
            out.append(f"\n{text}\n{'-' * len(text)}")

        else:
            out.append(text)

    return "\n".join(out)
