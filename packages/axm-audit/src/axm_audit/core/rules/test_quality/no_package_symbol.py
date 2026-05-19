"""Dual-criterion rule for integration / e2e tests.

Every test under ``tests/integration/`` or ``tests/e2e/`` must either

* exercise a first-party Python symbol (criterion **a**), or
* invoke a declared ``[project.scripts]`` entrypoint (criterion **b**).

A test in ``tests/e2e/`` that exercises only Python symbols is
mis-located (its real boundary is integration); a test that satisfies
neither criterion is not exercising the package at all. Both shapes are
reported with a verdict that drives a concrete fix-hint.

The rule mirrors :class:`PrivateImportsRule` structurally
(``rule_id`` / ``check`` / ``_scan_file`` / ``_build_check_result``)
but delegates the AST primitives to ``_shared`` so that
``pyramid_level`` and ``no_package_symbol`` consume the same
first-party-symbol / in-package-script helpers.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality._shared import (
    current_level_from_path,
    decorator_has_marker,
    file_has_module_marker,
    get_pkg_prefixes,
    iter_test_files,
    iter_test_funcs,
    load_project_scripts,
    test_invokes_in_package_script,
    test_references_first_party,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NoPackageSymbolRule"]

_SCORE_PENALTY = 2
_MARKER_NAME = "no_package_symbol_ok"
_FIX_HINT_MISLOCATED = (
    "Move test to tests/integration/ — it exercises Python symbols, not the package CLI"
)
_FIX_HINT_NO_SYMBOL = (
    "Express the invariant as a versioned rule of the target package, "
    "or move the check to a doc/packaging linter outside the pytest suite"
)


@dataclass(frozen=True)
class _Finding:
    test_file: str
    verdict: str  # "MISLOCATED_INTEGRATION" | "NO_PACKAGE_SYMBOL"
    criterion_a_passed: bool
    criterion_b_passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "test_file": self.test_file,
            "verdict": self.verdict,
            "criterion_a_passed": self.criterion_a_passed,
            "criterion_b_passed": self.criterion_b_passed,
        }


@dataclass(frozen=True)
class _ScanContext:
    project_path: Path
    pkg_prefixes: set[str]
    project_scripts: set[str]


def _has_per_test_marker(func: ast.FunctionDef) -> bool:
    return any(decorator_has_marker(d, _MARKER_NAME) for d in func.decorator_list)


def _classify_test(
    func: ast.FunctionDef,
    tree: ast.Module,
    level: str,
    ctx: _ScanContext,
) -> tuple[str, bool, bool] | None:
    """Return ``(verdict, a_passed, b_passed)`` or ``None`` when the test is OK.

    Verdict mapping:
        * (a) or (b)               -> OK (returns ``None``)
        * (a) only and level=e2e   -> ``MISLOCATED_INTEGRATION``
        * neither                  -> ``NO_PACKAGE_SYMBOL``
        * (b) only                 -> OK (criterion (b) satisfies for either tier)
    """
    a_passed = test_references_first_party(
        test_func=func,
        module_ast=tree,
        pkg_prefixes=ctx.pkg_prefixes,
    )
    b_passed = test_invokes_in_package_script(
        test_func=func,
        module_ast=tree,
        project_scripts=ctx.project_scripts,
    )
    if b_passed:
        return None
    if a_passed:
        if level == "e2e":
            return ("MISLOCATED_INTEGRATION", a_passed, b_passed)
        return None
    return ("NO_PACKAGE_SYMBOL", a_passed, b_passed)


@dataclass(frozen=True)
class _FileAggregate:
    any_a: bool
    any_b: bool


def _aggregate_file_verdicts(
    tree: ast.Module, level: str, ctx: _ScanContext
) -> _FileAggregate | None:
    any_a = False
    any_b = False
    had_unmarked_test = False
    for func in iter_test_funcs(tree):
        if _has_per_test_marker(func):
            continue
        had_unmarked_test = True
        verdict = _classify_test(func, tree, level, ctx)
        if verdict is None:
            return None
        any_a = any_a or verdict[1]
        any_b = any_b or verdict[2]
    if not had_unmarked_test:
        return None
    return _FileAggregate(any_a=any_a, any_b=any_b)


def _finding_for_aggregate(rel: str, agg: _FileAggregate, level: str) -> _Finding:
    if agg.any_a and not agg.any_b and level == "e2e":
        return _Finding(
            test_file=rel,
            verdict="MISLOCATED_INTEGRATION",
            criterion_a_passed=True,
            criterion_b_passed=False,
        )
    return _Finding(
        test_file=rel,
        verdict="NO_PACKAGE_SYMBOL",
        criterion_a_passed=agg.any_a,
        criterion_b_passed=agg.any_b,
    )


def _pick_fix_hint(findings: list[_Finding]) -> str | None:
    if not findings:
        return None
    has_mis = any(f.verdict == "MISLOCATED_INTEGRATION" for f in findings)
    has_no_sym = any(f.verdict == "NO_PACKAGE_SYMBOL" for f in findings)
    if has_mis and not has_no_sym:
        return _FIX_HINT_MISLOCATED
    if has_no_sym and not has_mis:
        return _FIX_HINT_NO_SYMBOL
    return _FIX_HINT_NO_SYMBOL + " — also: " + _FIX_HINT_MISLOCATED


@register_rule(category="test_quality")
class NoPackageSymbolRule(ProjectRule):
    """Flag integration / e2e tests that exercise neither symbol nor CLI."""

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_NO_PACKAGE_SYMBOL"

    def check(self, project_path: Path) -> CheckResult:
        """Scan integration/e2e tests for missing package exercise."""
        early = self.check_src(project_path)
        if early is not None:
            return early
        tests_dir = project_path / "tests"
        if not tests_dir.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="no tests/ directory",
                severity=Severity.INFO,
                score=100,
            )
        ctx = _ScanContext(
            project_path=project_path,
            pkg_prefixes=get_pkg_prefixes(project_path),
            project_scripts=load_project_scripts(project_path),
        )
        findings: list[_Finding] = []
        for test_file, tree in iter_test_files(project_path):
            if tree is None:
                continue
            level = current_level_from_path(test_file, tests_dir)
            if level not in {"integration", "e2e"}:
                continue
            findings.extend(self._scan_file(test_file, tree, level, ctx))
        return self._build_check_result(findings)

    def _scan_file(
        self,
        test_file: Path,
        tree: ast.Module,
        level: str,
        ctx: _ScanContext,
    ) -> list[_Finding]:
        """Report one finding per file when NO test exercises the package.

        The rule's intent is per-file: a test module that nowhere touches a
        first-party symbol or in-package CLI is the offender. Mixing one
        fixture-validation test with one symbol-exercising test is fine.
        """
        if file_has_module_marker(tree, _MARKER_NAME):
            return []
        aggregate = _aggregate_file_verdicts(tree, level, ctx)
        if aggregate is None:
            return []
        try:
            rel = test_file.relative_to(ctx.project_path).as_posix()
        except ValueError:
            rel = str(test_file)
        return [_finding_for_aggregate(rel, aggregate, level)]

    def _build_check_result(self, findings: list[_Finding]) -> CheckResult:
        n = len(findings)
        score = max(0, 100 - n * _SCORE_PENALTY)
        passed = n == 0
        if passed:
            message = "every integration/e2e test exercises the package"
        else:
            message = f"{n} integration/e2e test(s) exercise no package symbol or CLI"
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            score=score,
            details={"findings": [f.as_dict() for f in findings]},
            fix_hint=_pick_fix_hint(findings),
        )
