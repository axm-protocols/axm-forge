"""Integration tests for axm_mcp.lifecycle — real filesystem I/O (find_binary)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


class TestFindBinary:
    """Cover find_binary() in lifecycle.py."""

    def test_prefers_global_bin(self, tmp_path: Path) -> None:
        """Prefers ~/.local/bin/axm-mcp when it exists."""
        global_bin = tmp_path / ".local" / "bin" / "axm-mcp"
        global_bin.parent.mkdir(parents=True)
        global_bin.touch()

        with patch("axm_mcp.lifecycle._GLOBAL_BIN", global_bin):
            from axm_mcp.lifecycle import find_binary

            result = find_binary()
            assert result == global_bin

    def test_falls_back_to_which(self, tmp_path: Path) -> None:
        """Falls back to shutil.which when global bin does not exist."""
        global_bin = tmp_path / ".local" / "bin" / "axm-mcp"

        with (
            patch("axm_mcp.lifecycle._GLOBAL_BIN", global_bin),
            patch("axm_mcp.lifecycle.shutil.which", return_value="/usr/bin/axm-mcp"),
        ):
            from axm_mcp.lifecycle import find_binary

            result = find_binary()
            assert result == Path("/usr/bin/axm-mcp")

    def test_warns_on_protected_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Warns when resolved binary is under a macOS-protected directory."""
        global_bin = tmp_path / ".local" / "bin" / "axm-mcp"
        protected = str(Path.home() / "Documents" / ".venv" / "bin" / "axm-mcp")

        with (
            patch("axm_mcp.lifecycle._GLOBAL_BIN", global_bin),
            patch("axm_mcp.lifecycle.shutil.which", return_value=protected),
        ):
            from axm_mcp.lifecycle import find_binary

            result = find_binary()
            assert result == Path(protected)
            err = capsys.readouterr().err
            assert "macOS-protected directory" in err
            assert "uv tool install axm-mcp" in err

    def test_not_found(self, tmp_path: Path) -> None:
        """Exits with error when binary not on PATH."""
        global_bin = tmp_path / ".local" / "bin" / "axm-mcp"

        with (
            patch("axm_mcp.lifecycle._GLOBAL_BIN", global_bin),
            patch("axm_mcp.lifecycle.shutil.which", return_value=None),
        ):
            from axm_mcp.lifecycle import find_binary

            with pytest.raises(SystemExit):
                find_binary()
