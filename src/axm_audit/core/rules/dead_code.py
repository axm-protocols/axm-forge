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
        # Check if axm-ast is available in the environment
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

        # 2. Run the actual analysis
        try:
            result = run_in_project(
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

        # The CLI writes JSON to stdout
        try:
            # We expect a string back from run_in_project.stdout
            out = result.stdout or "[]"
            # axm-ast dead-code returns: {"total": 1, "dead_symbols": [...]}
            data = json.loads(out)
        except json.JSONDecodeError:
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

        # Extract symbols array from wrapped JSON output
        if isinstance(data, dict):
            dead_symbols = data.get("dead_symbols", [])
        else:
            dead_symbols = data if isinstance(data, list) else []

        dead_count = len(dead_symbols)

        # 3. Score
        score = max(0.0, 100.0 - (dead_count * 5.0))
        passed = dead_count == 0

        message = (
            "No dead code detected."
            if passed
            else f"Found {dead_count} dead (unreferenced) symbol(s)."
        )

        details = {
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
