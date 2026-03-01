"""Tests for tools.check — test mirror."""

from __future__ import annotations


class TestCheckToolImport:
    """Smoke: check tool is importable."""

    def test_import_init_check_tool(self) -> None:
        """InitCheckTool is importable."""
        from axm_init.tools.check import InitCheckTool

        assert InitCheckTool is not None
