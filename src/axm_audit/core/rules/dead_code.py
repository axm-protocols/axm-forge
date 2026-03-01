"""Dead code rule — detects unreferenced symbols via axm-ast subproccess."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.runner import run_in_project
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

__all__ = ["DeadCodeRule"]


class DeadCodeRule(ProjectRule):
    """Detect dead (unreferenced) code using axm-ast.

    Gracefully skips if axm-ast is not available in the environment.

    Scoring: 100 - (dead_symbols_count * 5), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_DEAD_CODE"

    def _skip(self, reason: str) -> CheckResult:
        """Return graceful skip result."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,  # Passing so it doesn't fail the build
            message=f"Skipped: {reason}",
            severity=Severity.INFO,
            details={"skipped": True, "reason": reason, "score": 100.0},
        )

    def check(self, project_path: Path) -> CheckResult:
        """Check for dead code using axm-ast dead-code via subprocess."""
        availability = self._check_availability(project_path)
        if availability is not None:
            return availability

        result = self._run_analysis(project_path)
        if isinstance(result, CheckResult):
            return result

        dead_symbols = self._parse_dead_symbols(result)
        if dead_symbols is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="Failed to parse axm-ast output",
                severity=Severity.ERROR,
                details={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "score": 0.0,
                },
            )
        return self._build_result(dead_symbols)

    def _check_availability(self, project_path: Path) -> CheckResult | None:
        """Return a skip result if axm-ast is not available, else None."""
        try:
            subprocess.run(
                ["uv", "run", "axm-ast", "--help"],  # noqa: S607
                cwd=project_path,
                capture_output=True,
                check=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self._skip("axm-ast is not available in the environment")
        return None

    def _run_analysis(
        self,
        project_path: Path,
    ) -> subprocess.CompletedProcess[str] | CheckResult:
        """Run axm-ast dead-code and return the result or a failure."""
        try:
            return run_in_project(
                ["uv", "run", "axm-ast", "dead-code", ".", "--json"],
                project_path,
                capture_output=True,
                text=True,
            )
        except RuntimeError:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="Failed to execute axm-ast",
                severity=Severity.ERROR,
                details={"score": 0.0},
                fix_hint="Check if the project environment is valid",
            )

    def _parse_dead_symbols(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> list[dict[str, str]] | None:
        """Parse JSON output from axm-ast, returning the dead symbols list.

        Returns ``None`` when the output is not valid JSON.
        """
        try:
            out = result.stdout or "[]"
            data = json.loads(out)
        except json.JSONDecodeError:
            return None

        if isinstance(data, dict):
            symbols: list[dict[str, str]] = data.get("dead_symbols", [])
            return symbols
        return data if isinstance(data, list) else []

    def _build_result(self, dead_symbols: list[dict[str, str]]) -> CheckResult:
        """Build a CheckResult from the dead symbols list."""
        dead_count = len(dead_symbols)
        score = max(0.0, 100.0 - (dead_count * 5.0))
        passed = dead_count == 0

        message = (
            "No dead code detected."
            if passed
            else f"Found {dead_count} dead (unreferenced) symbol(s)."
        )

        details: dict[str, object] = {
            "score": score,
            "dead_count": dead_count,
            "symbols": dead_symbols,
        }

        if dead_symbols:
            details["top_offenders"] = dead_symbols[:10]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING if dead_count > 0 else Severity.INFO,
            details=details,
            fix_hint="Remove dead code or mark exported in __all__ if public API",
        )
