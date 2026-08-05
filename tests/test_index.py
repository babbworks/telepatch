"""
The index is the only durable record Telepatch has, and every write to it
replaces it wholesale. These are the tests that stop a change eating one.
"""

import copy
import json

from conftest import p, li


# --------------------------------------------------------- the big one

def test_rebuild_is_byte_identical_when_nothing_changed(bot, primary):
    """
    Read, split, reassemble, write. If this ever differs, some command is
    silently dropping part of somebody's page.
    """
    before = json.dumps(primary)

    head, middle, foot = bot.split_master(primary)
    after = json.dumps(head + middle + foot + [bot.kept_marker(primary)])

    assert after == before


def test_rebuild_is_byte_identical_for_a_curated_collection(bot, curated):
    before = json.dumps(curated)

    head, middle, foot = bot.split_master(curated)
    after = json.dumps(head + middle + foot + [bot.kept_marker(curated)])

    assert after == before


def test_split_master_does_not_mutate_its_input(bot, primary):
    original = copy.deepcopy(primary)
    bot.split_master(primary)
    assert primary == original


# ------------------------------------------------------------- markers

def test_marker_fields_survive_a_rewrite(bot, primary, curated, legacy):
    assert "byline=separate" in bot.node_text(bot.kept_marker(primary))

    kept = bot.node_text(bot.kept_marker(curated))
    assert "collection=extra" in kept
    assert "byline=linked" in kept

    # A legacy index has no fields at all and must not gain collection=.
    assert "collection=" not in bot.node_text(bot.kept_marker(legacy))


def test_changing_the_byline_keeps_the_collection_field(bot, curated):
    """The bug that would have demoted a collection to a primary."""
    kept = bot.node_text(bot.kept_marker(curated, "plain"))
    assert "byline=plain" in kept
    assert "collection=extra" in kept


def test_rewriting_a_retired_index_does_not_revive_it(bot, retired, hand_retired):
    """
    split_master strips both marks, so a marker rebuilt from the byline
    alone would bring the page back into service. Reachable through an old
    Site message, whose carrier still points at it.
    """
    for content in (retired, hand_retired):
        assert bot.node_text(bot.kept_marker(content)) == bot.RETIRED_MARK
        assert bot.node_text(bot.kept_marker(content, "plain")) == bot.RETIRED_MARK

        head, middle, foot = bot.split_master(content)
        rebuilt = head + middle + foot + [bot.kept_marker(content)]

        assert bot.is_retired(rebuilt)
        assert bot.list_indexes([({"path": "x", "title": "x", "url": "u"}, rebuilt)]) == []


def test_classification(bot, primary, curated, retired, legacy, article):
    cases = [
        (primary, True, False),
        (curated, True, True),
        (retired, True, False),
        (legacy, True, False),
        (article, False, False),
    ]
    for content, index, extra in cases:
        assert bot.is_index(content) is index
        assert bot.is_extra(content) is extra


def test_masthead_and_footer_come_back(bot, primary):
    assert bot.node_text(bot.read_masthead(primary)[0]).startswith("An introduction")
    assert bot.node_text(bot.read_footer(primary)[0]).startswith("A footer")
    assert bot.read_byline(primary) == "separate"


# --------------------------------------------------------- collections

def scanned_account(primary, curated, retired, article):
    art = lambda name: (
        {"path": name, "title": name, "url": "https://telegra.ph/" + name}, article
    )
    return [
        ({"path": "primary-1", "title": "Main", "url": "u"}, primary),
        ({"path": "coll-1", "title": "Reading", "url": "u"}, curated),
        ({"path": "old-1", "title": "Gone", "url": "u"}, retired),
        art("Filed-07-28"),
        art("Also-Filed-07-28"),
        art("Stranded-07-28"),
        art("Loose-07-28"),
    ]


def test_pick_master_ignores_curated_and_retired(bot, primary, curated, retired, article):
    found, _ = bot.pick_master(scanned_account(primary, curated, retired, article))
    assert found == "primary-1"


def test_list_indexes_puts_the_primary_first(bot, primary, curated, retired, article):
    found = bot.list_indexes(scanned_account(primary, curated, retired, article))
    assert [i["path"] for i in found] == ["primary-1", "coll-1"]
    assert [i["extra"] for i in found] == [False, True]


def test_claimed_paths(bot, primary, curated, retired, article):
    filed = bot.claimed_paths(scanned_account(primary, curated, retired, article))

    assert filed == {"Filed-07-28", "Also-Filed-07-28"}
    # A GitHub entry is not an account page and must never be claimed.
    assert not any("telepatch" == f for f in filed)
    # A retired collection claims nothing, or its pages would be stranded.
    assert "Stranded-07-28" not in filed


def test_a_hand_retired_collection_claims_nothing(bot, hand_retired, article):
    """
    Retiring by hand leaves the original marker in place beside the
    retirement line. Anything that only checks for the first line still
    sees a live collection - and would strand its pages outside every
    index at once.
    """
    scanned = [
        ({"path": "coll-1", "title": "Reading", "url": "u"}, hand_retired),
        ({"path": "Hand-Stranded-07-28", "title": "x", "url": "u"}, article),
    ]

    assert bot.claimed_paths(scanned) == set()
    assert bot.list_indexes(scanned) == []
    assert bot.pick_master(scanned) == (None, None)

    listed, _ = bot.build_index(scanned, None, {}, [], [], "linked", [],
                                bot.claimed_paths(scanned))
    assert [e["path"] for e in listed] == ["Hand-Stranded-07-28"]


def test_filing_removes_a_page_from_the_primary(bot, primary, curated, retired, article):
    scanned = scanned_account(primary, curated, retired, article)
    filed = bot.claimed_paths(scanned)

    with_filter, _ = bot.build_index(scanned, "primary-1", {}, [], [], "linked", [], filed)
    without, _ = bot.build_index(scanned, "primary-1", {}, [], [], "linked", [])

    assert [e["path"] for e in with_filter] == ["Stranded-07-28", "Loose-07-28"]

    # Rollback: dropping the filter restores exactly the old behaviour.
    assert len(without) == 4


def test_build_index_is_idempotent(bot, primary, curated, retired, article):
    """Rebuilding without publishing anything must not change the page."""
    scanned = scanned_account(primary, curated, retired, article)

    _, first = bot.build_index(scanned, "primary-1", {}, [], [], "linked", [])
    dates = bot.read_index_dates(first)
    _, second = bot.build_index(scanned, "primary-1", dates, [], [], "linked", [])

    assert json.dumps(first) == json.dumps(second)


def test_entry_href(bot, curated):
    listing = curated[0]["children"]
    assert bot.entry_href(listing[0]) == "/Filed-07-28"
    assert bot.entry_href(listing[2]) == "https://github.com/babbworks/telepatch"
    assert bot.entry_href(p("not an entry")) is None


def test_read_external_keeps_a_foreign_telegraph_page(bot):
    """
    A /link entry pointing at a DIFFERENT Telegraph account's page - the
    observer's status page, say, published under telepatch-ops rather than
    this account - is not one of this account's own pages. A rebuild must
    not wipe it, exactly as it must not wipe a GitHub link.
    """
    content = [
        {"tag": "ul", "children": [
            li("https://telegra.ph/telepatch-server-performance-08-01",
               "Server status", " — 2026-08-01"),
        ]},
        p("Index generated by Telepatch. byline=linked"),
    ]

    kept = bot.read_external(content, own_paths={"One-07-28", "Two-07-28"})

    assert len(kept) == 1
    assert bot.entry_href(kept[0]["node"]) == \
        "https://telegra.ph/telepatch-server-performance-08-01"


def test_read_external_distinguishes_own_pages_from_foreign_ones(bot, curated):
    """
    A real account mixes all three shapes: its own page linked with a
    relative href, its own page linked with an absolute telegra.ph href,
    and a plain outward link. Only the two "own page" shapes should ever
    be dropped as "the ordinary scan already has this one" - the host
    alone was never a safe test for that.
    """
    own_paths = {"Filed-07-28", "Also-Filed-07-28"}

    kept = bot.read_external(curated, own_paths)
    hrefs = {bot.entry_href(k["node"]) for k in kept}

    assert hrefs == {"https://github.com/babbworks/telepatch"}


def test_read_external_defaults_to_treating_absolute_telegraph_as_foreign(bot, curated):
    """
    Guards the default: calling read_external without own_paths must not
    silently drop nothing. An empty own_paths means every *absolute*
    telegra.ph href looks foreign - the safe failure direction - while a
    relative href is still recognised as this account's own regardless,
    since only this account's own pages are ever written that way.
    """
    kept = bot.read_external(curated)
    hrefs = {bot.entry_href(k["node"]) for k in kept}

    assert hrefs == {
        "https://telegra.ph/Also-Filed-07-28",
        "https://github.com/babbworks/telepatch",
    }
