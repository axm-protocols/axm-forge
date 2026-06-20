"""Node structure rule — the package.json/tsconfig pendant of the pyproject rule.

Ports the intent of the Python ``STRUCTURE_PYPROJECT`` completeness check to the
Node ecosystem: a published package must declare the manifest fields and the
strict TypeScript config the research flags as gold-standard. This is a pure
file-read rule (no subprocess), so it subclasses ``ProjectRule`` directly.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_audit.core.framework import Framework
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeStructureRule"]

# Manifest fields a published node package must declare.
_REQUIRED_PACKAGE_FIELDS = ("name", "version", "license", "type")
# tsconfig compilerOptions that must be on for a gold-standard strict setup.
_REQUIRED_TSCONFIG = ("strict",)


def _load_json(path: Path) -> dict[str, object] | None:
    """Load a JSON file as a dict, or ``None`` if absent/invalid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _missing_package_fields(pkg: dict[str, object]) -> list[str]:
    """Return the required package.json fields absent from *pkg*."""
    return [f for f in _REQUIRED_PACKAGE_FIELDS if f not in pkg]


def _missing_tsconfig(project_path: Path) -> list[str]:
    """Return the required tsconfig strict options that are not enabled."""
    tsconfig = _load_json(project_path / "tsconfig.json")
    if tsconfig is None:
        return ["tsconfig.json"]
    options = tsconfig.get("compilerOptions")
    opts = options if isinstance(options, dict) else {}
    return [key for key in _REQUIRED_TSCONFIG if opts.get(key) is not True]


@register_rule("structure", framework=Framework.NODE)
class NodeStructureRule(ProjectRule):
    """Check package.json completeness + tsconfig strict mode.

    Mirrors the Python ``PyprojectCompletenessRule``: binary field-presence
    checks, ``100 - missing * 10``.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "STRUCTURE_PACKAGE_JSON"

    def check(self, project_path: Path) -> CheckResult:
        """Score by the count of missing manifest fields + strict tsconfig opts."""
        pkg = _load_json(project_path / "package.json")
        if pkg is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message="package.json missing or unparsable",
                severity=Severity.ERROR,
                score=0,
                fix_hint="Create a valid package.json (npm init).",
            )
        missing = _missing_package_fields(pkg) + _missing_tsconfig(project_path)
        score = max(0, 100 - len(missing) * 10)
        passed = not missing
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=(
                "package.json + tsconfig complete"
                if passed
                else f"Missing: {', '.join(missing)}"
            ),
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=score,
            details={"missing": missing},
            fix_hint=f"Add {', '.join(missing)}" if missing else None,
        )
