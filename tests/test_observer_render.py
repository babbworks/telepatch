"""
The page, and the property that keeps the local log honest.

render() returns (kind, text) sections; to_nodes() and to_text() are two
projections of that one list. The test that matters most here is that they
stay projections - a section cannot reach the page without also reaching
the log.
"""

import datetime

from observer import aggregate, render

NOW = datetime.datetime(2026, 8, 1, 14, 30, tzinfo=datetime.timezone.utc)

MACHINE = {
    "cpu": "7447A, altivec supported",
    "clock": "1666.666000MHz",
    "machine": "PowerBook5,6",
    "motherboard": "PowerBook5,6 MacRISC3 Power Macintosh",
    "detected": '287 (PowerBook G4 15")',
    "cache": "512K unified",
    "generation": "NewWorld",
    "kernel": "6.1.0-powerpc",
    "arch": "ppc",
}

STATUS = {
    "unit": "telepatch-bot.service",
    "active": "active",
    "sub": "running",
    "restarts": 2,
    "memory": 96 * 1024 * 1024,
    "exit_status": 0,
    "active_for": 275_000,
    "reachable": True,
}

SUMMARY = {
    "load": {"mean": 0.41, "min": 0.22, "max": 0.88, "n": 15},
    "temperature": {"mean": 47.2, "min": 44.1, "max": 51.0, "n": 15},
}


def page(**overrides):
    arguments = dict(
        now=NOW,
        machine=MACHINE,
        summary=SUMMARY,
        status=STATUS,
        history=[{
            "label": "14:00 UTC",
            "counts": {"command.total": 412, "page.published": 2},
            "restarted": False,
        }],
        sources={"temperature": "/sys/x", "fan_rpm": None},
        memory_total=1024 ** 3,
        uptime=1_040_000,
        battery_status="AC",
        exporting=True,
        suppress=aggregate.suppressed,
        sample_count=15,
    )
    arguments.update(overrides)

    return render.render(**arguments)


# ------------------------------------------------------------ projections


def test_log_and_page_carry_the_same_sections():
    """
    The property the local log depends on. Two renderers would agree on the
    day they were written and drift by the second change; two projections
    of one list cannot.
    """

    sections = page()

    nodes = render.to_nodes(sections)
    text = render.to_text(sections)

    for _, content in sections:
        if content:
            # Headings are underlined in text and wrapped in a tag in
            # nodes, but the content itself appears verbatim in both.
            assert content in text

    assert len(nodes) == len([s for s in sections if s[1]])


def test_only_telegraph_tags_are_emitted():
    """
    Telegraph silently drops unknown tags rather than erroring, so an
    invalid tag would show up as a missing section on a live page.
    Allowed tags are listed at bot.py:224.
    """

    allowed = {"aside", "p", "h3", "h4", "pre", "blockquote", "hr", "ul", "li"}

    for node in render.to_nodes(page()):
        assert node["tag"] in allowed


def test_empty_sections_are_dropped():
    sections = [("p", ""), ("p", None), ("p", "kept")]

    assert render.to_nodes(sections) == [{"tag": "p", "children": ["kept"]}]


# --------------------------------------------------------------- content


def test_the_heading_is_the_machine():
    assert page()[1] == ("h3", "PowerBook5,6")


def test_powerpc_identity_reaches_the_page():
    text = render.to_text(page())

    assert "PowerBook5,6 MacRISC3 Power Macintosh" in text
    assert '287 (PowerBook G4 15")' in text


def test_a_missing_sensor_has_no_line():
    text = render.to_text(page())

    assert "temperature" in text
    assert "\nfan " not in text


def test_sensor_resolution_is_reported():
    """The first look at the published page is also the diagnostic."""

    text = render.to_text(page())

    assert "temperature=yes" in text
    assert "fan_rpm=no" in text


def test_unreachable_systemd_says_so():
    """
    An observer that cannot see the bot must not read as an observer
    reporting a healthy bot.
    """

    text = render.to_text(page(status={"reachable": False}))

    assert "systemd did not answer" in text


def test_activity_absent_is_not_activity_zero():
    text = render.to_text(page(exporting=False))

    assert "not the same as no activity" in text
    assert "412" not in text


def test_small_activity_counts_are_suppressed():
    text = render.to_text(page())

    assert "412" in text            # commands, above the threshold
    assert "<5" in text             # pages published, below it


def test_multiple_hours_render_side_by_side():
    text = render.to_text(page(history=[
        {"label": "12:00 UTC", "counts": {"command.total": 3}, "restarted": False},
        {"label": "13:00 UTC", "counts": {"command.total": 412}, "restarted": False},
    ]))

    assert "last 2 hours, ending 13:00 UTC" in text
    assert "<5, 412" in text


def test_each_hour_is_suppressed_independently():
    """
    A quiet hour next to a busy one must not let the busy one's count carry
    over - each column passes through suppress() on its own, so a 9 next to
    a 1 still reads as 9 next to <5, not as a two-hour total.
    """

    text = render.to_text(page(history=[
        {"label": "12:00 UTC", "counts": {"page.published": 1}, "restarted": False},
        {"label": "13:00 UTC", "counts": {"page.published": 9}, "restarted": False},
    ]))

    assert "<5, 9" in text


def test_no_completed_hour_yet():
    """Fewer than one full hour since start - the original single-column
    wording, not an empty trend."""

    text = render.to_text(page(history=[]))

    assert "Activity - hour ending unknown" in text
    assert "no hour has completed yet" in text


def test_a_single_hour_reads_exactly_as_before():
    """One completed hour must not gain a 'last 1 hours' plural."""

    text = render.to_text(page())

    assert "Activity - hour ending 14:00 UTC" in text
    assert "last 1 hours" not in text


def test_a_restart_is_disclosed():
    """A partial count published as a whole one would be a quiet lie."""

    text = render.to_text(page(history=[{
        "label": "14:00 UTC",
        "counts": {"command.total": 412, "page.published": 2},
        "restarted": True,
    }]))

    assert "partial count" in text


def test_privacy_note_is_always_present():
    assert "No identifier of any kind" in render.to_text(page())


# -------------------------------------------------------------- formatting


def test_gauge_shows_its_range():
    """
    A mean of 0.41 could be a machine idling steadily or one alternating
    between asleep and on fire. The range is what makes the mean readable.
    """

    assert render.gauge(SUMMARY, "load", digits=2) == "0.41  (0.22-0.88)"


def test_degenerate_range_is_dropped():
    flat = {"load": {"mean": 1.0, "min": 1.0, "max": 1.0, "n": 3}}

    assert render.gauge(flat, "load", digits=2) == "1.00"


def test_missing_gauge_is_none():
    assert render.gauge({}, "load") is None


def test_human_bytes():
    assert render.human_bytes(1024 ** 3) == "1.0G"
    assert render.human_bytes(407 * 1024 ** 2) == "407M"
    assert render.human_bytes(None) is None


def test_human_seconds_stops_at_two_units():
    assert render.human_seconds(1_040_000) == "12d 0h"
    assert render.human_seconds(3700) == "1h 1m"
    assert render.human_seconds(45) == "45s"
    assert render.human_seconds(None) is None


def test_leader_omits_a_missing_value():
    assert render.leader("fan", None) is None
    assert render.leader("fan", "2900 rpm").startswith("fan ...")


def test_a_unit_that_was_never_installed_says_so():
    """
    systemd reports inactive/dead for a unit that does not exist, which is
    indistinguishable from a bot that crashed unless LoadState is read.
    Those deserve very different reactions.
    """

    text = render.to_text(page(status={"reachable": True, "loaded": "not-found",
                                       "unit": "telepatch-bot.service"}))

    assert "is not installed on this machine" in text
    assert "inactive" not in text


def test_sampling_interval_is_not_hardcoded():
    """
    The page used to claim "two minutes apart" as a constant while the real
    interval was OBSERVER_SAMPLE_SECONDS. Anything but the default made it
    state a falsehood about its own data.
    """

    assert "30 seconds apart" in render.to_text(page(sample_seconds=30))
    assert "two minutes apart" in render.to_text(page(sample_seconds=120))
    assert "five minutes apart" in render.to_text(page(sample_seconds=300))


def test_interval_phrasing():
    assert render.human_interval(60) == "one minute"
    assert render.human_interval(120) == "two minutes"
    assert render.human_interval(1800) == "30 minutes"
    assert render.human_interval(45) == "45 seconds"
    assert render.human_interval(None) == "an unknown interval"
