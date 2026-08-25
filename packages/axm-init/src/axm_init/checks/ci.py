"""Audit checks for CI workflows (6 checks, 16 pts)."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)


def _read_ci(project: Path) -> str | None:
    """Read .github/workflows/ci.yml content, or None if missing."""
    path = project / ".github" / "workflows" / "ci.yml"
    if not path.exists():
        return None
    return path.read_text()


def check_ci_workflow_exists(project: Path) -> CheckResult:
    """Check 8: .github/workflows/ci.yml exists."""
    content = _read_ci(project)
    if content is None:
        return CheckResult(
            name="ci.workflow_exists",
            category="ci",
            passed=False,
            weight=4,
            message="CI workflow not found",
            details=["Expected: .github/workflows/ci.yml"],
            fix="Create .github/workflows/ci.yml with lint, test, and security jobs.",
        )
    return CheckResult(
        name="ci.workflow_exists",
        category="ci",
        passed=True,
        weight=4,
        message="CI workflow found",
        details=[],
        fix="",
    )


def check_ci_lint_job(project: Path) -> CheckResult:
    """Check 9: CI has a lint job."""
    content = _read_ci(project)
    if content is None or "lint" not in content.lower():
        return CheckResult(
            name="ci.lint_job",
            category="ci",
            passed=False,
            weight=3,
            message="No lint job in CI",
            details=["CI should have a lint/type-check job"],
            fix="Add a lint job to .github/workflows/ci.yml that runs `make lint`.",
        )
    return CheckResult(
        name="ci.lint_job",
        category="ci",
        passed=True,
        weight=3,
        message="Lint job present",
        details=[],
        fix="",
    )


def _step_runs_tests(step: object) -> bool:
    """True if a workflow step invokes a test runner (e.g. pytest)."""
    if not isinstance(step, dict):
        return False
    run = str(step.get("run", "")).lower()
    uses = str(step.get("uses", "")).lower()
    return "pytest" in run or "test" in run or "test" in uses


def _job_has_python_matrix(job: object) -> bool:
    """True if a job declares a strategy.matrix.python-version axis."""
    if not isinstance(job, dict):
        return False
    strategy = job.get("strategy")
    if not isinstance(strategy, dict):
        return False
    matrix = strategy.get("matrix")
    return isinstance(matrix, dict) and "python-version" in matrix


def _has_matrix_test_job(content: str) -> bool:
    """True if the workflow has a job with a python-version matrix and a
    step that runs tests."""
    try:
        workflow = yaml.safe_load(content)
    except yaml.YAMLError:
        return False
    if not isinstance(workflow, dict):
        return False
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not _job_has_python_matrix(job):
            continue
        steps = job.get("steps") if isinstance(job, dict) else None
        if isinstance(steps, list) and any(_step_runs_tests(s) for s in steps):
            return True
    return False


def check_ci_test_job(project: Path) -> CheckResult:
    """Check 10: CI has a test job with a python-version matrix."""
    content = _read_ci(project)
    if content is None or not _has_matrix_test_job(content):
        return CheckResult(
            name="ci.test_job",
            category="ci",
            passed=False,
            weight=3,
            message="No matrix test job in CI",
            details=[
                "CI must define a job with strategy.matrix.python-version "
                "and a step that runs the tests"
            ],
            fix="Add a test job with strategy.matrix.python-version.",
        )
    return CheckResult(
        name="ci.test_job",
        category="ci",
        passed=True,
        weight=3,
        message="Matrix test job present",
        details=[],
        fix="",
    )


def check_ci_security_job(project: Path) -> CheckResult:
    """Check 11: CI has a security/pip-audit job."""
    content = _read_ci(project)
    if content is None or "audit" not in content.lower():
        return CheckResult(
            name="ci.security_job",
            category="ci",
            passed=False,
            weight=2,
            message="No security audit job in CI",
            details=["CI should run pip-audit for dependency scanning"],
            fix="Add a security job that runs `uv run pip-audit`.",
        )
    return CheckResult(
        name="ci.security_job",
        category="ci",
        passed=True,
        weight=2,
        message="Security audit job present",
        details=[],
        fix="",
    )


def _read_publish(project: Path) -> str | None:
    """Read .github/workflows/publish.yml content, or None if missing."""
    path = project / ".github" / "workflows" / "publish.yml"
    if not path.exists():
        return None
    return path.read_text()


def check_trusted_publishing(project: Path) -> CheckResult:
    """Check 34: publish.yml uses Trusted Publishing (OIDC) without API token."""
    content = _read_publish(project)
    if content is None or "id-token" not in content:
        return CheckResult(
            name="ci.trusted_publishing",
            category="ci",
            passed=False,
            weight=2,
            message="No Trusted Publishing (OIDC) in publish workflow",
            details=["publish.yml should use permissions: id-token: write"],
            fix="Add `permissions: id-token: write` to publish.yml for PyPI OIDC.",
        )
    if "PYPI_API_TOKEN" in content:
        return CheckResult(
            name="ci.trusted_publishing",
            category="ci",
            passed=False,
            weight=2,
            message="publish.yml still uses PYPI_API_TOKEN alongside OIDC",
            details=["Remove secrets.PYPI_API_TOKEN to use true Trusted Publishing"],
            fix=(
                "Remove `password: ${{ secrets.PYPI_API_TOKEN }}`"
                " from publish.yml — OIDC handles auth automatically."
            ),
        )
    return CheckResult(
        name="ci.trusted_publishing",
        category="ci",
        passed=True,
        weight=2,
        message="Trusted Publishing (OIDC) configured",
        details=[],
        fix="",
    )


def check_dependabot(project: Path) -> CheckResult:
    """Check 35: .github/dependabot.yml exists."""
    if not (project / ".github" / "dependabot.yml").exists():
        return CheckResult(
            name="ci.dependabot",
            category="ci",
            passed=False,
            weight=2,
            message="Dependabot config not found",
            details=["Dependabot automates dependency security updates"],
            fix="Create .github/dependabot.yml with pip and github-actions ecosystems.",
        )
    return CheckResult(
        name="ci.dependabot",
        category="ci",
        passed=True,
        weight=2,
        message="Dependabot configured",
        details=[],
        fix="",
    )
