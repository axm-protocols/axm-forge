from __future__ import annotations

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies import get_preset, get_strategy
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


# --- merged from strategies/test_registry.py (get_strategy / get_preset live
# in strategies/__init__.py, an exempt module — covered here at the SmeltStrategy
# infrastructure level since the registry composes SmeltStrategy subclasses) ---


class TestGetStrategy:
    def test_get_strategy_tabular(self) -> None:
        s = get_strategy("tabular")
        assert s.name == "tabular"
        assert s.category == "structural"

    def test_get_strategy_strip_quotes(self) -> None:
        s = get_strategy("strip_quotes")
        assert s.name == "strip_quotes"
        assert s.category == "cosmetic"

    def test_unknown_strategy(self) -> None:
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("nonexistent")


class TestGetPreset:
    def test_get_preset_safe(self) -> None:
        strats = get_preset("safe")
        names = [s.name for s in strats]
        assert names == ["minify", "collapse_whitespace"]

    def test_get_preset_moderate(self) -> None:
        strats = get_preset("moderate")
        names = [s.name for s in strats]
        assert "minify" in names
        assert "tabular" in names

    def test_unknown_preset(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("invalid")
