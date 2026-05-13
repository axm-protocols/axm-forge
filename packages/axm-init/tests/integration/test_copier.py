"""Tests for Copier adapter."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig


class TestCopierAdapterIntegration:
    """Integration tests for CopierAdapter (real stdout, fd, logging I/O)."""

    def test_copier_copy_passes_unsafe_true(self, tmp_path: Path) -> None:
        """unsafe=True is passed to run_copy when trust_template=True."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "trusted",
            data={"package_name": "test"},
            trust_template=True,
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["unsafe"] is True

    def test_copier_copy_warns_when_unsafe(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is logged when trust_template=True."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "warn-test",
            data={"package_name": "test"},
            trust_template=True,
        )
        adapter = CopierAdapter()

        with (
            patch("axm_init.adapters.copier.run_copy") as mock_run,
            caplog.at_level(logging.WARNING, logger="axm_init.adapters.copier"),
        ):
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        assert any("unsafe=True" in r.message for r in caplog.records)

    def test_copier_copy_no_warning_when_safe(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning is logged when trust_template=False."""
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "safe-test",
            data={"package_name": "test"},
            trust_template=False,
        )
        adapter = CopierAdapter()

        with (
            patch("axm_init.adapters.copier.run_copy") as mock_run,
            caplog.at_level(logging.WARNING, logger="axm_init.adapters.copier"),
        ):
            mock_run.return_value = MagicMock()
            adapter.copy(config)

        assert not any("unsafe" in r.message.lower() for r in caplog.records)

    def test_copy_handles_copier_error(self, tmp_path: Path) -> None:
        """Test graceful handling of Copier errors."""
        config = CopierConfig(
            template_path=Path("/nonexistent/template"),
            destination=tmp_path / "will-fail",
            data={},
        )
        adapter = CopierAdapter()

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.side_effect = RuntimeError("Template not found")
            result = adapter.copy(config)

        assert result.success is False
        assert "Template not found" in result.message

    def test_copy_suppresses_stdout(self, tmp_path: Path) -> None:
        """Test that stdout is suppressed during copy.

        Copier post-copy tasks (git init, uv sync) write to stdout.
        When running inside an MCP server, this corrupts the JSON-RPC
        transport. The adapter must redirect stdout/stderr.
        """
        import sys

        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "mcp-safe",
            data={"package_name": "test"},
        )
        adapter = CopierAdapter()
        captured_stdout = ""

        def fake_run_copy(**kwargs: object) -> None:
            # Simulate copier + post-copy tasks writing to stdout
            print("Initialized project")  # noqa: T201
            sys.stdout.write("Installing dependencies...\n")

        with patch("axm_init.adapters.copier.run_copy", side_effect=fake_run_copy):
            old_stdout = sys.stdout
            result = adapter.copy(config)
            # stdout should be restored to original
            assert sys.stdout is old_stdout
            captured_stdout = (
                old_stdout.getvalue() if hasattr(old_stdout, "getvalue") else ""
            )

        assert result.success is True
        # The copier output must NOT have leaked to the real stdout
        assert "Initialized project" not in captured_stdout

    def test_copy_fd_cleanup_on_dup_failure(self, tmp_path: Path) -> None:
        """No fd leak when os.dup fails partway through acquisition.

        Simulates fd limit exhaustion: os.dup(1) succeeds but os.dup(2)
        raises OSError.  The previously acquired fd must still be closed.
        """
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "fd-leak-test",
            data={"package_name": "test"},
        )
        adapter = CopierAdapter()

        original_dup = os.dup
        call_count = 0

        def _dup_that_fails_second(fd: int) -> int:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise OSError("fd limit reached")
            return original_dup(fd)

        with (
            patch(
                "axm_init.adapters.copier.os.dup",
                side_effect=_dup_that_fails_second,
            ),
            patch("axm_init.adapters.copier.os.open", return_value=99),
            patch("axm_init.adapters.copier.os.dup2"),
            patch("axm_init.adapters.copier.os.close") as mock_close,
        ):
            result = adapter.copy(config)

        assert result.success is False
        assert "fd limit" in result.message.lower()
        # devnull (99) and the first dup'd fd must have been closed
        closed_fds = [c.args[0] for c in mock_close.call_args_list]
        assert 99 in closed_fds  # devnull was cleaned up

    def test_copy_fd_cleanup_on_copier_failure(self, tmp_path: Path) -> None:
        """stdout/stderr are restored after run_copy raises."""
        import sys

        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=tmp_path / "restore-test",
            data={"package_name": "test"},
        )
        adapter = CopierAdapter()
        original_stdout = sys.stdout

        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.side_effect = RuntimeError("Template error")
            result = adapter.copy(config)

        assert result.success is False
        # stdio must be fully restored after the error
        assert sys.stdout is original_stdout
