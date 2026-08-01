"""
The arithmetic that reaches a public page.

Two rules that must not be confused: gauges are averaged, counters are
summed. And one rule that protects people: a small count is published as a
bound rather than a number.
"""

from observer import aggregate


def samples(*loads):
    return [{"load": value} for value in loads]


def test_mean_min_max():
    block = aggregate.summarise(samples(1.0, 2.0, 3.0), keys=("load",))

    assert block["load"]["mean"] == 2.0
    assert block["load"]["min"] == 1.0
    assert block["load"]["max"] == 3.0
    assert block["load"]["n"] == 3


def test_absent_readings_are_skipped_not_zeroed():
    """
    A thermistor that answered on two of three samples should report the
    mean of those two. Counting the absence as zero would drag the mean
    toward a temperature the machine never was.
    """

    block = aggregate.summarise(
        [{"temperature": 40.0}, {"temperature": None}, {"temperature": 50.0}],
        keys=("temperature",),
    )

    assert block["temperature"]["mean"] == 45.0
    assert block["temperature"]["n"] == 2


def test_a_sensor_that_never_answered_is_absent():
    """Not zero, not None - absent, so the renderer omits the line."""

    block = aggregate.summarise([{"fan_rpm": None}] * 5, keys=("fan_rpm",))

    assert "fan_rpm" not in block


def test_empty_block():
    assert aggregate.summarise([]) == {}


def test_latest_walks_backwards_past_gaps():
    found = aggregate.latest(
        [{"uptime": 1}, {"uptime": 2}, {"uptime": None}], "uptime"
    )

    assert found == 2


def test_counter_delta_is_the_difference():
    delta, restarted = aggregate.counter_delta(
        {"command.total": 10}, {"command.total": 25}
    )

    assert delta["command.total"] == 15
    assert restarted is False


def test_counter_delta_detects_a_restart():
    """
    Counters live in tmpfs and reset to zero with the bot. A value that
    went down can only mean a restart, and the post-reset number is the
    whole of what can honestly be attributed to this hour - what came
    before is unrecoverable and is not guessed at.
    """

    delta, restarted = aggregate.counter_delta(
        {"command.total": 100}, {"command.total": 3}
    )

    assert restarted is True
    assert delta["command.total"] == 3


def test_counter_delta_handles_a_new_key():
    """A counter that did not exist at the start of the hour starts at 0."""

    delta, _ = aggregate.counter_delta({}, {"page.published": 4})

    assert delta["page.published"] == 4


def test_small_counts_are_suppressed():
    """
    On a quiet bot an hour containing one publish is one identifiable
    person, correlated against the page that just appeared on their
    Telegraph account.
    """

    assert aggregate.suppressed(1) == "<5"
    assert aggregate.suppressed(4) == "<5"
    assert aggregate.suppressed(5) == "5"


def test_zero_is_not_suppressed():
    """
    "Nothing happened" identifies nobody, and showing "<5" for an idle hour
    would be both less informative and less honest than showing "0".
    """

    assert aggregate.suppressed(0) == "0"


def test_large_counts_are_grouped():
    assert aggregate.suppressed(1204) == "1,204"


def test_unknown_stays_unknown():
    assert aggregate.suppressed(None) is None
