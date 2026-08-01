"""
The test that guards the privacy claim.

telepatch-observer publishes activity counts to a public page. What makes
that safe is not that we are careful - it is that tally() cannot be handed
anything but a name from a fixed set. This walks the AST of bot.py and
proves it, so a future edit that writes tally(f"post:{chat_id}") fails the
suite rather than quietly publishing somebody's identity.

Parsing rather than importing is deliberate. bot.py needs python-telegram-bot
and a TELEGRAM_TOKEN to import; the source is just text. This test therefore
runs anywhere, including a CI job with no dependencies installed, which is
exactly what you want of the check that matters most.
"""

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent.parent / "bot.py"


@pytest.fixture(scope="module")
def tree():
    return ast.parse(SOURCE.read_text())


def counted_names(tree):
    """The COUNTED frozenset, read out of the AST rather than imported."""

    for node in ast.walk(tree):

        if not isinstance(node, ast.Assign):
            continue

        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]

        if "COUNTED" not in targets:
            continue

        # frozenset({...}) - the literal is the call's single argument.
        call = node.value
        assert isinstance(call, ast.Call), "COUNTED should be frozenset({...})"

        return {
            element.value
            for element in call.args[0].elts
            if isinstance(element, ast.Constant)
        }

    raise AssertionError("COUNTED is not defined in bot.py")


def tally_calls(tree):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tally"
    ]


def test_counted_is_a_closed_set(tree):
    names = counted_names(tree)

    assert names, "COUNTED is empty, so nothing is counted at all"
    assert all(isinstance(name, str) for name in names)


def test_every_tally_argument_is_a_literal(tree):
    """
    The whole guarantee, in one assertion.

    An f-string, a variable, a concatenation or a .format() call would each
    let an identifier reach a public counter. None of them is a Constant.
    """

    for call in tally_calls(tree):
        assert len(call.args) == 1, (
            f"tally() takes exactly one argument (line {call.lineno})"
        )

        argument = call.args[0]

        assert isinstance(argument, ast.Constant), (
            f"tally() was passed a {type(argument).__name__} at line "
            f"{call.lineno}. It must be a string literal - a computed name "
            f"is how a user id reaches a public page."
        )

        assert isinstance(argument.value, str), (
            f"tally() was passed a non-string at line {call.lineno}"
        )


def test_every_tally_argument_is_in_the_vocabulary(tree):
    allowed = counted_names(tree)

    for call in tally_calls(tree):
        argument = call.args[0] if call.args else None

        # A non-literal is the other test's failure to report. Skipping it
        # here keeps that failure readable instead of burying it under an
        # AttributeError from this one.
        if not isinstance(argument, ast.Constant):
            continue

        name = argument.value

        assert name in allowed, (
            f"tally({name!r}) at line {call.lineno} is not in COUNTED. Add "
            f"it there deliberately, having decided it is publishable."
        )


def test_something_is_actually_counted(tree):
    """
    Guards against the suite passing because every tally() call was
    deleted. A green test that proves nothing is worse than a red one.
    """

    assert len(tally_calls(tree)) >= 4


def test_tally_is_not_called_with_keywords(tree):
    """
    tally(event=...) would sidestep the args[0] checks above. Cheap to
    forbid outright rather than handle.
    """

    for call in tally_calls(tree):
        assert not call.keywords, (
            f"tally() at line {call.lineno} used a keyword argument"
        )
