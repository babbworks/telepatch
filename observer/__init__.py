"""
telepatch-observer - what the machine running Telepatch is doing.

Deliberately standalone. Nothing here imports bot.py, because bot.py reads
TELEGRAM_TOKEN at module scope (bot.py:101) and importing it would make
this service refuse to start without a credential it never uses.

Run as `python -m observer`. See docs/observer.md for installation on the
PowerBook, and docs/superpowers/specs/2026-08-01-observer-design.md for why
it is shaped this way.
"""

__version__ = "0.1.0"
