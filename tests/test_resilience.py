"""
Retries, redaction and configuration. The retry policy matters more than
it looks: Telegraph cannot delete a page, so a retried createPage that
already landed leaves a duplicate nobody can remove.
"""

import logging

import pytest
import requests


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"ok": True, "result": "x"}

    def json(self):
        return self._payload


@pytest.fixture
def calls(bot, monkeypatch):
    """Count posts, and never actually sleep between them."""
    seen = []
    monkeypatch.setattr(bot.time, "sleep", lambda _: None)

    def record(responses):
        def post(url, data=None, timeout=None):
            seen.append(url.rsplit("/", 1)[-1])
            outcome = responses[min(len(seen) - 1, len(responses) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        monkeypatch.setattr(bot.SESSION, "post", post)
        return seen

    return record


# ------------------------------------------------------------- retries

def test_a_read_retries_on_a_server_error(bot, calls):
    seen = calls([Response(503), Response(503), Response(200)])
    assert bot._post("getPage", path="x") == "x"
    assert len(seen) == 3


def test_a_read_retries_on_a_dropped_connection(bot, calls):
    seen = calls([requests.ConnectionError("reset"), Response(200)])
    assert bot._post("getPage", path="x") == "x"
    assert len(seen) == 2


def test_createPage_is_never_retried(bot, calls):
    """
    A timeout says nothing about whether the write landed, and Telegraph
    has no way to delete the second page.
    """
    seen = calls([requests.Timeout("slow")])

    with pytest.raises(requests.Timeout):
        bot._post("createPage", title="x")

    assert len(seen) == 1


def test_createAccount_is_never_retried(bot, calls):
    seen = calls([Response(503)])
    with pytest.raises(Exception):
        bot._post("createAccount", short_name="x")
    assert len(seen) == 1


def test_editPage_is_retried_because_it_is_idempotent(bot, calls):
    seen = calls([Response(503), Response(200)])
    assert bot._post("editPage", path="x") == "x"
    assert len(seen) == 2


def test_telegraph_saying_no_is_an_answer_not_a_failure(bot, calls):
    """PAGE_NOT_FOUND must not be retried three times."""
    seen = calls([Response(200, {"ok": False, "error": "PAGE_NOT_FOUND"})])

    with pytest.raises(RuntimeError, match="PAGE_NOT_FOUND"):
        bot._post("getPage", path="nope")

    assert len(seen) == 1


def test_it_gives_up_rather_than_looping(bot, calls):
    seen = calls([Response(503)])
    with pytest.raises(Exception):
        bot._post("getPage", path="x")
    assert len(seen) == bot.RETRIES


# ----------------------------------------------------------- redaction

def record(msg, *args):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args or None, None)


def test_tokens_are_stripped_from_logs(bot):
    token = "a1b2c3" * 10                      # 60 hex, a Telegraph token
    bot_token = "123456789:AAAA-BBBB_CCCCDDDDEEEEFFFFGGGGHHHH"

    for text in (f"failed for {token}", f"bot {bot_token} died"):
        rec = record(text)
        assert bot.Redact().filter(rec)
        assert "[redacted]" in rec.msg
        assert token not in rec.msg and bot_token not in rec.msg


def test_tokens_are_stripped_from_log_arguments(bot):
    token = "f" * 60
    rec = record("url=%s status=%s", token, 500)
    bot.Redact().filter(rec)

    assert rec.args[0] == "[redacted]"
    assert rec.args[1] == 500


def test_ordinary_text_is_untouched(bot):
    rec = record("built index for %s", "Life-of-Leibniz-07-27")
    bot.Redact().filter(rec)
    assert rec.args[0] == "Life-of-Leibniz-07-27"


# --------------------------------------------------------------- config

def test_config_fails_at_startup_not_on_first_use(bot, monkeypatch):
    monkeypatch.delenv("NOT_SET", raising=False)

    with pytest.raises(SystemExit):
        bot.config("NOT_SET", required=True)

    assert bot.config("NOT_SET", "fallback") == "fallback"


def test_blank_is_treated_as_absent(bot, monkeypatch):
    monkeypatch.setenv("BLANK", "   ")
    assert bot.config("BLANK", "fallback") == "fallback"
