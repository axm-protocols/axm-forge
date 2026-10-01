"""Dead code rule — detects unreferenced symbols via the axm-ast library."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.cache import get_package
from axm_ast.core.dead_code import find_dead_code

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

# axm-ast is a required library dependency; no executable is needed.

__all__ = ["DeadCodeRule"]

_MAX_TOP_OFFENDERS = 10


@register_rule("lint")
class DeadCodeRule(ProjectRule):
    """Detect dead (unreferenced) code using axm-ast.

    Uses the same package builder and analysis as the axm-ast CLI.

    Scoring: 100 - (dead_symbols_count * 5), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "QUALITY_DEAD_CODE"

    def check(self, project_path: Path) -> CheckResult:
        """Analyze the package in-process, with no CLI or target imports."""
        try:
            results = find_dead_code(get_package(project_path))
        except (OSError, ValueError, RuntimeError) as exc:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="Failed to analyze dead code",
                severity=Severity.ERROR,
                score=0,
                details={"error": str(exc)},
            )
        return self._build_result(
            [
                {
                    "name": symbol.name,
                    "module_path": symbol.module_path,
                    "line": symbol.line,
                    "kind": symbol.kind,
                }
                for symbol in results
            ]
        )

    def _build_result(self, dead_symbols: list[dict[str, object]]) -> CheckResult:
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
            "dead_count": dead_count,
            "symbols": dead_symbols,
        }

        if dead_symbols:
            details["top_offenders"] = dead_symbols[:_MAX_TOP_OFFENDERS]

        text_lines: list[str] = []
        for sym in dead_symbols[:_MAX_TOP_OFFENDERS]:
            path = str(sym.get("file", sym.get("module_path", "")))
            if path.startswith("src/"):
                path = path[4:]
            text_lines.append(f"\u2022 {sym['name']} {path}:{sym.get('line', '')}")
        if dead_count > _MAX_TOP_OFFENDERS:
            text_lines.append(f"\u2022 +{dead_count - _MAX_TOP_OFFENDERS} more")

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING if dead_count > 0 else Severity.INFO,
            score=int(score),
            details=details,
            fix_hint="Remove dead code or mark exported in __all__ if public API",
            text="\n".join(text_lines) if text_lines else None,
        )
