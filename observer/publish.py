"""
The Telegraph half. One method, one page, forever.

This is a deliberate near-duplicate of bot.py's _post(). It is not imported
from there because bot.py reads TELEGRAM_TOKEN at module scope with
required=True (bot.py:101), so importing it would make the observer refuse
to start without a Telegram token it has no use for. Two independently
startable services is worth ~40 duplicated lines.

WHY THIS CANNOT CREATE A PAGE
-----------------------------
There is no createPage call in this file and there must never be one. The
page path arrives from configuration, so however many times this service
restarts it edits the same page. The abuse shape Telegraph would care about
is unbounded page creation; a service that is structurally incapable of it
is a service that cannot drift into it after a bad night's debugging.

bot.py:414 reaches the same conclusion from the other side: createPage is
never retried because a timeout tells you nothing about whether the write
landed and Telegraph has no deletePage. editPage is freely repeatable
because writing the same content twice is the same as writing it once -
which is exactly why a status page is a safe thing to publish this way.
"""

import json
import logging
import random
import time

import requests

log = logging.getLogger("observer.publish")

TELEGRAPH_API = "https://api.telegra.ph"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Telepatch Observer (+https://github.com/babbworks/telepatch)"
)

RETRIES = 3
BACKOFF = 0.4

# Telegraph documents no rate limits and none could be found published, so
# there is no known error string to match on. These are the shapes a
# throttle would plausibly take, matched case-insensitively as a substring.
# If the observer ever does get limited, the real string will appear in the
# log line below and belongs in this tuple.
THROTTLED = ("flood", "too many", "rate", "retry")


def _post(method, **params):
    """
    A flat POST returning result, or raising. Blocking on purpose - the
    observer is one thread with a sleep loop and has no event loop to
    block.
    """

    url = f"{TELEGRAPH_API}/{method}"
    data = {key: value for key, value in params.items() if value is not None}

    last = None

    for attempt in range(RETRIES):

        try:
            response = SESSION.post(url, data=data, timeout=15)

            if response.status_code < 500:
                payload = response.json()

                if payload.get("ok"):
                    return payload["result"]

                error = str(payload.get("error", "unknown Telegraph error"))

                # bot.py raises on any not-ok answer without retrying, which
                # is right for a user-facing command - the person is waiting
                # and a wrong token will not fix itself. Here nobody is
                # waiting, so a throttle is worth backing off through.
                if not any(word in error.lower() for word in THROTTLED):
                    raise RuntimeError(error)

                log.warning("telegraph.throttled method=%s error=%s", method, error)
                last = RuntimeError(error)

            else:
                last = RuntimeError(f"Telegraph returned {response.status_code}")

        except (requests.RequestException, ValueError) as problem:
            last = problem

        if attempt + 1 < RETRIES:
            time.sleep(BACKOFF * (2 ** attempt) + random.random() * 0.1)

    raise last if last else RuntimeError("Telegraph did not answer")


def edit(token, path, title, content, author_name=None, author_url=None):
    """
    Replace the page's content wholesale.

    author_name and author_url are passed explicitly every single time.
    bot.py:484 records the trap: Telegraph's write methods do NOT inherit
    the account's byline - only the telegra.ph web editor reads those. Omit
    them here and the page silently loses its byline and renders as a bare
    date. There is no warning and no way to notice except by looking.
    """

    return _post(
        "editPage",
        access_token=token,
        path=path,
        title=title,
        content=json.dumps(content, ensure_ascii=False),
        author_name=author_name or "",
        author_url=author_url or "",
        return_content="false",
    )


def account(token):
    """
    Who we are publishing as. Called once at startup so a bad token fails
    loudly at boot rather than silently at the first publish, half an hour
    later, into a log nobody is reading.
    """

    return _post(
        "getAccountInfo",
        access_token=token,
        fields='["short_name","author_name","author_url","page_count"]',
    )
