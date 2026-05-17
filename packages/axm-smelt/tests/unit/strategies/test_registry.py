from __future__ import annotations

import pytest

from axm_smelt.strategies import get_preset, get_strategy


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
