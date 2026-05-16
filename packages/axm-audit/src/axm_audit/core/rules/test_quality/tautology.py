"""Tautology rule — mechanical detection + delete-side triage.

Detects six tautology patterns in test bodies and classifies each finding
via :func:`tautology_triage.triage`.  Verdicts land in
``CheckResult.metadata["verdicts"]`` so downstream tooling can filter by
``DELETE``/``STRENGTHEN``/``UNKNOWN``.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypedDict, cast

from pydantic import Field

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality._shared import (
    collect_pkg_contract_classes,
    collect_pkg_public_symbols,
    iter_test_files,
)
from axm_audit.core.rules.test_quality.tautology_triage import triage
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "Finding",
    "TautologyCheckResult",
    "TautologyRule",
    "detect_tautologies",
]


_SCORE_PENALTY = 2
_MAX_TEXT_ITEMS = 20
_NON_TAUTOLOGY_ACTIONS: frozenset[str] = frozenset({"OK", "KEEP"})


class _TautologyVerdict(TypedDict):
    """Serialized verdict payload for one tautology finding."""

    file: str
    test: str
    line: int
    pattern: str
    rule: str
    verdict: str
    reason: str


def _render_tautology_text(verdicts: list[_TautologyVerdict]) -> str:
    """Render top-N tautology verdicts as a compact bullet list."""
    real = [v for v in verdicts if v["verdict"] not in _NON_TAUTOLOGY_ACTIONS]
    lines = [
        f"• {v['file']}:{v['line']} {v['test']} [{v['pattern']}]"
        for v in real[:_MAX_TEXT_ITEMS]
    ]
    if len(real) > _MAX_TEXT_ITEMS:
        lines.append(f"(+{len(real) - _MAX_TEXT_ITEMS} more)")
    return "\n".join(lines)


_ASSERT_EQUAL_ARITY = 2


@dataclass
class Finding:
    """One tautology finding for a single test function."""

    test: str
    line: int
    pattern: str
    detail: str
    path: str = ""


class TautologyCheckResult(CheckResult):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """:class:`CheckResult` with ``metadata`` carrying the verdict list."""

    metadata: dict[str, object] = Field(default_factory=dict)
    score: int = 100

    model_config = {"extra": "forbid"}


# ── AST helpers (ported from detect_tautologies.py) ──────────────────


def _unparse_safe(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):  # pragma: no cover
        return "<?>"


def _is_constant_compare_truthy(node: ast.Compare) -> bool:
    if not (isinstance(node.left, ast.Constant) and node.left.value):
        return False
    if not all(isinstance(op, ast.Eq) for op in node.ops):
        return False
    target = node.left.value
    return all(
        isinstance(c, ast.Constant) and c.value == target for c in node.comparators
    )


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
        case ast.Compare() as cmp if _is_constant_compare_truthy(cmp):
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


class _PureBuiltin(Protocol):
    """A side-effect-free callable accepting positional ``object`` arguments."""

    def __call__(self, *args: object) -> object: ...


_PURE_BUILTINS: dict[str, _PureBuiltin] = {
    "int": cast(_PureBuiltin, int),
    "float": cast(_PureBuiltin, float),
    "str": cast(_PureBuiltin, str),
    "bool": cast(_PureBuiltin, bool),
    "len": cast(_PureBuiltin, len),
    "abs": cast(_PureBuiltin, abs),
    "round": cast(_PureBuiltin, round),
    "min": cast(_PureBuiltin, min),
    "max": cast(_PureBuiltin, max),
}


def _u_usub(v: object) -> object:
    return -cast(int, v)


def _u_uadd(v: object) -> object:
    return +cast(int, v)


def _u_not(v: object) -> object:
    return not v


def _u_invert(v: object) -> object:
    return ~cast(int, v)


_UnaryOpFn = Callable[[object], object]

_UNARY_OPS: dict[type, _UnaryOpFn] = {
    ast.USub: _u_usub,
    ast.UAdd: _u_uadd,
    ast.Not: _u_not,
    ast.Invert: _u_invert,
}


def _b_add(a: object, b: object) -> object:
    return cast(int, a) + cast(int, b)


def _b_sub(a: object, b: object) -> object:
    return cast(int, a) - cast(int, b)


def _b_mult(a: object, b: object) -> object:
    return cast(int, a) * cast(int, b)


def _b_div(a: object, b: object) -> object:
    return cast(int, a) / cast(int, b)


def _b_floordiv(a: object, b: object) -> object:
    return cast(int, a) // cast(int, b)


def _b_mod(a: object, b: object) -> object:
    return cast(int, a) % cast(int, b)


def _b_pow(a: object, b: object) -> object:
    return cast(int, a) ** cast(int, b)


_BinaryOpFn = Callable[[object, object], object]

_BINARY_OPS: dict[type, _BinaryOpFn] = {
    ast.Add: _b_add,
    ast.Sub: _b_sub,
    ast.Mult: _b_mult,
    ast.Div: _b_div,
    ast.FloorDiv: _b_floordiv,
    ast.Mod: _b_mod,
    ast.Pow: _b_pow,
}


def _c_eq(a: object, b: object) -> bool:
    return a == b


def _c_neq(a: object, b: object) -> bool:
    return a != b


def _c_lt(a: object, b: object) -> bool:
    return cast(int, a) < cast(int, b)


def _c_lte(a: object, b: object) -> bool:
    return cast(int, a) <= cast(int, b)


def _c_gt(a: object, b: object) -> bool:
    return cast(int, a) > cast(int, b)


def _c_gte(a: object, b: object) -> bool:
    return cast(int, a) >= cast(int, b)


def _c_is(a: object, b: object) -> bool:
    return a is b


def _c_is_not(a: object, b: object) -> bool:
    return a is not b


_CompareOpFn = Callable[[object, object], bool]

_COMPARE_OPS: dict[type, _CompareOpFn] = {
    ast.Eq: _c_eq,
    ast.NotEq: _c_neq,
    ast.Lt: _c_lt,
    ast.LtE: _c_lte,
    ast.Gt: _c_gt,
    ast.GtE: _c_gte,
    ast.Is: _c_is,
    ast.IsNot: _c_is_not,
}


def _eval_unary(node: ast.UnaryOp) -> tuple[bool, object]:
    fn = _UNARY_OPS.get(type(node.op))
    if fn is None:
        return False, None
    ok, val = _eval_pure(node.operand)
    if not ok:
        return False, None
    try:
        return True, fn(val)
    except TypeError:
        return False, None


def _eval_binop(node: ast.BinOp) -> tuple[bool, object]:
    fn = _BINARY_OPS.get(type(node.op))
    if fn is None:
        return False, None
    okl, lv = _eval_pure(node.left)
    okr, rv = _eval_pure(node.right)
    if not (okl and okr):
        return False, None
    try:
        return True, fn(lv, rv)
    except (TypeError, ZeroDivisionError, ValueError, OverflowError):
        return False, None


def _eval_and(evaluated: list[object]) -> tuple[bool, object]:
    for val in evaluated:
        if not val:
            return True, val
    return True, evaluated[-1] if evaluated else True


def _eval_or(evaluated: list[object]) -> tuple[bool, object]:
    for val in evaluated:
        if val:
            return True, val
    return True, evaluated[-1] if evaluated else False


def _eval_boolop(node: ast.BoolOp) -> tuple[bool, object]:
    evaluated: list[object] = []
    for v in node.values:
        ok, val = _eval_pure(v)
        if not ok:
            return False, None
        evaluated.append(val)
    if isinstance(node.op, ast.And):
        return _eval_and(evaluated)
    if isinstance(node.op, ast.Or):
        return _eval_or(evaluated)
    return False, None


def _eval_call(node: ast.Call) -> tuple[bool, object]:
    if not (isinstance(node.func, ast.Name) and not node.keywords):
        return False, None
    fn = _PURE_BUILTINS.get(node.func.id)
    if fn is None:
        return False, None
    args: list[object] = []
    for a in node.args:
        ok, val = _eval_pure(a)
        if not ok:
            return False, None
        args.append(val)
    try:
        return True, fn(*args)
    except (TypeError, ValueError, OverflowError):
        return False, None


def _eval_compare(node: ast.Compare) -> tuple[bool, object]:
    ok, cur = _eval_pure(node.left)
    if not ok:
        return False, None
    for op, comp in zip(node.ops, node.comparators, strict=False):
        fn = _COMPARE_OPS.get(type(op))
        if fn is None:
            return False, None
        okc, rv = _eval_pure(comp)
        if not okc:
            return False, None
        try:
            res = fn(cur, rv)
        except TypeError:
            return False, None
        if not res:
            return True, False
        cur = rv
    return True, True


class _EvalFn(Protocol):
    def __call__(self, node: ast.expr, /) -> tuple[bool, object]: ...


_EVAL_DISPATCH: dict[type, _EvalFn] = {
    ast.UnaryOp: cast(_EvalFn, _eval_unary),
    ast.BinOp: cast(_EvalFn, _eval_binop),
    ast.BoolOp: cast(_EvalFn, _eval_boolop),
    ast.Call: cast(_EvalFn, _eval_call),
    ast.Compare: cast(_EvalFn, _eval_compare),
}


def _eval_pure(node: ast.expr) -> tuple[bool, object]:
    """Try to evaluate *node* as a pure constant expression.

    Returns ``(ok, value)``. Only literals, arithmetic/comparison/bool
    operators, and a small whitelist of side-effect-free builtins on
    constant arguments are considered pure.
    """
    if isinstance(node, ast.Constant):
        return True, node.value
    fn = _EVAL_DISPATCH.get(type(node))
    if fn is None:
        return False, None
    return fn(node)


def _is_constant_arithmetic_assert(node: ast.expr) -> bool:
    """True when *node* is a fully-constant expression (no free variables).

    Catches asserts like ``assert 100 - 5 * 2 == 90`` or
    ``assert int(0.9 * 100) == 90`` whose truth value is fixed at
    AST-time and therefore exercises no SUT.
    """
    if isinstance(node, ast.Constant):
        return False
    ok, _ = _eval_pure(node)
    return ok


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


def _is_self_compare(test_expr: ast.expr) -> bool:
    return (
        isinstance(test_expr, ast.Compare)
        and len(test_expr.ops) == 1
        and len(test_expr.comparators) == 1
        and _same_expr(test_expr.left, test_expr.comparators[0])
    )


def _build_trivially_true(node: ast.Assert, test_expr: ast.expr) -> Finding:
    return Finding(
        test="",
        line=node.lineno,
        pattern="trivially_true",
        detail=f"assert {_unparse_safe(test_expr)}",
    )


def _build_self_compare(node: ast.Assert, test_expr: ast.expr) -> Finding:
    assert isinstance(test_expr, ast.Compare)
    op_name = type(test_expr.ops[0]).__name__
    return Finding(
        test="",
        line=node.lineno,
        pattern="self_compare",
        detail=f"assert {_unparse_safe(test_expr.left)} {op_name} itself",
    )


def _build_len_tautology(node: ast.Assert, test_expr: ast.expr) -> Finding:
    return Finding(
        test="",
        line=node.lineno,
        pattern="len_tautology",
        detail=f"assert {_unparse_safe(test_expr)}",
    )


def _build_constant_arithmetic(node: ast.Assert, test_expr: ast.expr) -> Finding:
    return Finding(
        test="",
        line=node.lineno,
        pattern="constant_arithmetic",
        detail=f"assert {_unparse_safe(test_expr)}",
    )


_ASSERT_PATTERNS: tuple[
    tuple[Callable[[ast.expr], bool], Callable[[ast.Assert, ast.expr], Finding]], ...
] = (
    (_is_constant_truthy, _build_trivially_true),
    (_is_self_compare, _build_self_compare),
    (_is_len_always_true, _build_len_tautology),
    (_is_constant_arithmetic_assert, _build_constant_arithmetic),
)


def _check_assert_stmt(
    node: ast.Assert, mock_setups: dict[str, ast.expr]
) -> Finding | None:
    test_expr = node.test
    if test_expr is None:
        return None
    for predicate, builder in _ASSERT_PATTERNS:
        if predicate(test_expr):
            return builder(node, test_expr)
    echo = _find_mock_echo(test_expr, mock_setups)
    if echo:
        return Finding(
            test="",
            line=node.lineno,
            pattern="mock_echo",
            detail=echo,
        )
    return None


def _check_assert_equal_self_compare(call: ast.Call, node: ast.Expr) -> Finding | None:
    args = call.args
    if len(args) != _ASSERT_EQUAL_ARITY or not _same_expr(args[0], args[1]):
        return None
    return Finding(
        test="",
        line=node.lineno,
        pattern="self_compare",
        detail=f"assertEqual({_unparse_safe(args[0])}, same)",
    )


def _check_assert_true_constant(call: ast.Call, node: ast.Expr) -> Finding | None:
    args = call.args
    if len(args) != 1 or not _is_constant_truthy(args[0]):
        return None
    return Finding(
        test="",
        line=node.lineno,
        pattern="trivially_true",
        detail=f"assertTrue({_unparse_safe(args[0])})",
    )


def _check_unittest_call(node: ast.Expr) -> Finding | None:
    """Dispatch a unittest-style assertion call to the matching tautology check."""
    call = node.value
    if not isinstance(call, ast.Call):
        return None
    if not (
        isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
    ):
        return None
    match call.func.attr:
        case "assertEqual":
            return _check_assert_equal_self_compare(call, node)
        case "assertTrue":
            return _check_assert_true_constant(call, node)
        case _:
            return None


def _check_assert(node: ast.AST, mock_setups: dict[str, ast.expr]) -> Finding | None:
    """Dispatch *node* to the matching tautology check (plain or unittest)."""
    if isinstance(node, ast.Assert):
        return _check_assert_stmt(node, mock_setups)
    if isinstance(node, ast.Expr):
        return _check_unittest_call(node)
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

    _verdicts: list[_TautologyVerdict] = field(
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

        all_verdicts: list[_TautologyVerdict] = []
        for test_file, tree in self._iter_test_files_with_fallback(project_path):
            if tree is None:
                continue
            all_verdicts.extend(
                self._verdicts_for_file(
                    test_file, tree, project_path, pkg_symbols, contracts
                )
            )

        counted = [
            v for v in all_verdicts if v["verdict"] not in _NON_TAUTOLOGY_ACTIONS
        ]
        n = len(counted)
        score = max(0, 100 - n * _SCORE_PENALTY)
        passed = n == 0
        message = "no tautologies found" if passed else f"{n} tautology finding(s)"
        text = _render_tautology_text(all_verdicts) if not passed else None
        fix_hint = (
            None
            if passed
            else (
                "Replace tautological asserts with behavioral assertions "
                "on real outputs"
            )
        )
        return TautologyCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            metadata={"verdicts": all_verdicts},
            score=score,
            text=text,
            fix_hint=fix_hint,
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
        pkg_symbols: set[str],
        contracts: set[str],
    ) -> list[_TautologyVerdict]:
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
        verdicts: list[_TautologyVerdict] = []
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
