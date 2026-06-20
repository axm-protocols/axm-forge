"""Node CI gold-standard checks — GitHub Actions workflow with lint/test jobs.

Ports the intent of the Python ``checks.ci`` to a node project: a CI workflow
that lints, type-checks, tests across a node-version matrix, and audits
dependencies. Reads ``.github/workflows/*.yml`` as text (the same lenient
substring approach the Python checks use — no YAML parse needed).
"""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = [
    "check_ci_lint_job",
    "check_ci_security_job",
    "check_ci_test_job",
    "check_ci_workflow_exists",
]


def _read_ci(project: Path) -> str | None:
    """Return the concatenated text of every ``.github/workflows/*.yml`` file."""
    workflows = project / ".github" / "workflows"
    if not workflows.is_dir():
        return None
    parts: list[str] = []
    for wf in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        parts.append(wf.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts) if parts else None


def check_ci_workflow_exists(project: Path) -> CheckResult:
    """Check: a GitHub Actions workflow exists."""
    if _read_ci(project) is not None:
        return CheckResult(
            name="ci.ci_workflow_exists",
            category="ci",
            passed=True,
            weight=4,
            message="CI workflow found",
            details=[],
            fix="",
        )
    return CheckResult(
        name="ci.ci_workflow_exists",
        category="ci",
        passed=False,
        weight=4,
        message="CI workflow not found",
        details=["Expected: .github/workflows/*.yml"],
        fix="Create .github/workflows/ci.yml with lint, test, and audit jobs.",
    )


def check_ci_lint_job(project: Path) -> CheckResult:
    """Check: CI runs lint / type-check."""
    content = _read_ci(project) or ""
    lowered = content.lower()
    if "lint" in lowered or "eslint" in lowered or "tsc" in lowered:
        return CheckResult(
            name="ci.ci_lint_job",
            category="ci",
            passed=True,
            weight=3,
            message="Lint job present",
            details=[],
            fix="",
        )
    return CheckResult(
        name="ci.ci_lint_job",
        category="ci",
        passed=False,
        weight=3,
        message="No lint job in CI",
        details=["CI should run eslint / tsc"],
        fix="Add a lint job running `npm run lint` and `npm run typecheck`.",
    )


def check_ci_test_job(project: Path) -> CheckResult:
    """Check: CI runs tests across a node-version matrix."""
    content = _read_ci(project) or ""
    lowered = content.lower()
    has_test = "test" in lowered or "vitest" in lowered
    has_matrix = "node-version" in lowered or "matrix" in lowered
    if has_test and has_matrix:
        return CheckResult(
            name="ci.ci_test_job",
            category="ci",
            passed=True,
            weight=3,
            message="Matrix test job present",
            details=[],
            fix="",
        )
    return CheckResult(
        name="ci.ci_test_job",
        category="ci",
        passed=False,
        weight=3,
        message="No matrix test job in CI",
        details=["CI must run tests with a strategy.matrix.node-version"],
        fix="Add a test job with strategy.matrix.node-version running `npm test`.",
    )


def check_ci_security_job(project: Path) -> CheckResult:
    """Check: CI runs a dependency-audit / security step."""
    content = _read_ci(project) or ""
    lowered = content.lower()
    if "audit" in lowered or "codeql" in lowered or "security" in lowered:
        return CheckResult(
            name="ci.ci_security_job",
            category="ci",
            passed=True,
            weight=2,
            message="Security job present",
            details=[],
            fix="",
        )
    return CheckResult(
        name="ci.ci_security_job",
        category="ci",
        passed=False,
        weight=2,
        message="No security/audit job in CI",
        details=["CI should run `npm audit` or CodeQL"],
        fix="Add a job running `npm audit --audit-level high`.",
    )
