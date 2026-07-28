"""
The incremental scan. The whole idea rests on one claim: what the index
recorded is exactly what a fresh read would compute. If that is ever
false, a rebuild quietly rewrites people's entries.
"""

import json


def account(article, primary):
    pages = [
        {"path": "primary-1", "title": "Main", "url": "https://telegra.ph/primary-1"},
        {"path": "One-07-28", "title": "One", "url": "/One-07-28"},
        {"path": "Two-07-28", "title": "Two", "url": "/Two-07-28"},
        {"path": "New-07-28", "title": "New", "url": "/New-07-28"},
    ]
    content = {"primary-1": primary, "One-07-28": article,
               "Two-07-28": article, "New-07-28": article}
    return pages, content


def test_read_index_entries_recovers_everything_written(bot, primary):
    found = bot.read_index_entries(primary)

    assert set(found) == {"One-07-28", "Two-07-28"}
    assert found["One-07-28"] == {
        "title": "One",
        "url": "/One-07-28",
        "date": "2026-07-28",
        "minutes": 2,
        "categories": ["tin"],
        "excerpt": "The first.",
    }
    assert found["Two-07-28"]["categories"] == ["tin", "trade"]
    assert found["Two-07-28"]["minutes"] == 3


def test_entries_without_a_reading_time_are_read_back(bot, curated):
    """A /link entry claims no minutes; that must not become minutes=0 lost."""
    found = bot.read_index_entries(curated)

    assert found["Filed-07-28"]["minutes"] == 1
    assert found["Also-Filed-07-28"]["minutes"] == 0
    # A GitHub entry is not an account page and has no path to key on.
    assert len(found) == 2


def test_dates_still_come_back(bot, primary):
    assert bot.read_index_dates(primary) == {
        "One-07-28": "2026-07-28", "Two-07-28": "2026-07-27",
    }


def test_reusing_the_record_matches_reading_every_page(bot, primary, article):
    """
    The claim the whole optimisation rests on, tested as a round trip:
    build an index by reading everything, read the record back out of it,
    then rebuild with those pages skipped. The two must be identical, or a
    rebuild silently rewrites people's entries.
    """
    pages, content = account(article, primary)
    full = [(p, content[p["path"]]) for p in pages]

    # Written by reading every page, which is what a first run does.
    _, first = bot.build_index(full, "primary-1", {}, [], [], "separate", [])

    recorded = bot.read_index_entries(first)
    dates = bot.read_index_dates(first)

    # Rebuilt trusting that record, which is what every run after does.
    lazy = [
        (p, None if p["path"] in recorded else content[p["path"]])
        for p in pages
    ]
    _, second = bot.build_index(
        lazy, "primary-1", dates, [], [], "separate", [], None, recorded
    )

    assert json.dumps(second) == json.dumps(first)


def test_a_page_the_index_has_never_seen_is_still_read(bot, primary, article):
    pages, content = account(article, primary)
    recorded = bot.read_index_entries(primary)

    lazy = [(p, None if p["path"] in recorded else content[p["path"]]) for p in pages]
    entries, _ = bot.build_index(
        lazy, "primary-1", {}, [], [], "separate", [], None, recorded
    )

    listed = {e["path"] for e in entries}
    assert listed == {"One-07-28", "Two-07-28", "New-07-28"}

    new = next(e for e in entries if e["path"] == "New-07-28")
    assert new["minutes"] > 0 and new["excerpt"]


def test_the_index_itself_is_never_skipped(bot, primary):
    """
    Skipping is only safe because an index is never listed as an entry. If
    that ever stopped being true, /site would stop finding its own page.
    """
    assert "primary-1" not in bot.read_index_entries(primary)
    assert bot.is_index(None) is False
