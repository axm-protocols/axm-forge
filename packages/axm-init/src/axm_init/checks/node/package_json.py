"""``package.json`` completeness checks — the Node pendant of ``checks.pyproject``.

Ports the intent of the pyproject gold-standard checks to Node: a project must
ship a parsable ``package.json`` declaring the metadata fields a published
package needs. Category key is ``node`` (the module name), matching the
``category.fn_name`` canonical-naming convention used by the Python checks.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_package_json_exists", "check_package_json_metadata"]

_REQUIRED_FIELDS = ("name", "version", "license", "repository")


def _load_package_json(project: Path) -> dict[str, object] | None:
    """Load and parse ``package.json``; return ``None`` if absent or invalid."""
    path = project / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def check_package_json_exists(project: Path) -> CheckResult:
    """Check: ``package.json`` exists and is parsable JSON."""
    path = project / "package.json"
    if not path.is_file():
        return CheckResult(
            name="package_json.package_json_exists",
            category="package_json",
            passed=False,
            weight=4,
            message="package.json not found",
            details=[],
            fix="Create a package.json at the project root (npm init).",
        )
    if _load_package_json(project) is None:
        return CheckResult(
            name="package_json.package_json_exists",
            category="package_json",
            passed=False,
            weight=4,
            message="package.json is unparsable",
            details=["File exists but contains invalid JSON"],
            fix="Fix the JSON syntax errors in package.json.",
        )
    return CheckResult(
        name="node.package_json_exists",
        category="package_json",
        passed=True,
        weight=4,
        message="package.json found",
        details=[],
        fix="",
    )


def check_package_json_metadata(project: Path) -> CheckResult:
    """Check: ``package.json`` declares the required publication metadata fields."""
    data = _load_package_json(project)
    if data is None:
        return CheckResult(
            name="package_json.package_json_metadata",
            category="package_json",
            passed=False,
            weight=3,
            message="package.json missing or unparsable",
            details=[],
            fix="Create a valid package.json before checking metadata.",
        )
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        return CheckResult(
            name="package_json.package_json_metadata",
            category="package_json",
            passed=False,
            weight=3,
            message=f"Missing {len(missing)} field(s) in package.json",
            details=[f"Missing: {', '.join(missing)}"],
            fix=f"Add {', '.join(missing)} to package.json.",
        )
    return CheckResult(
        name="node.package_json_metadata",
        category="package_json",
        passed=True,
        weight=3,
        message="All required metadata fields present",
        details=[],
        fix="",
    )
