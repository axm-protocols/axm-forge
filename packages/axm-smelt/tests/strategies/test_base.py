from __future__ import annotations

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy


def test_cannot_instantiate_abstract() -> None:
    """SmeltStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        SmeltStrategy()  # type: ignore[abstract]


def test_partial_implementation_raises() -> None:
    """Subclass missing abstract methods cannot be instantiated."""

    class Incomplete(SmeltStrategy):
        @property
        def name(self) -> str:
            return "incomplete"

        # Missing category and apply

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_concrete_subclass_works() -> None:
    """Fully implemented subclass can be instantiated and called."""

    class Noop(SmeltStrategy):
        @property
        def name(self) -> str:
            return "noop"

        @property
        def category(self) -> str:
            return "test"

        def apply(self, ctx: SmeltContext) -> SmeltContext:
            return ctx

    s = Noop()
    assert s.name == "noop"
    assert s.category == "test"
    ctx = SmeltContext(text="hello")
    assert s.apply(ctx) is ctx
