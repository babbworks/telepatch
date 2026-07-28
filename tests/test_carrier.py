"""
The carrier is how a stateless bot remembers anything. If it breaks, the
token is lost or - worse - something that is not a token is sent to
Telegraph as one.
"""

from conftest import Context, Entity, Message, Update

TOKEN = "a" * 60


def test_carrier_round_trip(bot):
    url = bot.carrier_link("post", TOKEN, site="Life-of-Leibniz-07-27", n="A Name")
    href = url.split('href="')[1].split('"')[0]

    reply = Message(reply_to=Message(entities=[Entity(href)]))
    field, token, extras = bot.read_carrier(reply)

    assert field == "post"
    assert token == TOKEN
    assert extras["site"] == "Life-of-Leibniz-07-27"
    assert extras["n"] == "A Name"


def test_empty_extras_survive(bot):
    """An empty author URL is a real value, not an absent one."""
    url = bot.carrier_link("post", TOKEN, n="Name", u="")
    href = url.split('href="')[1].split('"')[0]

    _, _, extras = bot.read_carrier(Message(reply_to=Message(entities=[Entity(href)])))
    assert extras["u"] == ""
    assert "u" in extras


def test_find_token_stops_at_the_query(bot):
    """
    The bug that produced PAGE_NOT_FOUND: taking everything past the colon
    swallowed the extras into the token.
    """
    href = bot.CARRIER + "#page:" + TOKEN + "?site=Telepatch-07-27"
    assert bot.find_token(Message(reply_to=Message(entities=[Entity(href)]))) == TOKEN


def test_find_token_ignores_other_links(bot):
    href = "https://example.com/#page:" + TOKEN
    assert bot.find_token(Message(reply_to=Message(entities=[Entity(href)]))) is None


def test_no_reply_means_no_token(bot):
    assert bot.find_token(Message()) is None
    assert bot.read_carrier(Message()) == (None, None, {})


# ------------------------------------------------------- pasted tokens

def test_a_title_is_not_a_token(bot):
    """
    "/newsite Browser Extension" sent Telegraph the word "Browser" and got
    back ACCESS_TOKEN_INVALID.
    """
    update = Update(Message())

    assert bot.token_for(update, Context(["Browser", "Extension"])) is None
    assert bot.command_words(Context(["Browser", "Extension"])) == "Browser Extension"


def test_a_pasted_token_is_recognised_and_dropped_from_the_title(bot):
    ctx = Context([TOKEN, "A", "Name"])

    assert bot.token_for(Update(Message()), ctx) == TOKEN
    assert bot.command_words(ctx) == "A Name"


def test_a_reply_supplies_the_token_when_words_follow_the_command(bot):
    href = bot.CARRIER + "#page:" + TOKEN
    reply = Message(reply_to=Message(entities=[Entity(href)]))

    assert bot.token_for(Update(reply), Context(["My", "New", "Name"])) == TOKEN


def test_telegraph_path(bot):
    cases = {
        "https://telegra.ph/Some-Page-07-28": "Some-Page-07-28",
        "https://telegra.ph/Some-Page-07-28/": "Some-Page-07-28",
        "Some-Page-07-28": "Some-Page-07-28",
        "https://telegra.ph/Some-Page-07-28?x=1#y": "Some-Page-07-28",
        "": None,
    }
    for given, want in cases.items():
        assert bot.telegraph_path(given) == want
