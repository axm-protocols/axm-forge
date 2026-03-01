"""Complexity rule — cyclomatic complexity analysis via radon."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import (
    COMPLEXITY_THRESHOLD,
    PASS_THRESHOLD,
    ProjectRule,
    register_rule,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["ComplexityRule"]

logger = logging.getLogger(__name__)


@dataclass
@register_rule("complexity")
class ComplexityRule(ProjectRule):
    """Analyse cyclomatic complexity via radon Python API.

    Scoring: 100 - (high_complexity_count * 10), min 0.
    High complexity = CC >= 10 (industry standard).

    Falls back to ``radon cc --json`` subprocess when the Python API
    is not importable (e.g. auditing a project that does not declare
    ``radon`` in its own dev dependencies).
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_COMPLEXITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check project complexity with radon."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        # Try Python API first, fall back to subprocess
        cc_visit = _try_import_radon()
        if cc_visit is not None:
            return self._check_via_api(src_path, cc_visit)

        return self._check_via_subprocess(src_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_via_api(
        self,
        src_path: Path,
        cc_visit: Callable[..., list[Any]],
    ) -> CheckResult:
        """Analyse complexity using the radon Python API."""
        high_complexity_count = 0
        all_functions: list[dict[str, str | int]] = []

        for py_file in src_path.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                blocks = cc_visit(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            for block in blocks:
                cc: int = block.complexity
                if cc >= COMPLEXITY_THRESHOLD:
                    high_complexity_count += 1
                    classname = getattr(block, "classname", "")
                    name = f"{classname}.{block.name}" if classname else block.name
                    all_functions.append(
                        {
                            "file": py_file.name,
                            "function": name,
                            "cc": cc,
                        }
                    )

        return self._build_result(high_complexity_count, all_functions)

    def _check_via_subprocess(self, src_path: Path) -> CheckResult:
        """Analyse complexity by shelling out to ``radon cc --json``."""
        radon_bin = shutil.which("radon")
        if radon_bin is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=("radon not found — complexity analysis skipped"),
                severity=Severity.ERROR,
                details={"score": 0},
                fix_hint=(
                    "Run 'uv sync' at workspace root or "
                    "'uv pip install axm-audit' to make radon available"
                ),
            )

        try:
            proc = subprocess.run(  # noqa: S603
                [radon_bin, "cc", "--json", str(src_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            data: dict[str, list[dict[str, object]]] = (
                json.loads(proc.stdout) if proc.stdout.strip() else {}
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "radon cc --json failed: %s",
                exc,
                exc_info=True,
            )
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="radon cc --json failed",
                severity=Severity.ERROR,
                details={"score": 0},
                fix_hint="Check radon installation",
            )

        high_complexity_count = 0
        all_functions: list[dict[str, str | int]] = []

        for file_path, blocks in data.items():
            file_name = Path(file_path).name
            for block in blocks:
                raw_cc = block.get("complexity", 0)
                cc = int(raw_cc) if isinstance(raw_cc, int | float | str) else 0
                if cc >= COMPLEXITY_THRESHOLD:
                    high_complexity_count += 1
                    raw_name = str(block.get("name", ""))
                    classname = str(block.get("classname", ""))
                    name = f"{classname}.{raw_name}" if classname else raw_name
                    all_functions.append(
                        {
                            "file": file_name,
                            "function": name,
                            "cc": cc,
                        }
                    )

        return self._build_result(high_complexity_count, all_functions)

    def _build_result(
        self,
        high_complexity_count: int,
        all_functions: list[dict[str, str | int]],
    ) -> CheckResult:
        """Build the final ``CheckResult`` from computed metrics."""
        top_offenders = sorted(all_functions, key=lambda x: x["cc"], reverse=True)
        score = max(0, 100 - high_complexity_count * 10)
        passed = score >= PASS_THRESHOLD

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                f"Complexity score: {score}/100 "
                f"({high_complexity_count} high-complexity functions)"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "high_complexity_count": high_complexity_count,
                "top_offenders": top_offenders,
                "score": score,
            },
            fix_hint=(
                "Refactor complex functions into smaller units"
                if high_complexity_count > 0
                else None
            ),
        )


def _try_import_radon() -> Callable[..., list[Any]] | None:
    """Try to import ``radon.complexity.cc_visit``.

    Returns:
        The ``cc_visit`` callable, or ``None`` if radon is not available.
    """
    try:
        from radon.complexity import cc_visit

        return cc_visit  # type: ignore[no-any-return]
    except ModuleNotFoundError:
        return None
