"""Tests for checks.tooling — developer tooling checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.tooling import (
    check_makefile,
    check_precommit_basic,
    check_precommit_conventional,
    check_precommit_exists,
    check_precommit_installed,
    check_precommit_mypy,
    check_precommit_ruff,
)


class TestCheckPrecommitExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_precommit_exists(empty_project)
        assert r.passed is False


class TestCheckPrecommitRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_ruff(empty_project)
        assert r.passed is False


class TestCheckPrecommitMypy:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_mypy(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_mypy(empty_project)
        assert r.passed is False


class TestCheckPrecommitConventional:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_conventional(gold_project)
        assert r.passed is True

    def test_fail_no_hook(self, tmp_path: Path) -> None:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: x\n")
        r = check_precommit_conventional(tmp_path)
        assert r.passed is False


class TestCheckPrecommitBasic:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_basic(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_basic(empty_project)
        assert r.passed is False


class TestCheckMakefile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_makefile(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_makefile(empty_project)
        assert r.passed is False

    def test_fail_partial_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("install:\n\techo hi\n")
        r = check_makefile(tmp_path)
        assert r.passed is False
        assert len(r.details) > 0  # reports missing targets


class TestCheckPrecommitInstalled:
    def test_pass_hooks_installed(self, gold_project: Path) -> None:
        """Config exists + .git/hooks/pre-commit exists -> PASS."""
        r = check_precommit_installed(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_pass_no_config(self, empty_project: Path) -> None:
        """No .pre-commit-config.yaml -> PASS (nothing to install)."""
        r = check_precommit_installed(empty_project)
        assert r.passed is True

    def test_fail_config_no_hooks(self, tmp_path: Path) -> None:
        """Config exists but no .git/hooks/pre-commit -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
        assert "pre-commit install" in r.fix

    def test_fail_git_dir_no_hooks(self, tmp_path: Path) -> None:
        """.git/ exists but no hooks/ -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        (tmp_path / ".git").mkdir()
        r = check_precommit_installed(tmp_path)
        assert r.passed is False

    def test_fail_no_git_dir(self, tmp_path: Path) -> None:
        """Config exists but not a git repo -> FAIL."""
        (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
        r = check_precommit_installed(tmp_path)
        assert r.passed is False
