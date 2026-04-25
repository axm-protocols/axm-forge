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
from collections.abc import Callable
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


def _variable_kind(name: str) -> str:
    return "constant" if _CONSTANT_RE.match(name) else "variable"


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
        """Scan test files in ``project_path`` for private-symbol imports."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        pkg_prefixes = get_pkg_prefixes(project_path)
        findings: list[dict[str, Any]] = []
        mod_cache: dict[str, ModuleInfo | None] = {}

        for test_file, tree in iter_test_files(project_path):
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                mod = node.module
                if not any(mod == p or mod.startswith(p + ".") for p in pkg_prefixes):
                    continue
                for alias in node.names or []:
                    name = alias.name
                    if not name.startswith("_"):
                        continue
                    if _DUNDER_RE.match(name):
                        continue
                    if _CONSTANT_RE.match(name) and not self.include_constants:
                        continue
                    kind = self._resolve_symbol_kind(mod, name, project_path, mod_cache)
                    findings.append(
                        {
                            "test_file": str(test_file),
                            "line": node.lineno,
                            "import_module": mod,
                            "private_symbol": name,
                            "symbol_kind": kind,
                        }
                    )

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
