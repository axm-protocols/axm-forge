"""AC2: a fresh scaffold with no installed hook still scores 100 in CI."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine

pytestmark = pytest.mark.integration


def test_ci_scaffold_without_hook_scores_100(
    gold_project__from_check_engine_run_and_format: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gold project minus the installed hook, under CI, still scores 100."""
    project = gold_project__from_check_engine_run_and_format
    # Simulate a fresh CI checkout where hooks were never activated.
    (project / ".git" / "hooks" / "pre-commit").unlink()
    monkeypatch.setenv("CI", "true")

    result = CheckEngine(project).run()

    assert result.score == 100, [f.name for f in result.failures]


def test_local_scaffold_without_hook_below_100(
    gold_project__from_check_engine_run_and_format: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: outside CI, the missing hook drops the score below 100."""
    project = gold_project__from_check_engine_run_and_format
    (project / ".git" / "hooks" / "pre-commit").unlink()
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    result = CheckEngine(project).run()

    assert result.score < 100
    assert "tooling.precommit_installed" in {f.name for f in result.failures}
