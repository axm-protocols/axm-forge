"""Audit checks for CI workflows (7 checks, 18 pts)."""

from __future__ import annotations

from pathlib import Path

from axm_init.models.audit import CheckResult


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


def check_ci_test_job(project: Path) -> CheckResult:
    """Check 10: CI has a test job with Python matrix."""
    content = _read_ci(project)
    if content is None or "test" not in content.lower():
        return CheckResult(
            name="ci.test_job",
            category="ci",
            passed=False,
            weight=3,
            message="No test job in CI",
            details=["CI should have a test job with python-version matrix"],
            fix="Add a test job with strategy.matrix.python-version.",
        )
    return CheckResult(
        name="ci.test_job",
        category="ci",
        passed=True,
        weight=3,
        message="Test job present",
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


def check_ci_coverage_upload(project: Path) -> CheckResult:
    """Check 12: CI uploads coverage."""
    content = _read_ci(project)
    if content is None or (
        "coveralls" not in content.lower() and "codecov" not in content.lower()
    ):
        return CheckResult(
            name="ci.coverage_upload",
            category="ci",
            passed=False,
            weight=2,
            message="No coverage upload in CI",
            details=["CI should upload coverage to Coveralls or Codecov"],
            fix="Add coverallsapp/github-action or codecov/codecov-action step.",
        )
    return CheckResult(
        name="ci.coverage_upload",
        category="ci",
        passed=True,
        weight=2,
        message="Coverage upload configured",
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
