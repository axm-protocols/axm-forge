"""Tautology rule — mechanical detection + delete-side triage.

Detects six tautology patterns in test bodies and classifies each finding
via :func:`tautology_triage.triage`.  Verdicts land in
``CheckResult.metadata["verdicts"]`` so downstream tooling can filter by
``DELETE``/``STRENGTHEN``/``UNKNOWN``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import Field

from axm_audit.core.registry import register_rule
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.test_quality._shared import (
    collect_pkg_contract_classes,
    collect_pkg_public_symbols,
    iter_test_files,
)
from axm_audit.core.rules.test_quality.tautology_triage import triage
from axm_audit.core.severity import Severity
from axm_audit.models.results import CheckResult

__all__ = [
    "Finding",
    "TautologyCheckResult",
    "TautologyRule",
    "detect_tautologies",
]


_SCORE_PENALTY = 2
_ASSERT_EQUAL_ARITY = 2


@dataclass
class Finding:
    """One tautology finding for a single test function."""

    test: str
    line: int
    pattern: str
    detail: str
    path: str = ""


class TautologyCheckResult(CheckResult):
    """:class:`CheckResult` with ``metadata`` carrying the verdict list."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    score: int = 100

    model_config = {"extra": "forbid"}


# ── AST helpers (ported from detect_tautologies.py) ──────────────────


def _unparse_safe(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):  # pragma: no cover
        return "<?>"


def _is_constant_truthy(node: ast.expr) -> bool:  # noqa: PLR0911
    match node:
        case ast.Constant(value=v) if v:
            return True
        case ast.List(elts=elts) if elts:
            return True
        case ast.Dict(keys=keys) if keys:
            return True
        case ast.Tuple(elts=elts) if elts:
            return True
        case ast.Set(elts=elts) if elts:
            return True
        case ast.JoinedStr():
            return True
    return False


def _same_expr(a: ast.expr, b: ast.expr) -> bool:
    return ast.dump(a) == ast.dump(b)


def _is_deep_access(node: ast.expr) -> bool:
    match node:
        case ast.Subscript():
            return True
        case ast.Attribute():
            return True
        case ast.Call(func=ast.Attribute(attr="get")):
            return True
    return False


def _is_isinstance_call(node: ast.expr, *, shallow_only: bool = False) -> bool:
    match node:
        case ast.Call(func=ast.Name(id="isinstance"), args=[first, *_]):
            if shallow_only and _is_deep_access(first):
                return False
            return True
    return False


def _is_none_compare(node: ast.expr) -> bool:
    match node:
        case ast.Compare(left=left, ops=ops, comparators=comps):
            if _is_deep_access(left):
                return False
            for op, comp in zip(ops, comps, strict=False):
                if isinstance(comp, ast.Constant) and comp.value is None:
                    if isinstance(op, ast.IsNot | ast.NotEq):
                        return True
    return False


def _is_len_always_true(node: ast.expr) -> bool:
    match node:
        case ast.Compare(
            left=ast.Call(func=ast.Name(id="len")),
            ops=[ast.GtE()],
            comparators=[ast.Constant(value=0)],
        ):
            return True
        case ast.Compare(
            left=ast.Constant(value=0),
            ops=[ast.LtE()],
            comparators=[ast.Call(func=ast.Name(id="len"))],
        ):
            return True
        case ast.Compare(
            left=ast.Call(func=ast.Name(id="len")),
            ops=[ast.Gt()],
            comparators=[ast.Constant(value=v)],
        ) if isinstance(v, int) and v < 0:
            return True
    return False


# ── Mock echo detection ───────────────────────────────────────────────


def _extract_mock_setups(body: list[ast.stmt]) -> dict[str, ast.expr]:
    setups: dict[str, ast.expr] = {}
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "return_value"
                and isinstance(target.value, ast.Name | ast.Attribute)
            ):
                key = _dotted(target.value)
                if key:
                    setups[key] = node.value
    return setups


def _dotted(expr: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST = expr
    while True:
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Name):
            parts.append(cur.id)
            break
        else:
            return None
    return ".".join(reversed(parts))


def _call_candidates(call: ast.Call) -> list[str]:
    candidates: list[str] = []
    if isinstance(call.func, ast.Name):
        candidates.append(call.func.id)
    elif isinstance(call.func, ast.Attribute):
        dotted = _dotted(call.func)
        if dotted:
            candidates.append(dotted)
        parent = _dotted(call.func.value)
        if parent:
            candidates.append(parent)
    return candidates


def _match_call_side(
    call_side: ast.expr,
    value_side: ast.expr,
    mock_setups: dict[str, ast.expr],
) -> str | None:
    if not isinstance(call_side, ast.Call):
        return None
    for key in _call_candidates(call_side):
        if key in mock_setups and _same_expr(value_side, mock_setups[key]):
            return f"{key}() == {_unparse_safe(value_side)}"
    return None


def _find_mock_echo(
    assert_node: ast.expr, mock_setups: dict[str, ast.expr]
) -> str | None:
    """Return a mock-echo explanation.

    True when *assert_node* compares a configured mock call
    to its own return value.
    """
    match assert_node:
        case ast.Compare(left=left, ops=[ast.Eq()], comparators=[comp]):
            pass
        case _:
            return None

    for call_side, value_side in ((left, comp), (comp, left)):
        result = _match_call_side(call_side, value_side, mock_setups)
        if result is not None:
            return result
    return None


# ── Per-assert / per-test checks ──────────────────────────────────────


def _check_assert(  # noqa: PLR0911
    node: ast.AST, mock_setups: dict[str, ast.expr]
) -> Finding | None:
    if isinstance(node, ast.Assert) and node.test:
        test_expr = node.test
        if _is_constant_truthy(test_expr):
            return Finding(
                test="",
                line=node.lineno,
                pattern="trivially_true",
                detail=f"assert {_unparse_safe(test_expr)}",
            )
        if (
            isinstance(test_expr, ast.Compare)
            and len(test_expr.ops) == 1
            and len(test_expr.comparators) == 1
            and _same_expr(test_expr.left, test_expr.comparators[0])
        ):
            op_name = type(test_expr.ops[0]).__name__
            return Finding(
                test="",
                line=node.lineno,
                pattern="self_compare",
                detail=f"assert {_unparse_safe(test_expr.left)} {op_name} itself",
            )
        if _is_len_always_true(test_expr):
            return Finding(
                test="",
                line=node.lineno,
                pattern="len_tautology",
                detail=f"assert {_unparse_safe(test_expr)}",
            )
        echo = _find_mock_echo(test_expr, mock_setups)
        if echo:
            return Finding(
                test="",
                line=node.lineno,
                pattern="mock_echo",
                detail=echo,
            )

    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        if isinstance(call.func, ast.Attribute) and isinstance(
            call.func.value, ast.Name
        ):
            method = call.func.attr
            args = call.args
            if (
                method == "assertEqual"
                and len(args) == _ASSERT_EQUAL_ARITY
                and _same_expr(args[0], args[1])
            ):
                return Finding(
                    test="",
                    line=node.lineno,
                    pattern="self_compare",
                    detail=f"assertEqual({_unparse_safe(args[0])}, same)",
                )
            if (
                method == "assertTrue"
                and len(args) == 1
                and _is_constant_truthy(args[0])
            ):
                return Finding(
                    test="",
                    line=node.lineno,
                    pattern="trivially_true",
                    detail=f"assertTrue({_unparse_safe(args[0])})",
                )
    return None


def _collect_asserts(body: list[ast.stmt]) -> list[ast.stmt]:
    asserts: list[ast.stmt] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assert):
            asserts.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute):
                method = call.func.attr
                if method.startswith("assert") or method == "fail":
                    asserts.append(node)
    return asserts


def _is_isinstance_assert(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assert) and _is_isinstance_call(
        node.test, shallow_only=True
    ):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "assertIsInstance"
        ):
            if call.args and _is_deep_access(call.args[0]):
                return False
            return True
    return False


def _is_none_check_assert(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assert) and _is_none_compare(node.test):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        if isinstance(call.func, ast.Attribute) and call.func.attr == "assertIsNotNone":
            if call.args and _is_deep_access(call.args[0]):
                return False
            return True
    return False


def _classify_meaningless_asserts(
    asserts: list[ast.stmt], func: ast.FunctionDef
) -> Finding | None:
    if any(
        not _is_isinstance_assert(a) and not _is_none_check_assert(a) for a in asserts
    ):
        return None

    count = len(asserts)
    if all(_is_isinstance_assert(a) for a in asserts):
        pattern = "isinstance_only"
        detail = f"{count} isinstance assert(s), no content check"
    elif all(_is_none_check_assert(a) for a in asserts):
        pattern = "none_check_only"
        detail = f"{count} not-None assert(s), no content check"
    else:
        pattern = "isinstance_only"
        detail = f"only isinstance/None checks ({count} assert(s)), no content"

    return Finding(test=func.name, line=func.lineno, pattern=pattern, detail=detail)


def _analyze_test_function(
    func: ast.FunctionDef, mock_setups: dict[str, ast.expr]
) -> list[Finding]:
    """Return tautology findings for a single test function."""
    findings: list[Finding] = []
    asserts = _collect_asserts(func.body)

    func_mock_setups = {**mock_setups, **_extract_mock_setups(func.body)}
    for a in asserts:
        f = _check_assert(a, func_mock_setups)
        if f:
            f.test = func.name
            findings.append(f)

    if asserts and not findings:
        meaningless = _classify_meaningless_asserts(asserts, func)
        if meaningless is not None:
            findings.append(meaningless)

    return findings


# ── Public API ────────────────────────────────────────────────────────


def detect_tautologies(tree: ast.Module, *, path: str = "") -> list[Finding]:
    """Return :class:`Finding` entries for every tautological test in *tree*."""
    findings: list[Finding] = []
    module_mocks = _extract_mock_setups(tree.body)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        for f in _analyze_test_function(node, module_mocks):
            f.path = path
            findings.append(f)
    return findings


# ── Helpers for the rule ──────────────────────────────────────────────


@dataclass
class _FuncLoc:
    func: ast.FunctionDef
    enclosing_class: str | None = None


def _find_func(tree: ast.Module, name: str) -> _FuncLoc | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return _FuncLoc(func=node)
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return _FuncLoc(func=item, enclosing_class=node.name)
    return None


def _collect_helpers(tree: ast.Module) -> list[ast.FunctionDef]:
    out: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_"):
            out.append(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith(
                    "test_"
                ):
                    out.append(item)
    return out


# ── Rule ──────────────────────────────────────────────────────────────


@register_rule("test_quality")
@dataclass
class TautologyRule(ProjectRule):
    """Detect tautological test assertions and triage each finding."""

    _verdicts: list[dict[str, Any]] = field(
        default_factory=list, init=False, repr=False
    )

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_TAUTOLOGY"

    def check(self, project_path: Path) -> TautologyCheckResult:
        """Scan test files in ``project_path`` and return tautology verdicts."""
        pkg_symbols = collect_pkg_public_symbols(project_path)
        contracts = collect_pkg_contract_classes(project_path)

        all_verdicts: list[dict[str, Any]] = []
        for test_file, tree in self._iter_test_files_with_fallback(project_path):
            if tree is None:
                continue
            all_verdicts.extend(
                self._verdicts_for_file(
                    test_file, tree, project_path, pkg_symbols, contracts
                )
            )

        n = len(all_verdicts)
        score = max(0, 100 - n * _SCORE_PENALTY)
        passed = n == 0
        message = "no tautologies found" if passed else f"{n} tautology finding(s)"
        return TautologyCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            metadata={"verdicts": all_verdicts},
            score=score,
        )

    @staticmethod
    def _iter_test_files_with_fallback(
        project_path: Path,
    ) -> Iterator[tuple[Path, ast.Module | None]]:
        tests_dir = project_path / "tests"
        if tests_dir.exists():
            yield from iter_test_files(project_path)
            return
        for p in sorted(project_path.rglob("test_*.py")):
            try:
                yield p, ast.parse(p.read_text(), filename=str(p))
            except (OSError, SyntaxError, UnicodeDecodeError):
                yield p, None

    @staticmethod
    def _verdicts_for_file(
        test_file: Path,
        tree: ast.Module,
        project_path: Path,
        pkg_symbols: Any,
        contracts: Any,
    ) -> list[dict[str, Any]]:
        try:
            source = test_file.read_text()
        except (OSError, UnicodeDecodeError):
            source = ""
        try:
            rel = str(test_file.relative_to(project_path))
        except ValueError:
            rel = str(test_file)
        findings = detect_tautologies(tree, path=rel)
        if not findings:
            return []
        helpers = _collect_helpers(tree)
        verdicts: list[dict[str, Any]] = []
        for f in findings:
            loc = _find_func(tree, f.test)
            if loc is None:
                continue
            v = triage(
                f,
                tree=tree,
                func=loc.func,
                enclosing_class=loc.enclosing_class,
                helpers=helpers,
                pkg_symbols=pkg_symbols,
                contracts=contracts,
                test_file=test_file,
                source_text=source,
            )
            verdicts.append(
                {
                    "file": rel,
                    "test": f.test,
                    "line": f.line,
                    "pattern": f.pattern,
                    "rule": v.rule,
                    "verdict": v.action,
                    "reason": v.reason,
                }
            )
        return verdicts
