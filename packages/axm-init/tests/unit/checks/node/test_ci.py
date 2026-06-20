"""Unit tests for the node CI gold-standard checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.node.ci import (
    check_ci_dependabot,
    check_ci_lint_job,
    check_ci_publish,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
)


def test_dependabot_config_passes(tmp_path: Path) -> None:
    """A .github/dependabot.yml passes the dependabot check."""
    wf = tmp_path / ".github"
    wf.mkdir()
    (wf / "dependabot.yml").write_text("version: 2\n")
    assert check_ci_dependabot(tmp_path).passed is True


def test_renovate_config_passes(tmp_path: Path) -> None:
    """A renovate.json also satisfies the dependabot check."""
    (tmp_path / "renovate.json").write_text("{}")
    assert check_ci_dependabot(tmp_path).passed is True


def test_dependabot_absent_fails(tmp_path: Path) -> None:
    """No dependency-update config fails."""
    assert check_ci_dependabot(tmp_path).passed is False


def test_publish_requires_provenance(tmp_path: Path) -> None:
    """A publish workflow needs provenance/id-token to pass."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "release.yml").write_text(
        "permissions:\n  id-token: write\nsteps:\n  - run: npm publish --provenance\n"
    )
    assert check_ci_publish(tmp_path).passed is True


def test_publish_without_workflow_fails(tmp_path: Path) -> None:
    """No publish workflow fails."""
    assert check_ci_publish(tmp_path).passed is False


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
