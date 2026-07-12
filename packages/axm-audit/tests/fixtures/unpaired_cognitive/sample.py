"""Fixture reproducing the complexity `no cognitive score paired` diagnostic.

radon's ``cc_visit`` reports the *class* itself as a block (name ``Registry``),
whereas complexipy only reports the class *methods* (``Registry::add`` …). The
class-level key therefore never pairs with a complexipy entry, so
``_lookup_cognitive`` emits its ``no cognitive score paired … treating cognitive
as unmeasured (0)`` warning — the exact situation hit when axm-audit audits its
own class-heavy rule modules.

The bodies are deliberately trivial (cc < 10, cog unmeasured -> 0) so the module
produces **no** complexity offenders: the audit ``score`` stays 100 and the only
observable effect is the diagnostic, which must land on stderr — never on the
``--json`` stdout payload.
"""

from __future__ import annotations


class Registry:
    """A class whose methods pair, but whose class block does not."""

    def __init__(self) -> None:
        self._items: dict[str, int] = {}

    def add(self, key: str, value: int) -> None:
        self._items[key] = value

    def get(self, key: str) -> int:
        return self._items.get(key, 0)


class Counter:
    """A second class, to fire the diagnostic more than once."""

    def __init__(self) -> None:
        self._total = 0

    def bump(self, amount: int) -> int:
        self._total += amount
        return self._total
