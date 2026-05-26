"""Complex source fixture with multiple imports and overloads."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mylib.core.models import ModuleInfo

SAMPLE_PKG = "sample_pkg"


class TestAnalyzeModuleUnit:
    def test_unit(self) -> None:
        info = ModuleInfo()
        mock = MagicMock()
        assert info is not None
        assert mock is not None
        assert SAMPLE_PKG == "sample_pkg"


class TestAnalyzePackageIntegration:
    def test_integration(self) -> None:
        with pytest.raises(ValueError):
            raise ValueError


class StaysHere:
    def test_stay(self) -> None:
        assert True
