"""Node tooling gold-standard checks — ESLint config + test script.

The Node pendant of the Python tooling checks (ruff/pre-commit config). A
gold-standard node project ships a flat ESLint config and wires a ``test``
script (the research's de-facto stack: ESLint v9 flat config + Vitest).
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_eslint_config", "check_test_script"]

# ESLint v9 flat config filenames (any one is enough).
_ESLINT_CONFIGS = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.ts",
    "eslint.config.cjs",
)


def check_eslint_config(project: Path) -> CheckResult:
    """Check: a flat ESLint config file is present."""
    if any((project / name).is_file() for name in _ESLINT_CONFIGS):
        return CheckResult(
            name="tooling.eslint_config",
            category="tooling",
            passed=True,
            weight=2,
            message="ESLint flat config found",
            details=[],
            fix="",
        )
    return CheckResult(
        name="tooling.eslint_config",
        category="tooling",
        passed=False,
        weight=2,
        message="No ESLint flat config (eslint.config.js)",
        details=[],
        fix="Add an eslint.config.js (ESLint v9 flat config).",
    )


def check_test_script(project: Path) -> CheckResult:
    """Check: ``package.json`` declares a ``test`` script."""
    pkg_path = project / "package.json"
    if not pkg_path.is_file():
        return CheckResult(
            name="tooling.test_script",
            category="tooling",
            passed=False,
            weight=2,
            message="package.json missing — cannot verify test script",
            details=[],
            fix="Add a package.json with a `test` script.",
        )
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    scripts = data.get("scripts") if isinstance(data, dict) else None
    has_test = isinstance(scripts, dict) and bool(scripts.get("test"))
    if has_test:
        return CheckResult(
            name="tooling.test_script",
            category="tooling",
            passed=True,
            weight=2,
            message="test script present",
            details=[],
            fix="",
        )
    return CheckResult(
        name="tooling.test_script",
        category="tooling",
        passed=False,
        weight=2,
        message="No `test` script in package.json",
        details=[],
        fix='Add "test": "vitest run" to package.json scripts.',
    )
