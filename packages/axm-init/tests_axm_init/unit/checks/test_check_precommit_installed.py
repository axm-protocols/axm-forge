"""Unit tests for ``check_precommit_installed`` CI-skip behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.tooling import check_precommit_installed


def _config_no_hook(tmp_path: Path) -> Path:
    """Scaffold a project with a pre-commit config but no installed hook."""
    (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n")
    return tmp_path


class TestCheckPrecommitInstalledCI:
    def test_skips_when_ci_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: config present, no hook, CI=true -> skip (pass, not failure)."""
        monkeypatch.setenv("CI", "true")
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        r = check_precommit_installed(_config_no_hook(tmp_path))
        assert r.passed is True
        assert "CI" in r.message

    def test_skips_when_github_actions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: GITHUB_ACTIONS set also triggers the CI skip."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        r = check_precommit_installed(_config_no_hook(tmp_path))
        assert r.passed is True

    def test_fails_locally_without_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC3: config present, no hook, CI unset -> failure preserved."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        r = check_precommit_installed(_config_no_hook(tmp_path))
        assert r.passed is False
        assert "prek install" in r.fix

    def test_passes_locally_with_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC3: installed hook passes regardless of CI env."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        project = _config_no_hook(tmp_path)
        hooks = project / ".git" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\n")
        r = check_precommit_installed(project)
        assert r.passed is True
        assert r.message == "Pre-commit hooks installed"
