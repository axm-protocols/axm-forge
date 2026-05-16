"""Tests for checks.structure — project structure checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.structure import (
    check_uv_lock,
)


class TestCheckUvLock:
    def test_pass(self, gold_project: Path) -> None:
        r = check_uv_lock(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_uv_lock(empty_project)
        assert r.passed is False

    def test_pass_workspace_root(self, tmp_path: Path) -> None:
        """uv.lock at workspace root is detected for a member package."""
        # Workspace root
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        (tmp_path / "uv.lock").write_text("version = 1\n")
        # Member package (no local uv.lock)
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is True
        assert "workspace root" in r.message

    def test_fail_workspace_no_lock(self, tmp_path: Path) -> None:
        """Workspace root exists but has no uv.lock -> fail."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is False
