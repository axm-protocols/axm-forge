"""Flag tests that reach into private (``_prefixed``) package symbols.

Tests that import ``_private`` helpers couple the suite to implementation
details, turning refactors into multi-file chores.  The rule walks every
``tests/**/test_*.py`` file, collects imports of underscore-prefixed
symbols from first-party packages and classifies each hit via
``axm_ast.extract_module_info``.

Dunders (``__version__``) are always ignored and ``_UPPER_CASE`` constants
are ignored by default — flip ``include_constants=True`` on the rule
instance to surface those as well.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_ast import ModuleInfo
from axm_ast.core.parser import extract_module_info

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality._shared import (
    get_pkg_prefixes,
    iter_test_files,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["PrivateImportsRule"]


_DUNDER_RE = re.compile(r"^__\w+__$")
_CONSTANT_RE = re.compile(r"^_[A-Z][A-Z0-9_]+$")
_DOCS_ANCHOR = "docs/test_quality.md#private-imports"
_SCORE_PENALTY = 5


@dataclass(frozen=True)
class _ScanContext:
    project_path: Path
    pkg_prefixes: list[str]
    mod_cache: dict[str, ModuleInfo | None]


def _variable_kind(name: str) -> str:
    return "constant" if _CONSTANT_RE.match(name) else "variable"


def _test_owning_package(
    test_file: Path, project_path: Path, pkg_prefixes: Iterable[str]
) -> str | None:
    """Return the top-level first-party package the test belongs to.

    For single-package projects, every test belongs to that package.  For
    multi-package projects, the owning package is inferred from the test
    path under ``tests/`` (e.g. ``tests/pkg_b/test_x.py`` -> ``pkg_b``).
    Returns ``None`` when the owner cannot be determined.
    """
    prefixes = set(pkg_prefixes)
    if len(prefixes) == 1:
        return next(iter(prefixes))
    try:
        rel = test_file.relative_to(project_path / "tests")
    except ValueError:
        return None
    for part in rel.parts:
        if part in prefixes:
            return part
    return None


def _is_same_package_module_import(
    module: str, name: str, project_path: Path, test_pkg: str | None
) -> bool:
    """True when ``from module import name`` targets a private *submodule*
    that lives in the same top-level package as the importing test file.
    """
    if test_pkg is None or module.split(".", 1)[0] != test_pkg:
        return False
    rel = (module + "." + name).replace(".", "/")
    src = project_path / "src"
    return (src / f"{rel}.py").exists() or (src / rel / "__init__.py").exists()


@dataclass
@register_rule("test_quality")
class PrivateImportsRule(ProjectRule):
    """Report test imports of private package symbols."""

    include_constants: bool = False

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_PRIVATE_IMPORTS"

    def check(self, project_path: Path) -> CheckResult:
        """Scan test files in ``project_path`` for private-symbol imports.

        Walks every ``tests/**/test_*.py`` file under ``project_path``,
        collects ``ImportFrom`` nodes that reference first-party packages
        and flags each underscore-prefixed alias.  Dunders are always
        ignored; ``_UPPER_CASE`` constants are ignored unless
        ``include_constants`` is ``True``.

        Returns a :class:`CheckResult` with ``passed=True`` when no
        private imports are found.  Otherwise ``details["findings"]``
        lists each offending import (test file, line, source module,
        symbol, and resolved kind) and ``details["score"]`` reports a
        100-point score penalised by ``_SCORE_PENALTY`` per finding.
        """
        early = self.check_src(project_path)
        if early is not None:
            return early

        pkg_prefixes = get_pkg_prefixes(project_path)
        findings: list[dict[str, Any]] = []
        mod_cache: dict[str, ModuleInfo | None] = {}

        ctx = _ScanContext(
            project_path=project_path,
            pkg_prefixes=list(pkg_prefixes),
            mod_cache=mod_cache,
        )
        for test_file, tree in iter_test_files(project_path):
            if tree is None:
                continue
            test_pkg = _test_owning_package(test_file, project_path, ctx.pkg_prefixes)
            findings.extend(
                self._scan_file_for_private_imports(test_file, tree, ctx, test_pkg)
            )

        return self._build_check_result(findings)

    def _scan_file_for_private_imports(
        self,
        test_file: Path,
        tree: ast.AST,
        ctx: _ScanContext,
        test_pkg: str | None = None,
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            mod = node.module
            if not any(mod == p or mod.startswith(p + ".") for p in ctx.pkg_prefixes):
                continue
            for alias in node.names or []:
                name = alias.name
                if not self._is_private_symbol(name):
                    continue
                if _is_same_package_module_import(
                    mod, name, ctx.project_path, test_pkg
                ):
                    continue
                kind = self._resolve_symbol_kind(
                    mod, name, ctx.project_path, ctx.mod_cache
                )
                findings.append(
                    {
                        "test_file": str(test_file),
                        "line": node.lineno,
                        "import_module": mod,
                        "private_symbol": name,
                        "symbol_kind": kind,
                    }
                )
        return findings

    def _is_private_symbol(self, name: str) -> bool:
        if not name.startswith("_"):
            return False
        if _DUNDER_RE.match(name):
            return False
        if _CONSTANT_RE.match(name) and not self.include_constants:
            return False
        return True

    def _build_check_result(self, findings: list[dict[str, Any]]) -> CheckResult:
        n = len(findings)
        score = max(0, 100 - n * _SCORE_PENALTY)
        passed = n == 0
        if passed:
            message = f"No private imports in tests/ (see {_DOCS_ANCHOR})"
        else:
            message = f"{n} private import(s) in tests/ — see {_DOCS_ANCHOR}"
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.ERROR,
            details={"findings": findings, "score": score},
        )

    def _resolve_symbol_kind(
        self,
        module: str,
        symbol: str,
        pkg_root: Path,
        cache: dict[str, ModuleInfo | None],
    ) -> str:
        """Return the kind of *symbol* in *module*.

        Possible values: function, class, constant, variable, unknown.
        """
        if module not in cache:
            cache[module] = self._load_module_info(module, pkg_root)
        info = cache[module]
        if info is None:
            return "unknown"
        return self._lookup_symbol_in_info(info, symbol)

    @staticmethod
    def _lookup_symbol_in_info(info: ModuleInfo, symbol: str) -> str:
        dispatch: list[tuple[list[Any], str | Callable[[str], str]]] = [
            (info.functions, "function"),
            (info.classes, "class"),
            (info.variables, _variable_kind),
        ]
        for entries, kind in dispatch:
            for entry in entries:
                if entry.name == symbol:
                    return kind(symbol) if callable(kind) else kind
        return "unknown"

    def _load_module_info(self, module: str, pkg_root: Path) -> ModuleInfo | None:
        path = self._resolve_source_path(module, pkg_root)
        if path is None:
            return None
        try:
            return extract_module_info(path)
        except (FileNotFoundError, ValueError, OSError):
            return None

    @staticmethod
    def _resolve_source_path(module: str, pkg_root: Path) -> Path | None:
        rel = module.replace(".", "/")
        candidates = (
            pkg_root / "src" / f"{rel}.py",
            pkg_root / "src" / rel / "__init__.py",
        )
        for cand in candidates:
            if cand.exists():
                return cand
        return None
