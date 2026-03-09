"""Tests for tools.scaffold — test mirror.

Canonical tests live in ``test_scaffold_template.py``.
This file covers import smoke tests.
"""

from __future__ import annotations


class TestScaffoldToolImport:
    """Smoke: scaffold tool is importable."""

    def test_import_init_scaffold_tool(self) -> None:
        """InitScaffoldTool is importable."""
        from axm_init.tools.scaffold import InitScaffoldTool

        assert InitScaffoldTool is not None
