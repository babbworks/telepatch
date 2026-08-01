"""
The loop.

One process, one thread, two deadlines. No asyncio: the bot needs an event
loop because python-telegram-bot is async all the way down, but this
service does nothing concurrent - it reads some files, does some
arithmetic, and makes one HTTP call every thirty minutes. A sleep loop is
the honest shape for that, and on a 1.5GHz G4 the cheapest.

    sample   every 120s   read sensors  -> ring buffer + samples.log
    publish  every 1800s  aggregate     -> editPage + observer.log

Activity runs on a third, slower boundary: the top of each hour. See
render.activity_section for why that is not the same as the publish tick.
"""

import collections
import datetime
import logging
import os
import signal
import sys
import time

from dotenv import load_dotenv

from . import aggregate, counters, logfile, probe, publish, render, service

# The unit sets EnvironmentFile, but loading here too means `python -m
# observer` behaves the same way when run by hand for a smoke test.
load_dotenv("/opt/telepatch/.env")
load_dotenv()

log = logging.getLogger("observer")


def config(name, default="", required=False):
    """
    Same contract as bot.py's config(): fail at boot, not at first use.

    An empty environment variable counts as unset. EnvironmentFile makes
    that easy to do by accident - a commented-out line edited down to
    `OBSERVER_SAMPLE_SECONDS=` would otherwise reach int() as "" and take
    the service down on a typo.
    """

    value = os.environ.get(name) or default

    if required and not value:
        sys.exit(f"{name} is not set. See .env.example.")

    return value


TOKEN = config("OBSERVER_TOKEN", required=True)
PAGE_PATH = config("OBSERVER_PAGE_PATH", required=True)

SAMPLE_SECONDS = int(config("OBSERVER_SAMPLE_SECONDS", "120"))
PUBLISH_SECONDS = int(config("OBSERVER_PUBLISH_SECONDS", "1800"))

LOG_PATH = config("OBSERVER_LOG", "/var/log/telepatch/observer.log")
SAMPLE_LOG = logfile.sample_path(LOG_PATH)

UNIT = config("OBSERVER_UNIT", "telepatch-bot.service")
COUNTERS = config("OBSERVER_COUNTERS", counters.DEFAULT_PATH)

PAGE_TITLE = config("OBSERVER_PAGE_TITLE", "telepatch-server-performance")

LOG_LEVEL = config("OBSERVER_LOG_LEVEL", "INFO").upper()

# 15 samples at 120s covers exactly one 1800s publish window. Kept as a
# bounded deque so a publish that fails cannot grow this without limit -
# the block is dropped, not queued, because a status page reporting a
# half-hour that ended two hours ago is worse than one that skips it.
BUFFER = collections.deque(maxlen=64)


def notify(state):
    """
    sd_notify by hand, lifted from bot.py:3745. One datagram to a unix
    socket, and a no-op anywhere systemd is not watching - so running this
    by hand on a laptop behaves exactly the same.
    """

    address = os.environ.get("NOTIFY_SOCKET")

    if not address:
        return

    try:
        import socket

        if address.startswith("@"):
            address = "\0" + address[1:]

        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(state.encode())

    except Exception as problem:
        log.debug("notify.failed state=%s error=%s", state, problem)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class Observer:
    """
    Holds the three things that have to survive between ticks: the sample
    buffer, the /proc/stat snapshot that CPU percentage is a delta of, and
    the hourly counter bookkeeping.
    """

    def __init__(self):
        self.machine = probe.machine()
        self.previous_cpu = None
        self.sources = {}

        # Hourly activity. hour_start is the counter snapshot taken at the
        # top of the current hour; completed is the last whole hour, which
        # is the only thing that ever reaches the page.
        self.hour = utc_now().replace(minute=0, second=0, microsecond=0)
        self.hour_start = counters.events(counters.read(COUNTERS))
        self.completed = None

    # ------------------------------------------------------------ sample

    def sample(self):
        reading, cpu_snapshot, sources = probe.sample(self.previous_cpu)

        self.previous_cpu = cpu_snapshot
        self.sources = sources

        BUFFER.append(reading)

        try:
            logfile.sampled(SAMPLE_LOG, utc_now().isoformat(timespec="seconds"), reading)

        except OSError as problem:
            log.warning("log.sample.failed error=%s", problem)

        self.roll_hour()

    def roll_hour(self):
        """
        Close the hour if the clock has passed it.

        Checked on the sample tick rather than the publish tick so the
        boundary lands within two minutes of the hour regardless of where
        the publish cadence happens to fall.
        """

        now_hour = utc_now().replace(minute=0, second=0, microsecond=0)

        if now_hour <= self.hour:
            return

        snapshot = counters.events(counters.read(COUNTERS))
        delta, restarted = aggregate.counter_delta(self.hour_start, snapshot)

        self.completed = {
            "label": self.hour.strftime("%H:%M UTC"),
            "counts": delta,
            "restarted": restarted,
        }

        self.hour = now_hour
        self.hour_start = snapshot

        log.info("hour.closed at=%s restarted=%s", self.completed["label"], restarted)

    # ----------------------------------------------------------- publish

    def page(self):
        """The rendered sections for the block currently in the buffer."""

        samples = list(BUFFER)
        summary = aggregate.summarise(samples)

        status = service.state(
            UNIT,
            uptime_seconds=aggregate.latest(samples, "uptime"),
        )

        completed = self.completed or {}

        return render.render(
            now=utc_now(),
            machine=self.machine,
            summary=summary,
            status=status,
            counts=completed.get("counts", {}),
            sources=self.sources,
            memory_total=aggregate.latest(samples, "memory_total"),
            disk_used=aggregate.latest(samples, "disk_used"),
            disk_total=aggregate.latest(samples, "disk_total"),
            uptime=aggregate.latest(samples, "uptime"),
            battery_status=aggregate.latest(samples, "battery_status"),
            restarted=completed.get("restarted", False),
            # No completed hour yet means the service started less than an
            # hour ago. Saying "collecting" is honest; showing zeros would
            # claim an idle hour we never observed.
            exporting=bool(self.completed) and counters.available(COUNTERS),
            activity_hour=completed.get("label"),
            suppress=aggregate.suppressed,
            sample_count=len(samples),
        )

    def publish(self):
        if not BUFFER:
            log.warning("publish.skipped reason=no-samples")
            return

        sections = self.page()

        try:
            publish.edit(
                TOKEN,
                PAGE_PATH,
                PAGE_TITLE,
                render.to_nodes(sections),
                author_name=AUTHOR_NAME,
                author_url=AUTHOR_URL,
            )
            log.info("published samples=%s path=%s", len(BUFFER), PAGE_PATH)

        except Exception as problem:
            # A failed publish must not lose the local copy. The log is the
            # record; Telegraph is the copy of it that happens to be public.
            log.warning("publish.failed error=%s", problem)

        try:
            logfile.published(
                LOG_PATH,
                utc_now().isoformat(timespec="seconds"),
                render.to_text(sections),
            )

        except OSError as problem:
            log.warning("log.publish.failed error=%s", problem)

        BUFFER.clear()


AUTHOR_NAME = None
AUTHOR_URL = None


def main():
    global AUTHOR_NAME, AUTHOR_URL

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Fail loudly at boot on a bad token rather than silently at the first
    # publish half an hour later, into a log nobody is reading. This also
    # gets the byline, which every editPage has to send explicitly or the
    # page loses it (bot.py:484).
    try:
        info = publish.account(TOKEN)
        AUTHOR_NAME = info.get("author_name")
        AUTHOR_URL = info.get("author_url")

        log.info(
            "observer.account short_name=%s author=%s pages=%s",
            info.get("short_name"), AUTHOR_NAME, info.get("page_count"),
        )

    except Exception as problem:
        sys.exit(f"Telegraph rejected OBSERVER_TOKEN: {problem}")

    observer = Observer()

    log.info(
        "observer.started machine=%s sample=%ss publish=%ss unit=%s page=%s",
        observer.machine.get("machine") or observer.machine.get("arch"),
        SAMPLE_SECONDS, PUBLISH_SECONDS, UNIT, PAGE_PATH,
    )

    running = {"yes": True}

    def stop(signum, _frame):
        log.info("observer.stopping signal=%s", signum)
        running["yes"] = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    notify("READY=1")

    window = int(os.environ.get("WATCHDOG_USEC", 0)) / 1_000_000
    watchdog_every = window / 2 if window else None

    now = time.monotonic()
    sample_due = now
    # First publish lands just after the first sample rather than half an
    # hour in. On a machine that is awkward to reach, seeing the page
    # update within a few minutes of `systemctl start` is worth one extra
    # edit a day.
    publish_due = now + SAMPLE_SECONDS + 5
    watchdog_due = now

    while running["yes"]:
        now = time.monotonic()

        if now >= sample_due:
            try:
                observer.sample()

            except Exception:
                log.exception("sample.failed")

            sample_due = now + SAMPLE_SECONDS

        if now >= publish_due:
            try:
                observer.publish()

            except Exception:
                log.exception("publish.failed")

            publish_due = now + PUBLISH_SECONDS

        if watchdog_every and now >= watchdog_due:
            notify("WATCHDOG=1")
            watchdog_due = now + watchdog_every

        # Wake for whichever deadline is nearest, but never sleep so long
        # that SIGTERM waits on it - systemd's TimeoutStopSec is the
        # ceiling and a five second granularity sits comfortably inside it.
        deadlines = [sample_due, publish_due]

        if watchdog_every:
            deadlines.append(watchdog_due)

        time.sleep(max(0.5, min(min(deadlines) - time.monotonic(), 5.0)))

    notify("STOPPING=1")
    log.info("observer.stopped")


if __name__ == "__main__":
    main()
