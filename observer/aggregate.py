"""
Fifteen samples in, one block out.

Pure functions only - no clock, no filesystem, no network. This is where
the arithmetic that reaches the public page is decided, so it is the part
most worth testing, and it is testable with plain lists of dicts.

Two rules, chosen by metric type:

  gauges   (load, temperature, fan, memory, cpu%)  -> mean, min, max
  counters (commands, publishes, API calls)        -> sum over the period

Averaging a counter is meaningless - "an average of 3 commands per sample"
answers no question anyone asked. The distinction is structural rather than
stylistic, which is why the two live in separate functions with separate
call sites rather than one clever dispatcher.
"""

# Every key from probe.sample() that is a level rather than a count.
# battery_status is a string and uptime is monotonic, so neither is here.
GAUGES = (
    "load",
    "cpu_percent",
    "memory_used",
    "swap_used",
    "temperature",
    "fan_rpm",
    "battery_percent",
)


def summarise(samples, keys=GAUGES):
    """
    Mean, min and max per gauge across the block.

    None readings are skipped rather than counted as zero - a thermistor
    that answered on 12 of 15 samples should report the mean of those 12,
    not a mean dragged toward zero by three absences. A gauge that answered
    on none of them is absent from the result entirely, and the renderer
    leaves its line off the page.
    """

    block = {}

    for key in keys:
        values = [
            sample[key]
            for sample in samples
            if isinstance(sample.get(key), (int, float))
        ]

        if not values:
            continue

        block[key] = {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "n": len(values),
        }

    return block


def latest(samples, key):
    """
    The most recent non-None reading of something that should not be
    averaged - uptime, battery status, total memory. Walks backwards
    because the freshest answer is the one worth showing.
    """

    for sample in reversed(samples):
        value = sample.get(key)

        if value is not None:
            return value

    return None


def counter_delta(start, end):
    """
    What happened between two counter snapshots.

    Counters live in tmpfs and reset to zero when the bot restarts, which
    would otherwise show up as a large negative delta. A key whose value
    went *down* can only mean a reset, so the post-reset value is the whole
    of what we can honestly attribute to this period - everything before the
    restart is unrecoverable and is not guessed at.

    Returns (delta, restarted) so the page can say so rather than quietly
    publishing an undercount.
    """

    start = start or {}
    end = end or {}

    restarted = any(
        end.get(key, 0) < value
        for key, value in start.items()
    )

    delta = {}

    for key, value in end.items():
        previous = start.get(key, 0)
        delta[key] = value if value < previous else value - previous

    return delta, restarted


# Below this, a count is a person rather than a statistic. See the privacy
# section of docs/superpowers/specs/2026-08-01-observer-design.md - on a
# quiet bot an hour bucket containing 1 publish is trivially correlated
# against the page that appeared on someone's Telegraph account.
SUPPRESS_BELOW = 5


def suppressed(count, threshold=SUPPRESS_BELOW):
    """
    A small count rendered as a bound rather than a number.

    Zero is safe and stays zero - "nothing happened" identifies nobody, and
    showing "<5" for an idle hour would be both less informative and less
    honest than showing "0".
    """

    if count is None:
        return None

    if count == 0:
        return "0"

    if count < threshold:
        return f"<{threshold}"

    return f"{count:,}"
