"""Unit tests for the node CI gold-standard checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.node.ci import (
    check_ci_lint_job,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
)

_CI = """\
name: CI
jobs:
  lint:
    steps: [{ run: npm run lint }]
  test:
    strategy:
      matrix:
        node-version: [20, 22]
    steps: [{ run: npm test }]
  security:
    steps: [{ run: npm audit --audit-level high }]
"""


def _workflow(tmp_path: Path, content: str) -> Path:
    """Write a CI workflow file under .github/workflows and return the root."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(content)
    return tmp_path


def test_workflow_absent_fails(tmp_path: Path) -> None:
    """No workflow dir fails the existence check."""
    assert check_ci_workflow_exists(tmp_path).passed is False


def test_full_workflow_passes_all(tmp_path: Path) -> None:
    """A workflow with lint/test-matrix/audit passes every CI check."""
    root = _workflow(tmp_path, _CI)
    assert check_ci_workflow_exists(root).passed is True
    assert check_ci_lint_job(root).passed is True
    assert check_ci_test_job(root).passed is True
    assert check_ci_security_job(root).passed is True


def test_test_job_requires_matrix(tmp_path: Path) -> None:
    """A test step without a node-version matrix fails the test-job check."""
    root = _workflow(tmp_path, "jobs:\n  test:\n    steps: [{ run: npm test }]\n")
    assert check_ci_test_job(root).passed is False
