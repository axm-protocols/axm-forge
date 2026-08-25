"""Tests for Copier adapter."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_concurrent_fd_writer_unaffected_during_copy(self, tmp_path: Path) -> None:
        """AC2: suppression is scoped — a concurrent fd-1 writer is unaffected.

        The old implementation pointed the process-global fd 1 at
        ``/dev/null`` via ``os.dup2``, which would swallow *any* writer on
        fd 1 (not just copier's).  The scoped ``_suppress_output`` only swaps
        ``sys.stdout``/``sys.stderr``, so raw ``os.write(1, ...)`` bytes from a
        concurrent task still reach the underlying fd intact, while the
        interpreter-level copier chatter is discarded.
        """
        r, w = os.pipe()
        saved_fd1 = os.dup(1)
        os.dup2(w, 1)
        try:
            config = CopierConfig(
                template_path=Path("/templates/python"),
                destination=tmp_path / "concurrent-fd",
                data={"package_name": "test"},
            )
            adapter = CopierAdapter()

            def fake_run_copy(**kwargs: object) -> None:
                # Interpreter-level chatter (must be suppressed) ...
                print("copier post-copy chatter")  # noqa: T201
                # ... alongside a concurrent writer on the raw fd 1.
                os.write(1, b"CONCURRENT-FD-BYTES\n")

            with patch("axm_init.adapters.copier.run_copy", side_effect=fake_run_copy):
                result = adapter.copy(config)
        finally:
            os.dup2(saved_fd1, 1)
            os.close(saved_fd1)
            os.close(w)
            piped = os.read(r, 65536)
            os.close(r)

        assert result.success is True
        # The concurrent fd-1 writer's bytes survived (suppression not global).
        assert b"CONCURRENT-FD-BYTES" in piped
        # The interpreter-level copier chatter did not reach fd 1.
        assert b"copier post-copy chatter" not in piped

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
class TestFilesCreatedFiltering:
    """files_created walk: keep dotted dirs like .github/, drop real noise."""

    def _copy_with_planted_files(
        self, tmp_path: Path, relpaths: list[str]
    ) -> list[str]:
        dest = tmp_path / "project"
        for rel in relpaths:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x")
        config = CopierConfig(
            template_path=Path("/templates/python"),
            destination=dest,
            data={"package_name": "test"},
        )
        adapter = CopierAdapter()
        with patch("axm_init.adapters.copier.run_copy") as mock_run:
            mock_run.return_value = MagicMock()
            result = adapter.copy(config)
        assert result.success is True
        return result.files_created

    def test_files_created_lists_github_dir_files(self, tmp_path: Path) -> None:
        """AC1: files under dotted DIRECTORIES (.github/) are listed."""
        created = self._copy_with_planted_files(
            tmp_path,
            [".github/workflows/ci.yml", "pyproject.toml"],
        )
        assert ".github/workflows/ci.yml" in created
        assert "pyproject.toml" in created

    def test_files_created_still_excludes_noise(self, tmp_path: Path) -> None:
        """AC1: genuine noise dirs (.git, __pycache__) stay excluded."""
        created = self._copy_with_planted_files(
            tmp_path,
            [
                ".git/config",
                "__pycache__/mod.pyc",
                "src/test/__pycache__/x.pyc",
                "src/test/__init__.py",
            ],
        )
        assert "src/test/__init__.py" in created
        assert not any(".git/" in c or c.startswith(".git/") for c in created)
        assert not any("__pycache__" in c for c in created)


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
