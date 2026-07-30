"""Integration tests for the per-root ruff availability probe.

Exercises :func:`axm_edit.services.lint.ruff_available` end-to-end against
real project directories (real ``Path.resolve`` + filesystem), with only the
``subprocess`` boundary faked to make the ruff-present / ruff-absent verdict
deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_edit.services.lint import ruff_available


@pytest.fixture(autouse=True)
def _assume_tools_available() -> None:
    """Override the global conftest stub so the real probe runs here."""
    return None


def _make_project(root: Path) -> Path:
    """Materialise a minimal project directory on disk."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'sample'\n")
    return root


@pytest.mark.integration
class TestRuffAvailableIntegration:
    """The probe distinguishes an env-local ruff from a ruff-less project."""

    def test_env_local_ruff_detected_lint_runs(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        project = _make_project(tmp_path / "with_ruff")
        run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=mocker.Mock(returncode=0),
        )

        # Available -> the lint runner's gate opens.
        assert ruff_available(project) is True
        # A subsequent edit against the same root reuses the memoized verdict.
        assert ruff_available(project) is True
        run.assert_called_once()
        assert run.call_args.kwargs["cwd"] == project

    def test_project_without_ruff_skips_cleanly(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        project = _make_project(tmp_path / "no_ruff")
        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=mocker.Mock(returncode=2),
        )

        # A non-zero probe means 'ruff absent': the runner skips, no crash and
        # no false 'ruff crashed' error surfaced from the probe itself.
        assert ruff_available(project) is False
