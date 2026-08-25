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
    "check_commitlint",
    "check_engines_pinned",
    "check_eslint_config",
    "check_git_hooks",
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


def _has_git_hook_manager(project: Path) -> bool:
    """Return True if a git-hook manager is configured (husky/lefthook/pre-commit)."""
    if (project / ".husky").is_dir():
        return True
    for name in ("lefthook.yml", "lefthook.yaml", ".pre-commit-config.yaml"):
        if (project / name).is_file():
            return True
    pkg = project / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        dev = data.get("devDependencies") if isinstance(data, dict) else None
        if isinstance(dev, dict) and any(
            n in dev for n in ("husky", "lefthook", "simple-git-hooks")
        ):
            return True
    return False


def check_git_hooks(project: Path) -> CheckResult:
    """Check: a git-hook manager is configured (node analog of pre-commit)."""
    if _has_git_hook_manager(project):
        return CheckResult(
            name="tooling.git_hooks",
            category="tooling",
            passed=True,
            weight=2,
            message="Git-hook manager configured",
            details=[],
            fix="",
        )
    return CheckResult(
        name="tooling.git_hooks",
        category="tooling",
        passed=False,
        weight=2,
        message="No git-hook manager (husky/lefthook)",
        details=[],
        fix="Add husky (or lefthook) to run lint/format/tests on commit.",
    )


def check_commitlint(project: Path) -> CheckResult:
    """Check: conventional-commit enforcement is configured (commitlint).

    Node analog of the Python ``tooling.precommit_conventional`` check.
    """
    configs = (
        "commitlint.config.js",
        "commitlint.config.cjs",
        "commitlint.config.mjs",
        "commitlint.config.ts",
        ".commitlintrc",
        ".commitlintrc.json",
        ".commitlintrc.js",
    )
    if any((project / name).is_file() for name in configs):
        return CheckResult(
            name="tooling.commitlint",
            category="tooling",
            passed=True,
            weight=1,
            message="commitlint configured",
            details=[],
            fix="",
        )
    pkg = project / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and "commitlint" in data:
            return CheckResult(
                name="tooling.commitlint",
                category="tooling",
                passed=True,
                weight=1,
                message="commitlint configured in package.json",
                details=[],
                fix="",
            )
    return CheckResult(
        name="tooling.commitlint",
        category="tooling",
        passed=False,
        weight=1,
        message="No commitlint config",
        details=["Enforce Conventional Commits"],
        fix="Add @commitlint/cli + a commitlint.config.js.",
    )
