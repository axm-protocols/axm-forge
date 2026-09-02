"""Integration tests for semantic CI workflow step validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks import ci

pytestmark = pytest.mark.integration


def _write_workflow(project: Path, filename: str, content: str) -> None:
    workflows = project / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / filename).write_text(content)


def test_mapping_without_uses_or_run_fails_with_job_and_entry(tmp_path: Path) -> None:
    """AC3: an orphan mapping fails and identifies its job and entry."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    steps:
      - name: orphan
""".lstrip(),
    )

    result = ci.check_ci_steps_executable(tmp_path)

    assert result.passed is False
    assert "test" in result.message
    assert "orphan" in result.message


def test_invalid_release_workflow_is_reported_by_filename(tmp_path: Path) -> None:
    """AC4: an invalid release workflow is found even when ci.yml is healthy."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    steps:
      - run: pytest
""".lstrip(),
    )
    _write_workflow(
        tmp_path,
        "release.yml",
        """
jobs:
  release:
    steps:
      - v*
""".lstrip(),
    )

    result = ci.check_ci_steps_executable(tmp_path)

    assert result.passed is False
    assert "release.yml" in result.message


def test_decorated_executable_steps_pass(tmp_path: Path) -> None:
    """AC5: uses/run steps remain valid with all supported decorations."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
jobs:
  test:
    steps:
      - name: checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
        if: always()
      - name: tests
        run: pytest
        env:
          PYTHONUTF8: "1"
        continue-on-error: false
""".lstrip(),
    )

    result = ci.check_ci_steps_executable(tmp_path)

    assert result.passed is True
