"""Tests for models.results — test mirror."""

from __future__ import annotations


class TestResultsImport:
    """Smoke: results models are importable."""

    def test_import_reserve_result(self) -> None:
        """ReserveResult is importable from models.results."""
        from axm_init.models.results import ScaffoldResult

        assert ScaffoldResult is not None
