"""Delete-side triage for tautology findings.

Implements the v4 decision tree steps that decide whether a tautology
finding should be deleted or strengthened.  Only the delete-side steps
plus the supporting STRENGTHEN guards (n2b, n1, 0, 0c, 0d, 1a, 1b) are
ported here; the remaining STRENGTHEN steps land in a follow-up ticket.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from axm_audit.core.rules.test_quality._shared import (
    is_import_smoke_test,
    test_is_in_lazy_import_context,
)

if TYPE_CHECKING:
    from axm_audit.core.rules.test_quality.tautology import Finding

__all__ = [
    "Verdict",
    "triage",
]


_TEST_INFRA_CALLS: frozenset[str] = frozenset(
    {
        "assertEqual",
        "assertNotEqual",
        "assertTrue",
        "assertFalse",
        "assertIs",
        "assertIsNot",
        "assertIsNone",
        "assertIsNotNone",
        "assertIn",
        "assertNotIn",
        "assertIsInstance",
        "assertNotIsInstance",
        "assertRaises",
        "assertWarns",
        "assertLogs",
        "assertAlmostEqual",
        "assertCountEqual",
        "assertGreater",
        "assertGreaterEqual",
        "assertLess",
        "assertLessEqual",
        "assertRegex",
        "assertNotRegex",
        "fail",
        "skipTest",
        "setUp",
        "tearDown",
        "raises",
        "warns",
        "deprecated_call",
        "skip",
        "xfail",
        "importorskip",
        "mark",
        "Mock",
        "MagicMock",
        "patch",
        "PropertyMock",
        "AsyncMock",
        "create_autospec",
        "sentinel",
        "call",
        "monkeypatch",
        "isinstance",
        "len",
        "type",
        "print",
        "hasattr",
        "getattr",
        "setattr",
        "id",
        "hash",
        "vars",
        "dir",
        "repr",
        "super",
        "object",
        "callable",
    }
)

_STDLIB_CONTRACT_NAMES: frozenset[str] = frozenset(
    {
        "Mapping",
        "Sequence",
        "Iterable",
        "Iterator",
        "Callable",
        "AsyncIterable",
        "AsyncIterator",
        "Awaitable",
        "Coroutine",
        "Container",
        "Collection",
        "Reversible",
        "Sized",
        "Hashable",
        "Set",
        "MutableMapping",
        "MutableSequence",
        "MutableSet",
    }
)

_FACTORY_PREFIXES: tuple[str, ...] = ("create_", "make_", "build_", "new_", "from_")

_CONTRACT_NAME_INFIXES: tuple[str, ...] = (
    "_is_a_",
    "_is_an_",
    "_is_instance",
    "_is_cyclopts",
    "_satisfies_",
    "_satisfies",
    "_implements_",
    "_implements",
    "_conforms_to_",
    "_conforms_",
    "_is_axm_tool",
    "_is_tool_result",
    "_is_provider_port",
    "_compliance",
)


@dataclass
class Verdict:
    """Result of triaging one tautology finding."""

    action: str
    rule: str
    reason: str


# ── Small AST helpers ─────────────────────────────────────────────────


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _call_name(node: ast.Call) -> str | None:
    match node.func:
        case ast.Name(id=name):
            return name
        case ast.Attribute(attr=attr):
            return attr
    return None


def _extract_calls(body: list[ast.stmt], helper_names: set[str]) -> list[str]:
    calls: list[str] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if not name:
                continue
            if name in _TEST_INFRA_CALLS or name in helper_names:
                continue
            if name.startswith("assert"):
                continue
            calls.append(name)
    return calls


def _dominant_call(
    body: list[ast.stmt], helper_names: set[str], pkg_symbols: set[str]
) -> str | None:
    calls = _extract_calls(body, helper_names)
    if not calls:
        return None
    for c in calls:
        if c in pkg_symbols:
            return c
    return calls[0]


def _call_signature(call: ast.Call) -> str:
    name = _call_name(call) or ""
    parts: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant):
            parts.append(repr(arg.value))
        elif isinstance(arg, ast.Name):
            parts.append(f"var:{arg.id}")
        elif isinstance(arg, ast.List):
            inner = [
                repr(e.value) if isinstance(e, ast.Constant) else type(e).__name__
                for e in arg.elts
            ]
            parts.append(f"[{','.join(inner)}]")
        else:
            parts.append(type(arg).__name__)
    for kw in call.keywords:
        if isinstance(kw.value, ast.Constant):
            parts.append(f"{kw.arg}={kw.value.value!r}")
        elif isinstance(kw.value, ast.List):
            inner = [
                repr(e.value) if isinstance(e, ast.Constant) else type(e).__name__
                for e in kw.value.elts
            ]
            parts.append(f"{kw.arg}=[{','.join(inner)}]")
        elif isinstance(kw.value, ast.Name):
            parts.append(f"{kw.arg}=var:{kw.value.id}")
        else:
            parts.append(f"{kw.arg}={type(kw.value).__name__}")
    return f"{name}({','.join(parts)})"


def _extract_call_signatures(
    body: list[ast.stmt], helper_names: set[str]
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if not name or name in _TEST_INFRA_CALLS or name in helper_names:
            continue
        out.append((name, _call_signature(node)))
    return out


# ── Contracts / naming ────────────────────────────────────────────────


def _isinstance_target(func: ast.FunctionDef) -> str | None:
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) >= 2
        ):
            second = node.args[1]
            match second:
                case ast.Name(id=name):
                    return name
                case ast.Attribute(attr=name):
                    return name
    return None


def _is_contract_conformance_test(func: ast.FunctionDef, contracts: set[str]) -> bool:
    target = _isinstance_target(func)
    if not target:
        return False
    return target in contracts or target in _STDLIB_CONTRACT_NAMES


def _name_is_explicit_contract(name: str) -> bool:
    low = name.lower()
    return any(inf in low for inf in _CONTRACT_NAME_INFIXES)


# ── Sibling traversal ─────────────────────────────────────────────────


def _iter_sibling_funcs(
    tree: ast.Module, target_name: str, target_class: str | None
) -> list[ast.FunctionDef]:
    """Yield `test_*` siblings of *target_name* (class-scoped when provided)."""
    results: list[ast.FunctionDef] = []
    if target_class:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == target_class:
                for item in node.body:
                    if (
                        isinstance(item, ast.FunctionDef)
                        and item.name.startswith("test_")
                        and item.name != target_name
                    ):
                        results.append(item)
        return results
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
            and node.name != target_name
        ):
            results.append(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and item.name.startswith("test_")
                    and item.name != target_name
                ):
                    results.append(item)
    return results


@dataclass
class _SiblingInfo:
    count: int = 0
    dominant_calls: set[str] = field(default_factory=set)
    all_calls: set[str] = field(default_factory=set)
    call_signatures: set[str] = field(default_factory=set)


def _collect_siblings(
    tree: ast.Module,
    target_name: str,
    target_class: str | None,
    helper_names: set[str],
    pkg_symbols: set[str],
) -> _SiblingInfo:
    info = _SiblingInfo()
    for sib in _iter_sibling_funcs(tree, target_name, target_class):
        info.count += 1
        dc = _dominant_call(sib.body, helper_names, pkg_symbols)
        if dc:
            info.dominant_calls.add(dc)
        info.all_calls |= set(_extract_calls(sib.body, helper_names))
        for _, sig in _extract_call_signatures(sib.body, helper_names):
            info.call_signatures.add(sig)
    return info


# ── Top-level import / smoke helpers ──────────────────────────────────


def _collect_top_level_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                names.add(alias.asname or alias.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _asserted_name_is_not_none(func: ast.FunctionDef) -> str | None:
    body = [s for s in func.body if not _is_docstring(s)]
    if len(body) != 1:
        return None
    stmt = body[0]
    if not isinstance(stmt, ast.Assert):
        return None
    test = stmt.test
    if isinstance(test, ast.Compare):
        if (
            len(test.ops) == 1
            and isinstance(test.ops[0], ast.IsNot)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
            and isinstance(test.left, ast.Name)
        ):
            return test.left.id
    if isinstance(test, ast.Name):
        return test.id
    return None


def _name_used_by_any_sibling(
    name: str,
    tree: ast.Module,
    target_name: str,
    target_class: str | None,
) -> bool:
    for sib in _iter_sibling_funcs(tree, target_name, target_class):
        for node in ast.walk(sib):
            if isinstance(node, ast.Name) and node.id == name:
                return True
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == name:
                    return True
    return False


# ── Pure-constructor detection ────────────────────────────────────────


def _is_factory_name(name: str) -> bool:
    if not name or not name[0].islower():
        return False
    return any(name.startswith(p) for p in _FACTORY_PREFIXES)


def _is_pure_constructor_test(
    func: ast.FunctionDef, helper_names: set[str], pkg_symbols: set[str]
) -> bool:
    """True when *func* is a single-constructor call followed by a weak assert."""
    for stmt in ast.walk(func):
        if isinstance(
            stmt,
            ast.With | ast.AsyncWith | ast.Try | ast.For | ast.AsyncFor | ast.While,
        ):
            return False

    calls = _extract_calls(func.body, helper_names)
    if len(calls) != 1:
        return False
    c = calls[0]
    if not (c[0].isupper() or _is_factory_name(c)):
        return False

    for node in ast.walk(ast.Module(body=func.body, type_ignores=[])):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
        ):
            return True
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Name):
                return True
            if isinstance(node.test, ast.Compare):
                cmp = node.test
                if (
                    len(cmp.ops) == 1
                    and isinstance(cmp.ops[0], ast.IsNot)
                    and len(cmp.comparators) == 1
                    and isinstance(cmp.comparators[0], ast.Constant)
                    and cmp.comparators[0].value is None
                ):
                    return True
    return False


def _count_pure_constructor_siblings(
    tree: ast.Module,
    target_name: str,
    target_class: str | None,
    helper_names: set[str],
    pkg_symbols: set[str],
) -> int:
    count = 0
    for sib in _iter_sibling_funcs(tree, target_name, target_class):
        if _is_pure_constructor_test(sib, helper_names, pkg_symbols):
            count += 1
    return count


# ── Triage entry point ────────────────────────────────────────────────


def triage(  # noqa: PLR0911, PLR0912, PLR0913
    finding: Finding,
    *,
    tree: ast.Module,
    func: ast.FunctionDef,
    enclosing_class: str | None,
    helpers: list[ast.FunctionDef],
    pkg_symbols: set[str],
    contracts: set[str],
    test_file: Path,
    source_text: str = "",
) -> Verdict:
    """Return the verdict for *finding* inside *func*."""
    del source_text  # reserved for step4f (not ported in this ticket)
    helper_names = {h.name for h in helpers}

    # Step -2 — import + weak-assert smoke
    if is_import_smoke_test(func):
        if _is_contract_conformance_test(func, contracts):
            return Verdict(
                "STRENGTHEN",
                "step0c_contract_conformance",
                "import + isinstance against Protocol/ABC — contract test",
            )
        if _name_is_explicit_contract(func.name):
            return Verdict(
                "STRENGTHEN",
                "step0d_explicit_contract_name",
                f"name `{func.name}` declares explicit contract check",
            )
        if test_is_in_lazy_import_context(func, tree, test_file):
            return Verdict(
                "STRENGTHEN",
                "step_n2b_lazy_import_sut",
                "import IS the SUT (lazy/__getattr__/re-export) — keep",
            )
        return Verdict(
            "DELETE",
            "step_n2_import_smoke",
            "import smoke test: tautological by construction",
        )

    # Step -2c — top-level import re-tested with `is not None`, used by sibling
    if finding.pattern == "none_check_only":
        asserted = _asserted_name_is_not_none(func)
        if asserted and asserted in _collect_top_level_imports(tree):
            if not test_is_in_lazy_import_context(func, tree, test_file):
                if _name_used_by_any_sibling(
                    asserted, tree, func.name, enclosing_class
                ):
                    return Verdict(
                        "DELETE",
                        "step_n2c_toplevel_import_not_none",
                        f"`{asserted}` imported at top-level and used by "
                        f"siblings — `assert is not None` is redundant",
                    )

    siblings = _collect_siblings(
        tree, func.name, enclosing_class, helper_names, pkg_symbols
    )

    # Step -1 — no siblings
    if siblings.count == 0:
        return Verdict(
            "STRENGTHEN",
            "step_n1_no_siblings",
            "no sibling tests — cannot be redundant",
        )

    # Step 0 — self-compare
    if finding.pattern == "self_compare":
        return Verdict(
            "STRENGTHEN",
            "step0_self_compare",
            "self-compare tests determinism",
        )

    # Step 0d — explicit contract name
    if finding.pattern == "isinstance_only" and _name_is_explicit_contract(func.name):
        return Verdict(
            "STRENGTHEN",
            "step0d_explicit_contract_name",
            f"name `{func.name}` declares explicit contract check",
        )

    # Step 0c — isinstance against Protocol/ABC/TypedDict/stdlib ABC
    if finding.pattern == "isinstance_only" and _is_contract_conformance_test(
        func, contracts
    ):
        return Verdict(
            "STRENGTHEN",
            "step0c_contract_conformance",
            "isinstance against Protocol/ABC — contract test",
        )

    my_dominant = _dominant_call(func.body, helper_names, pkg_symbols)
    my_calls = set(_extract_calls(func.body, helper_names))

    # Step 1a — unique SUT (scoped to pkg_symbols so we don't treat
    # built-in constructors like object() as domain SUTs).
    if (
        my_dominant
        and my_dominant in pkg_symbols
        and my_dominant not in siblings.dominant_calls
        and my_calls
        and not (my_calls & siblings.all_calls)
    ):
        return Verdict(
            "STRENGTHEN",
            "step1a_unique_fn",
            f"SUT `{my_dominant}` not in siblings",
        )

    # Step 1b — same fn, different args (MUST precede 0b/0b2)
    if my_dominant and my_dominant in siblings.dominant_calls:
        my_sigs = {
            sig
            for name, sig in _extract_call_signatures(func.body, helper_names)
            if name == my_dominant
        }
        sib_sigs = {
            sig for sig in siblings.call_signatures if sig.startswith(f"{my_dominant}(")
        }
        if my_sigs and not (my_sigs & sib_sigs):
            return Verdict(
                "STRENGTHEN",
                "step1b_different_args",
                f"`{my_dominant}` called with different args",
            )

    # Step 0b — N-copies pure constructor+weak-assert, SAME args
    if finding.pattern in (
        "isinstance_only",
        "none_check_only",
    ) and _is_pure_constructor_test(func, helper_names, pkg_symbols):
        n_pure = _count_pure_constructor_siblings(
            tree, func.name, enclosing_class, helper_names, pkg_symbols
        )
        if n_pure >= 1:
            return Verdict(
                "DELETE",
                "step0b_n_copies_constructor",
                f"N-copies constructor+weak-assert ({n_pure + 1} similar)",
            )

    # Step 0b2 — impure sibling covers the ctor
    if finding.pattern in (
        "isinstance_only",
        "none_check_only",
    ) and _is_pure_constructor_test(func, helper_names, pkg_symbols):
        my_calls_here = _extract_calls(func.body, helper_names)
        if my_calls_here and my_calls_here[0] in pkg_symbols:
            my_ctor = my_calls_here[0]
            if my_ctor in siblings.all_calls:
                return Verdict(
                    "DELETE",
                    "step0b2_impure_sibling_covers_ctor",
                    f"pure weak check on `{my_ctor}` — sibling exercises "
                    f"the same constructor with stronger assertions",
                )

    # Step 5 — terminator (temporary until the full STRENGTHEN-side lands)
    reason = "no decisive signal — requires human review"
    if my_dominant:
        reason = f"`{my_dominant}` tested elsewhere but ambiguity remains"
    return Verdict("UNKNOWN", "step5_default_unknown", reason)
