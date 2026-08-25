"""``tsconfig.json`` gold-standard checks — the Node pendant of mypy config.

A node/TS project must ship a ``tsconfig.json`` with strict mode on (the
research's gold-standard baseline, equivalent to the Python mypy-strict check).
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_tsconfig_exists", "check_tsconfig_strict"]


def _load_tsconfig(project: Path) -> dict[str, object] | None:
    """Load and parse ``tsconfig.json``; return ``None`` if absent/invalid."""
    path = project / "tsconfig.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def check_tsconfig_exists(project: Path) -> CheckResult:
    """Check: ``tsconfig.json`` exists and is parsable."""
    if _load_tsconfig(project) is None:
        return CheckResult(
            name="tsconfig.tsconfig_exists",
            category="tsconfig",
            passed=False,
            weight=3,
            message="tsconfig.json missing or unparsable",
            details=[],
            fix="Add a tsconfig.json with strict mode enabled.",
        )
    return CheckResult(
        name="tsconfig.tsconfig_exists",
        category="tsconfig",
        passed=True,
        weight=3,
        message="tsconfig.json found",
        details=[],
        fix="",
    )


def check_tsconfig_strict(project: Path) -> CheckResult:
    """Check: ``tsconfig.json`` enables ``compilerOptions.strict``."""
    data = _load_tsconfig(project)
    if data is None:
        return CheckResult(
            name="tsconfig.tsconfig_strict",
            category="tsconfig",
            passed=False,
            weight=3,
            message="tsconfig.json missing — cannot verify strict mode",
            details=[],
            fix="Add tsconfig.json with compilerOptions.strict = true.",
        )
    options = data.get("compilerOptions")
    opts = options if isinstance(options, dict) else {}
    if opts.get("strict") is not True:
        return CheckResult(
            name="tsconfig.tsconfig_strict",
            category="tsconfig",
            passed=False,
            weight=3,
            message="tsconfig strict mode is not enabled",
            details=["compilerOptions.strict must be true"],
            fix="Set compilerOptions.strict = true in tsconfig.json.",
        )
    return CheckResult(
        name="tsconfig.tsconfig_strict",
        category="tsconfig",
        passed=True,
        weight=3,
        message="tsconfig strict mode enabled",
        details=[],
        fix="",
    )
