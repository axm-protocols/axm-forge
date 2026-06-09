"""Tests for Copier adapter."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "axm_init"
    / "templates"
    / "workspace-member"
)


class TestCopierAdapterIntegration:
    """Integration tests for CopierAdapter (real stdout, fd, logging I/O)."""

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


@pytest.mark.integration
def test_member_documentation_url_uses_workspace_base(tmp_path: Path) -> None:
    """AC1: Documentation URL is built on the workspace base, not a member-only host.

    A scaffolded member has no standalone GitHub Pages site: its docs are
    merged into the workspace site via the mkdocs ``monorepo`` plugin, served
    at ``github.io/{workspace_name}``. The Documentation URL must therefore
    resolve on the workspace base (``workspace_name``), never on a host keyed
    only by ``member_name``.
    """
    org = "acme-org"
    workspace_name = "acme-workspace"
    member_name = "my-member"
    dest = tmp_path / "member"

    config = CopierConfig(
        template_path=TEMPLATE,
        destination=dest,
        data={
            "member_name": member_name,
            "description": "A workspace member package",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "org": org,
            "license": "Apache-2.0",
            "workspace_name": workspace_name,
        },
        defaults=True,
        overwrite=True,
        trust_template=True,
    )

    result = CopierAdapter().copy(config)
    assert result.success, result.message

    pyproject = dest / "pyproject.toml"
    assert pyproject.exists()
    parsed = tomllib.loads(pyproject.read_text())
    documentation = parsed["project"]["urls"]["Documentation"]

    # Built on the workspace base, not a member-only host.
    assert workspace_name in documentation, documentation
    assert documentation != f"https://{org}.github.io/{member_name}/"
    assert f"{org}.github.io/{member_name}/" not in documentation, documentation

    # Consistent with the other member URLs (all share the workspace_name base).
    urls = parsed["project"]["urls"]
    for key in ("Homepage", "Repository", "Issues"):
        assert workspace_name in urls[key], (key, urls[key])
