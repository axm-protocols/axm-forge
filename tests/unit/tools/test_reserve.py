"""Tests for tools.reserve — test mirror."""

from __future__ import annotations


class TestReserveToolImport:
    """Smoke: reserve tool is importable."""

    def test_import_init_reserve_tool(self) -> None:
        """InitReserveTool is importable."""
        from axm_init.tools.reserve import InitReserveTool

        assert InitReserveTool is not None
