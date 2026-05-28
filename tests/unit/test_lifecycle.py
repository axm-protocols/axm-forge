"""Tests for launchd lifecycle management (plist_template, lifecycle, CLI)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_mcp.plist_template import PLIST_TEMPLATE

# ──────────────────────── plist_template tests ─────────────────────────


class TestPlistTemplate:
    """Validate the plist XML template."""

    def test_template_has_placeholders(self) -> None:
        """Template contains the required format placeholders."""
        assert "{bin_path}" in PLIST_TEMPLATE
        assert "{port}" in PLIST_TEMPLATE
        assert "{log_dir}" in PLIST_TEMPLATE

    def test_template_has_keep_alive(self) -> None:
        """Template includes KeepAlive for auto-restart."""
        assert "<key>KeepAlive</key>" in PLIST_TEMPLATE
        assert "<true/>" in PLIST_TEMPLATE

    def test_template_renders_cleanly(self) -> None:
        """Template renders without errors given valid values."""
        rendered = PLIST_TEMPLATE.format(
            bin_path="/usr/local/bin/axm-mcp",
            port=9427,
            log_dir="/tmp/logs",
        )
        assert "/usr/local/bin/axm-mcp" in rendered
        assert "9427" in rendered
        assert "/tmp/logs/stdout.log" in rendered
        assert "/tmp/logs/stderr.log" in rendered


# ──────────────────────── lifecycle tests ──────────────────────────────


class TestGeneratePlist:
    """Cover generate_plist() in lifecycle.py."""

    def test_renders_with_defaults(self, tmp_path: Path) -> None:
        """Plist contains correct binary path and default port."""
        fake_global = tmp_path / "axm-mcp"
        with (
            patch("axm_mcp.lifecycle._GLOBAL_BIN", fake_global),
            patch(
                "axm_mcp.lifecycle.shutil.which",
                return_value="/usr/local/bin/axm-mcp",
            ),
        ):
            from axm_mcp.lifecycle import generate_plist

            plist = generate_plist()
            assert "/usr/local/bin/axm-mcp" in plist
            assert "9427" in plist

    def test_renders_custom_port(self, tmp_path: Path) -> None:
        """Plist uses the provided port."""
        fake_global = tmp_path / "axm-mcp"
        with (
            patch("axm_mcp.lifecycle._GLOBAL_BIN", fake_global),
            patch(
                "axm_mcp.lifecycle.shutil.which",
                return_value="/usr/local/bin/axm-mcp",
            ),
        ):
            from axm_mcp.lifecycle import generate_plist

            plist = generate_plist(port=8080)
            assert "8080" in plist

    def test_renders_with_explicit_binary(self) -> None:
        """Plist uses the explicit binary path, skipping find_binary()."""
        from axm_mcp.lifecycle import generate_plist

        plist = generate_plist(binary=Path("/opt/custom/bin/axm-mcp"))
        assert "/opt/custom/bin/axm-mcp" in plist


class TestInstall:
    """Cover install() in lifecycle.py."""

    def test_writes_plist_and_bootstraps(self) -> None:
        """install() writes the plist file and calls launchctl bootstrap."""

        def which_side_effect(name: str) -> str:
            return f"/usr/local/bin/{name}"

        with (
            patch("axm_mcp.lifecycle.shutil.which", side_effect=which_side_effect),
            patch("axm_mcp.lifecycle.PLIST_PATH") as mock_plist_path,
            patch("axm_mcp.lifecycle.LOG_DIR") as mock_log_dir,
            patch("axm_mcp.lifecycle.subprocess.run") as mock_run,
            patch("axm_mcp.lifecycle.os.getuid", return_value=501),
        ):
            mock_plist_path.parent = MagicMock()

            from axm_mcp.lifecycle import install

            install(port=9427)

            mock_plist_path.write_text.assert_called_once()
            mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0].endswith("launchctl")
            assert args[1] == "bootstrap"
            assert "gui/501" in args[2]

    def test_install_fails_on_launchctl_error(self) -> None:
        """install() exits 1 when launchctl bootstrap fails."""
        with (
            patch(
                "axm_mcp.lifecycle.shutil.which",
                return_value="/usr/local/bin/axm-mcp",
            ),
            patch("axm_mcp.lifecycle.PLIST_PATH") as mock_plist_path,
            patch("axm_mcp.lifecycle.LOG_DIR"),
            patch(
                "axm_mcp.lifecycle.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1, "launchctl", stderr="already loaded"
                ),
            ),
            patch("axm_mcp.lifecycle.os.getuid", return_value=501),
        ):
            mock_plist_path.parent = MagicMock()

            from axm_mcp.lifecycle import install

            with pytest.raises(SystemExit):
                install()


class TestUninstall:
    """Cover uninstall() in lifecycle.py."""

    def test_bootout_and_remove(self) -> None:
        """uninstall() calls launchctl bootout and removes the plist."""
        with (
            patch("axm_mcp.lifecycle.PLIST_PATH") as mock_plist_path,
            patch("axm_mcp.lifecycle.subprocess.run") as mock_run,
            patch("axm_mcp.lifecycle.shutil.which", return_value="/usr/bin/launchctl"),
            patch("axm_mcp.lifecycle.os.getuid", return_value=501),
        ):
            mock_plist_path.exists.return_value = True

            from axm_mcp.lifecycle import uninstall

            uninstall()

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0].endswith("launchctl")
            assert args[1] == "bootout"
            mock_plist_path.unlink.assert_called_once_with(missing_ok=True)

    def test_not_installed(self) -> None:
        """uninstall() exits 1 when plist file does not exist."""
        with patch("axm_mcp.lifecycle.PLIST_PATH") as mock_plist_path:
            mock_plist_path.exists.return_value = False

            from axm_mcp.lifecycle import uninstall

            with pytest.raises(SystemExit):
                uninstall()


class TestFindBinary:
    """Cover find_binary() in lifecycle.py (shutil.which mocked, no real I/O)."""

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


# ──────────────────────── CLI integration tests ────────────────────────


class TestCLIInstall:
    """Cover install CLI command delegation."""

    def test_cli_install_delegates(self) -> None:
        """axm-mcp install delegates to lifecycle.install."""
        with (
            patch("axm_mcp.lifecycle.install") as mock_install,
            patch("sys.argv", ["axm-mcp", "install", "--port", "9427"]),
        ):
            from axm_mcp.cli import app

            with pytest.raises(SystemExit, match="0"):
                app()
            mock_install.assert_called_once_with(9427, binary=None)

    def test_cli_install_with_binary_flag(self) -> None:
        """axm-mcp install --binary passes path to lifecycle.install."""
        with (
            patch("axm_mcp.lifecycle.install") as mock_install,
            patch("sys.argv", ["axm-mcp", "install", "--binary", "/opt/bin/axm-mcp"]),
        ):
            from axm_mcp.cli import app

            with pytest.raises(SystemExit, match="0"):
                app()
            mock_install.assert_called_once_with(9427, binary=Path("/opt/bin/axm-mcp"))


class TestCLIUninstall:
    """Cover uninstall CLI command delegation."""

    def test_cli_uninstall_delegates(self) -> None:
        """axm-mcp uninstall delegates to lifecycle.uninstall."""
        with (
            patch("axm_mcp.lifecycle.uninstall") as mock_uninstall,
            patch("sys.argv", ["axm-mcp", "uninstall"]),
        ):
            from axm_mcp.cli import app

            with pytest.raises(SystemExit, match="0"):
                app()
            mock_uninstall.assert_called_once()
