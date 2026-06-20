"""Node tooling gold-standard checks — ESLint config + test script.

The Node pendant of the Python tooling checks (ruff/pre-commit config). A
gold-standard node project ships a flat ESLint config and wires a ``test``
script (the research's de-facto stack: ESLint v9 flat config + Vitest).
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = [
    "check_engines_pinned",
    "check_eslint_config",
    "check_prettier_config",
    "check_test_script",
]

# Prettier config filenames / package.json key.
_PRETTIER_CONFIGS = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    ".prettierrc.cjs",
    "prettier.config.js",
    "prettier.config.cjs",
)

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


def check_engines_pinned(project: Path) -> CheckResult:
    """Check: package.json pins a supported node version via ``engines.node``.

    The node analog of the Python ``structure.python_version`` check — declares
    the runtime the package supports.
    """
    pkg_path = project / "package.json"
    if not pkg_path.is_file():
        return CheckResult(
            name="tooling.engines_pinned",
            category="tooling",
            passed=False,
            weight=2,
            message="package.json missing — cannot verify engines",
            details=[],
            fix="Add an `engines.node` field to package.json.",
        )
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    engines = data.get("engines") if isinstance(data, dict) else None
    if isinstance(engines, dict) and engines.get("node"):
        return CheckResult(
            name="tooling.engines_pinned",
            category="tooling",
            passed=True,
            weight=2,
            message=f"engines.node = {engines['node']}",
            details=[],
            fix="",
        )
    return CheckResult(
        name="tooling.engines_pinned",
        category="tooling",
        passed=False,
        weight=2,
        message="No engines.node in package.json",
        details=["Declare the supported node runtime"],
        fix='Add "engines": {"node": ">=20"} to package.json.',
    )


def check_prettier_config(project: Path) -> CheckResult:
    """Check: a Prettier config is present (file or ``prettier`` package key)."""
    if any((project / name).is_file() for name in _PRETTIER_CONFIGS):
        return CheckResult(
            name="tooling.prettier_config",
            category="tooling",
            passed=True,
            weight=1,
            message="Prettier config found",
            details=[],
            fix="",
        )
    pkg_path = project / "package.json"
    if pkg_path.is_file():
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and "prettier" in data:
            return CheckResult(
                name="tooling.prettier_config",
                category="tooling",
                passed=True,
                weight=1,
                message="Prettier config in package.json",
                details=[],
                fix="",
            )
    return CheckResult(
        name="tooling.prettier_config",
        category="tooling",
        passed=False,
        weight=1,
        message="No Prettier config",
        details=[],
        fix="Add a .prettierrc (or a `prettier` key in package.json).",
    )
