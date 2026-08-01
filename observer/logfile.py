"""
The local copy.

Two files, because they answer different questions:

  observer.log  - exactly what was published, every 30 minutes
  samples.log   - every 2-minute reading, one JSON object per line

The page carries 30-minute means; samples.log is the only place the
underlying readings exist. That makes it the more detailed artifact, and
therefore the more sensitive one - it stays on the machine. See the privacy
section of the design spec.

Both are trimmed by line count rather than rotated by logrotate. Fewer
moving parts, no config file outside this repo, and nothing to forget to
install on a machine that is awkward to reach. At 48 published blocks and
720 samples a day the defaults below hold roughly three weeks and one week
respectively.
"""

import json
import os

PUBLISHED_LINES = 5_000
SAMPLE_LINES = 20_000


def append(path, text, keep=PUBLISHED_LINES):
    """
    One entry, then trim if the file has outgrown its allowance.

    Failure to write is logged by the caller and otherwise ignored: losing
    the local copy is bad, but taking down the service that publishes the
    public page because a disk filled up is worse.
    """

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "a") as handle:
        handle.write(text.rstrip("\n") + "\n")

    trim(path, keep)


def trim(path, keep):
    """
    Keep the last `keep` lines.

    Checked cheaply first - counting lines on every append would mean
    reading the whole file 720 times a day. Only when the file is over its
    allowance by a margin does it get rewritten, so the expensive path runs
    rarely and in a batch.

    The rewrite goes through a temporary file and a rename so that a crash
    mid-trim leaves either the old log or the new one, never a half file.
    """

    try:
        with open(path, "r", errors="replace") as handle:
            lines = handle.readlines()

    except OSError:
        return

    if len(lines) <= keep * 1.1:
        return

    temporary = path + ".tmp"

    with open(temporary, "w") as handle:
        handle.writelines(lines[-keep:])

    os.replace(temporary, path)


def published(path, when, text):
    """
    Mirror a published block, framed so the file can be read by eye and
    split by machine. The marker line is what a future reader greps for.
    """

    append(path, f"\n===== published {when} =====\n{text}", PUBLISHED_LINES)


def sampled(path, when, reading):
    """
    One raw sample as JSON, with the timestamp first so that sorting the
    file by line is the same as sorting it by time.

    default=str keeps a surprise value - a Decimal, an unexpected string
    from a sensor - from raising inside the sample tick.
    """

    record = {"at": when}
    record.update(reading)

    append(path, json.dumps(record, default=str, sort_keys=True), SAMPLE_LINES)


def sample_path(published_path):
    """
    samples.log beside observer.log, whatever observer.log was configured
    to be. One env var instead of two, and they cannot end up in different
    directories by accident.
    """

    directory = os.path.dirname(published_path) or "."

    return os.path.join(directory, "samples.log")
