"""Integration tests for axm_mcp.lifecycle — real filesystem I/O (find_binary)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


class TestFindBinary:
    """Cover find_binary() in lifecycle.py with real filesystem I/O."""

    def test_prefers_global_bin(self, tmp_path: Path) -> None:
        """Prefers ~/.local/bin/axm-mcp when it exists."""
        global_bin = tmp_path / ".local" / "bin" / "axm-mcp"
        global_bin.parent.mkdir(parents=True)
        global_bin.touch()

        with patch("axm_mcp.lifecycle._GLOBAL_BIN", global_bin):
            from axm_mcp.lifecycle import find_binary

            result = find_binary()
            assert result == global_bin
