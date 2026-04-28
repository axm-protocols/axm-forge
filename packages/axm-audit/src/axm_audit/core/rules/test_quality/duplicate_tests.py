"""Duplicate-tests rule — cluster likely-duplicate test functions.

Three clustering signals (S1/S2/S3) + six rescue anti-signals (P1-P6)
ported from the ``detect_duplicates.py`` prototype.
"""

from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import Field

from axm_audit.core.registry import register_rule
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.severity import Severity
from axm_audit.models.results import CheckResult

__all__ = [
    "DuplicateTestsCheckResult",
    "DuplicateTestsRule",
    "_jaccard_similarity",
    "_merge_clusters",
    "_p1_rescues",
    "_p2_rescues",
    "_p3_rescues",
    "_p4_rescues",
    "_p5_rescues",
    "_p6_rescues",
]


_P1_MIN_SYMDIFF = 2
_P3_MIN_TOKEN_LEN = 4
_P3_MAX_BODY = 4
_P4_MAX_BODY = 8
_P5_SETUP_DIVERGENCE_THRESHOLD = 0.5
_S2_HIGH_SIM = 0.95
_SCORE_PENALTY = 5
_MIN_PAIR = 2

# Names excluded from P6 candidate-SUT search: builtins, common test
# infrastructure, and ubiquitous library helpers that are almost never
# the actual SUT.  Underscore-prefixed names are also excluded
# dynamically (private helpers/fixtures).
_P6_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        # Builtins
        "len",
        "isinstance",
        "type",
        "repr",
        "str",
        "int",
        "float",
        "bool",
        "set",
        "list",
        "dict",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "next",
        "iter",
        "any",
        "all",
        "min",
        "max",
        "sum",
        "hasattr",
        "getattr",
        "setattr",
        "callable",
        "id",
        "vars",
        "print",
        "open",
        # Test infrastructure
        "MagicMock",
        "Mock",
        "patch",
        "fixture",
        "raises",
        "approx",
        "fail",
        "readouterr",
        # Common exceptions
        "FileNotFoundError",
        "ValueError",
        "TypeError",
        "KeyError",
        "AttributeError",
        "OSError",
        "Exception",
        "RuntimeError",
        "AssertionError",
        # Path / filesystem methods
        "Path",
        "mkdir",
        "touch",
        "exists",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "save",
        "close",
        # Misc method names that are rarely SUTs in test bodies
        "join",
        "replace",
        "find",
        "qn",
    }
)


class DuplicateTestsCheckResult(CheckResult):
    """:class:`CheckResult` with cluster metadata and a scoring field."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    score: int = 100

    model_config = {"extra": "forbid"}


@dataclass
class _TestFunc:
    file: str
    name: str
    line: int
    node: ast.FunctionDef
    call_sig: str = ""
    assert_pattern: str = ""
    stmt_set: frozenset[str] = field(default_factory=frozenset)
    setup_set: frozenset[str] = field(default_factory=frozenset)


# ── Statement-set similarity ──────────────────────────────────────────


_CONSTANT_RE = re.compile(r"Constant\([^()]*\)")
_NAME_RE = re.compile(r"Name\('[^']*',")


def _flatten_body(body: list[ast.stmt]) -> list[ast.stmt]:
    """Flatten compound statements (with/if/for/while/try) into their inner body."""
    out: list[ast.stmt] = []
    for stmt in body:
        match stmt:
            case ast.With() | ast.AsyncWith():
                out.extend(_flatten_body(stmt.body))
            case ast.If() | ast.For() | ast.While() | ast.AsyncFor():
                out.extend(_flatten_body(stmt.body))
                out.extend(_flatten_body(stmt.orelse))
            case ast.Try():
                out.extend(_flatten_body(stmt.body))
                for handler in stmt.handlers:
                    out.extend(_flatten_body(handler.body))
                out.extend(_flatten_body(stmt.orelse))
                out.extend(_flatten_body(stmt.finalbody))
            case _:
                out.append(stmt)
    return out


def _statement_set(node: ast.FunctionDef) -> frozenset[str]:
    """Normalized stmt shapes (constants + name ids replaced) as a set."""
    stmts: set[str] = set()
    for stmt in _flatten_body(node.body):
        try:
            dump = ast.dump(stmt, annotate_fields=False)
        except Exception:  # noqa: BLE001, S112
            continue
        dump = _CONSTANT_RE.sub("Constant(<C>)", dump)
        dump = _NAME_RE.sub("Name(<N>,", dump)
        stmts.add(dump)
    return frozenset(stmts)


def _normalize_dump(stmt: ast.stmt) -> str | None:
    try:
        dump = ast.dump(stmt, annotate_fields=False)
    except Exception:  # noqa: BLE001
        return None
    dump = _CONSTANT_RE.sub("Constant(<C>)", dump)
    dump = _NAME_RE.sub("Name(<N>,", dump)
    return dump


def _compute_setup_set(
    node: ast.FunctionDef, tainted: set[ast.Assign]
) -> frozenset[str]:
    """Set of normalized statement-dumps NOT participating in the assert chain.

    Builds on ``_statement_set`` semantics but excludes ``ast.Assign`` nodes
    in ``tainted`` and any ``ast.Assert`` statement.  Two tests with the
    same SUT call but radically different fixtures (e.g. ``git_coupled_files``
    cluster) produce disjoint setup-sets — used by P5 to demote false
    positives whose divergence lives entirely in the setup phase.
    """
    setup: set[str] = set()
    for stmt in _flatten_body(node.body):
        if isinstance(stmt, ast.Assert):
            continue
        if isinstance(stmt, ast.Assign) and stmt in tainted:
            continue
        dump = _normalize_dump(stmt)
        if dump is None:
            continue
        setup.add(dump)
    return frozenset(setup)


def _jaccard_similarity(
    a: set[str] | frozenset[str], b: set[str] | frozenset[str]
) -> float:
    """Jaccard similarity between two sets (1.0 when both are empty)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ── Fingerprints ──────────────────────────────────────────────────────


def _kwarg_value_token(value: ast.expr) -> str:
    """One-token fingerprint of a kwarg value.

    Scalar literals (``str``/``int``/``bool``/``None``) carry their actual
    value so that ``format="mermaid"`` and ``format="text"`` produce distinct
    tokens — branch-discriminating in dispatch tests.  Other shapes collapse
    to their AST type name.
    """
    if isinstance(value, ast.Constant):
        if isinstance(value.value, str):
            return f"'{value.value}'"
        if isinstance(value.value, (int, bool)) or value.value is None:
            return repr(value.value)
        return "<C>"
    return type(value).__name__


def _call_kwargs_fingerprint(call: ast.Call) -> str:
    """Sorted ``name=<value-token>`` pairs of *call*'s kwargs, joined by ``,``.

    Two calls with the same positional arity but different kwarg *names* or
    different scalar kwarg *values* exercise structurally distinct branches
    (e.g. ``execute(path=…)`` vs ``execute(path=…, format="mermaid")``;
    ``execute(format="mermaid")`` vs ``execute(format="text")``).  Encoding
    them lets the call signature discriminate.  ``**kwargs`` splat is encoded
    as ``**``.
    """
    pairs: list[str] = []
    for kw in call.keywords:
        name = kw.arg if kw.arg is not None else "**"
        pairs.append(f"{name}={_kwarg_value_token(kw.value)}")
    if not pairs:
        return ""
    return "|" + ",".join(sorted(pairs))


def _call_sig(call: ast.Call) -> str | None:
    kw = _call_kwargs_fingerprint(call)
    match call.func:
        case ast.Name(id=name):
            return f"{name}({len(call.args)}{kw})"
        case ast.Attribute(attr=attr, value=ast.Name(id=obj)):
            return f"{obj}.{attr}({len(call.args)}{kw})"
    return None


def _collect_asserted_names(node: ast.FunctionDef) -> set[str]:
    """Names referenced in ``assert`` expressions of ``node``."""
    asserted: set[str] = set()
    for child in ast.walk(node):
        if not (isinstance(child, ast.Assert) and child.test is not None):
            continue
        for sub in ast.walk(child.test):
            if isinstance(sub, ast.Name):
                asserted.add(sub.id)
    return asserted


def _is_tainted_assign(assign: ast.Assign, asserted: set[str]) -> bool:
    target = assign.targets[0]
    return isinstance(target, ast.Name) and target.id in asserted


def _propagate_call_args(call: ast.Call, asserted: set[str]) -> bool:
    """Add positional name args to ``asserted``; return True if any added."""
    added = False
    for arg in call.args:
        if isinstance(arg, ast.Name) and arg.id not in asserted:
            asserted.add(arg.id)
            added = True
    return added


def _collect_single_target_assigns(node: ast.FunctionDef) -> list[ast.Assign]:
    return [
        stmt
        for stmt in _flatten_body(node.body)
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
    ]


def _propagate_taint(
    node: ast.FunctionDef,
) -> tuple[set[str], set[ast.Assign]]:
    """Run taint propagation; return ``(call_sigs, tainted_assigns)``.

    Starts from names referenced in ``assert`` expressions and propagates
    the taint back through direct ``target = call(...)`` assignments,
    collecting each call's signature and the participating assigns.
    Two tests with different upstream calls in the chain produce
    different signatures; ``tainted_assigns`` is used by P5 to compute
    a setup-set fingerprint over the remaining (non-chain) statements.
    """
    asserted = _collect_asserted_names(node)
    assigns = _collect_single_target_assigns(node)

    sigs: set[str] = set()
    tainted: set[ast.Assign] = set()
    changed = True
    while changed:
        changed = False
        for assign in list(assigns):
            if not _is_tainted_assign(assign, asserted):
                continue
            if _process_tainted_assign(assign, asserted, sigs):
                changed = True
            tainted.add(assign)
            assigns.remove(assign)

    return sigs, tainted


def _process_tainted_assign(
    assign: ast.Assign,
    asserted: set[str],
    sigs: set[str],
) -> bool:
    if not isinstance(assign.value, ast.Call):
        return False
    sig = _call_sig(assign.value)
    if sig is not None:
        sigs.add(sig)
    return _propagate_call_args(assign.value, asserted)


def _expr_shape(expr: ast.expr) -> str:
    match expr:
        case ast.Subscript(value=val, slice=sl):
            return f"sub({_expr_shape(val)},[{_expr_shape(sl)}])"
        case ast.Attribute(attr=attr, value=val):
            return f"attr({_expr_shape(val)}.{attr})"
        case ast.Name(id=name):
            return f"name({name})"
        case ast.Call(func=func, args=args):
            return f"call({_expr_shape(func)},{len(args)})"
        case ast.Constant():
            return "<C>"
        case _:
            return type(expr).__name__


def _normalize_assert_expr(expr: ast.expr) -> str:
    match expr:
        case ast.Compare(left=left, ops=ops):
            op_names = [type(op).__name__ for op in ops]
            return f"cmp({_expr_shape(left)},{','.join(op_names)})"
        case ast.Call(func=func, args=args):
            return f"call({_expr_shape(func)},{len(args)})"
        case ast.UnaryOp(op=op, operand=operand):
            return f"unary({type(op).__name__},{_expr_shape(operand)})"
        case ast.BoolOp(op=op):
            return f"bool({type(op).__name__})"
        case _:
            return _expr_shape(expr)


def _compute_assert_pattern(node: ast.FunctionDef) -> str:
    """Deterministic signature of the asserts in *node*."""
    patterns: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assert) and child.test is not None:
            patterns.append(_normalize_assert_expr(child.test))
    return "|".join(sorted(patterns))


# ── Rescue anti-signals ───────────────────────────────────────────────


def _string_literals(node: ast.FunctionDef) -> set[str]:
    """Str/bytes literals in the body, excluding the leading docstring."""
    lits: set[str] = set()
    body = node.body
    skip_first = bool(
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
    for stmt in body[1:] if skip_first else body:
        for child in ast.walk(stmt):
            if isinstance(child, ast.Constant) and isinstance(
                child.value, (str, bytes)
            ):
                lits.add(repr(child.value))
    return lits


def _is_patch_call(call: ast.Call) -> bool:
    match call.func:
        case ast.Name(id="patch"):
            return True
        case ast.Attribute(attr=attr) if attr in {"patch", "object"}:
            return True
    return False


def _is_mocker_patch_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "mocker"
        and func.attr.startswith("patch")
    )


def _count_decorator_patches(node: ast.FunctionDef) -> int:
    return sum(
        1
        for dec in node.decorator_list
        if isinstance(dec, ast.Call) and _is_patch_call(dec)
    )


def _count_with_patches(node: ast.FunctionDef) -> int:
    count = 0
    for child in ast.walk(node):
        if not isinstance(child, ast.With):
            continue
        for item in child.items:
            if isinstance(item.context_expr, ast.Call) and _is_patch_call(
                item.context_expr
            ):
                count += 1
    return count


def _count_mocker_patches(node: ast.FunctionDef) -> int:
    return sum(
        1
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and _is_mocker_patch_call(child)
    )


def _patch_targets(node: ast.FunctionDef) -> tuple[int, int, int]:
    """Count patch usages in ``node``.

    Returns a tuple ``(decorator_patches, with_patches, mocker_patches)`` where
    each element is the number of ``patch``/``patch.object`` decorator calls,
    ``with patch(...)`` context managers, and ``mocker.patch*`` invocations
    found inside the function body, respectively.
    """
    return (
        _count_decorator_patches(node),
        _count_with_patches(node),
        _count_mocker_patches(node),
    )


def _p1_rescues(tests: list[_TestFunc]) -> bool:
    """P1 — pair differs on ≥ 2 distinct str/bytes literals per side."""
    if len(tests) < _MIN_PAIR:
        return False
    lits = [_string_literals(t.node) for t in tests]
    for a, b in combinations(lits, 2):
        if len(a - b) >= _P1_MIN_SYMDIFF and len(b - a) >= _P1_MIN_SYMDIFF:
            return True
    return False


def _p2_rescues(tests: list[_TestFunc]) -> bool:
    """P2 — pair exercises different ``(deco, with, mocker)`` patch shapes."""
    if len(tests) < _MIN_PAIR:
        return False
    targets = {_patch_targets(t.node) for t in tests}
    return len(targets) >= _MIN_PAIR


def _p3_rescues(tests: list[_TestFunc]) -> bool:
    """P3 — cross-file template pair on short bodies."""
    if len(tests) != _MIN_PAIR:
        return False
    a, b = tests
    stem_a = Path(a.file).stem.removeprefix("test_")
    stem_b = Path(b.file).stem.removeprefix("test_")
    toks_a = set(stem_a.split("_"))
    toks_b = set(stem_b.split("_"))
    diff = toks_a ^ toks_b
    if not any(len(tok) >= _P3_MIN_TOKEN_LEN for tok in diff):
        return False
    body_max = max(
        len(list(ast.iter_child_nodes(a.node))),
        len(list(ast.iter_child_nodes(b.node))),
    )
    return body_max <= _P3_MAX_BODY


def _p4_rescues(tests: list[_TestFunc]) -> bool:
    """P4 — intra-file body-size delta rescue on small bodies."""
    if len(tests) < _MIN_PAIR:
        return False
    sizes = {len(list(ast.iter_child_nodes(t.node))) for t in tests}
    if len(sizes) < _MIN_PAIR:
        return False
    return max(sizes) <= _P4_MAX_BODY


def _p5_rescues(
    tests: list[_TestFunc],
    threshold: float = _P5_SETUP_DIVERGENCE_THRESHOLD,
) -> bool:
    """P5 — semantic divergence lives in the test SETUP, not the call/assert.

    Compute the pairwise Jaccard between ``setup_set`` (statements not on
    the asserted call chain) for every pair of tests in the cluster.  If
    the *minimum* similarity is below ``threshold``, at least one pair has
    structurally distinct fixtures (different repo state, different mocked
    inputs, …) — same SUT and same assert shape are then a coincidence,
    not a true clone.  Demote to ``ambiguous_setup_divergence``.
    """
    if len(tests) < _MIN_PAIR:
        return False
    if any(not t.setup_set for t in tests):
        return False
    min_sim = 1.0
    for a, b in combinations(tests, 2):
        min_sim = min(min_sim, _jaccard_similarity(a.setup_set, b.setup_set))
    return min_sim < threshold


def _call_target_name(call: ast.Call) -> str | None:
    """Return the immediate name being called (``Name`` id or ``Attribute`` attr)."""
    match call.func:
        case ast.Name(id=name):
            return name
        case ast.Attribute(attr=attr):
            return attr
    return None


def _p6_eligible_sut(name: str) -> bool:
    """A candidate SUT must be public and not a builtin/fixture helper."""
    if name.startswith("_"):
        return False
    return name not in _P6_EXCLUDED_NAMES


def _p6_call_counts(node: ast.FunctionDef) -> Counter[str]:
    """Multiset of public, non-builtin call-target names in *node*'s body."""
    counts: Counter[str] = Counter()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_target_name(child)
        if name is not None and _p6_eligible_sut(name):
            counts[name] += 1
    return counts


def _p6_rescues(tests: list[_TestFunc]) -> bool:
    """P6 — a public SUT shared by all tests is called a different number of times.

    Two tests with the same call_sig and assert pattern can still exercise
    structurally distinct properties: idempotence (one call vs two), override
    (re-application), accumulation (state across multiple invocations).  When
    the *common* SUT (the function called by every test in the cluster) has
    different call counts across tests, the cluster is demoted to
    ``ambiguous_call_multiplicity``.

    The candidate SUT must be a *public* name (no leading underscore) and
    not a known builtin or test-infra helper, so that fixture/setup helpers
    like ``_make_plan`` or ``mkdir`` cannot trigger the rescue.
    """
    if len(tests) < _MIN_PAIR:
        return False
    per_test = [_p6_call_counts(t.node) for t in tests]
    common = set(per_test[0].keys())
    for counts in per_test[1:]:
        common &= set(counts.keys())
    for sut in common:
        if len({counts[sut] for counts in per_test}) >= _MIN_PAIR:
            return True
    return False


# ── Clustering ────────────────────────────────────────────────────────


def _pair_key(a: _TestFunc, b: _TestFunc) -> tuple[str, str]:
    ka = f"{a.file}::{a.line}::{a.name}"
    kb = f"{b.file}::{b.line}::{b.name}"
    return (ka, kb) if ka < kb else (kb, ka)


def _test_key(t: _TestFunc) -> str:
    return f"{t.file}::{t.line}::{t.name}"


def _test_entry(t: _TestFunc) -> dict[str, Any]:
    return {"file": t.file, "name": t.name, "line": t.line, "call_sig": t.call_sig}


def _classify_s1(tests: list[_TestFunc], sig: str, pattern: str) -> tuple[str, str]:
    if _p1_rescues(tests):
        return "ambiguous_distinct_literals", f"distinct literals rescue for SUT {sig}"
    if _p2_rescues(tests):
        return "ambiguous_patch_context", f"patch-context rescue for SUT {sig}"
    if _p5_rescues(tests):
        return (
            "ambiguous_setup_divergence",
            f"setup divergence rescue for SUT {sig}",
        )
    if _p6_rescues(tests):
        return (
            "ambiguous_call_multiplicity",
            f"call-multiplicity rescue for SUT {sig}",
        )
    tail = " + same asserts" if pattern != "<no-assert>" else ""
    return "signal1_call_assert", f"same SUT: {sig}{tail}"


def _classify_s2(tests: list[_TestFunc], name: str, sim: float) -> tuple[str, str]:
    if _p1_rescues(tests):
        return (
            "ambiguous_distinct_literals",
            f"distinct literals rescue (cross-file {name})",
        )
    if _p3_rescues(tests):
        return (
            "ambiguous_template_pair",
            f"template-pair rescue (cross-file {name})",
        )
    if _p2_rescues(tests):
        return (
            "ambiguous_patch_context",
            f"patch-context rescue (cross-file {name})",
        )
    return "signal2_cross_file_name", f"cross-file duplicate ({sim:.0%}): {name}"


def _classify_s3(tests: list[_TestFunc], sim: float) -> tuple[str, str]:
    if _p1_rescues(tests):
        return (
            "ambiguous_distinct_literals",
            f"distinct literals rescue (intra-file {sim:.0%})",
        )
    if _p2_rescues(tests):
        return (
            "ambiguous_patch_context",
            f"patch-context rescue (intra-file {sim:.0%})",
        )
    if _p4_rescues(tests):
        return (
            "ambiguous_body_size",
            f"body-size delta rescue (intra-file {sim:.0%})",
        )
    if _p5_rescues(tests):
        return (
            "ambiguous_setup_divergence",
            f"setup divergence rescue (intra-file {sim:.0%})",
        )
    if _p6_rescues(tests):
        return (
            "ambiguous_call_multiplicity",
            f"call-multiplicity rescue (intra-file {sim:.0%})",
        )
    return "signal3_intra_file_similarity", f"AST similarity {sim:.0%}"


def _try_emit_s2_pair(
    a: _TestFunc,
    b: _TestFunc,
    seen_pairs: set[tuple[str, str]],
) -> dict[str, Any] | None:
    """Return cluster dict if ``a``/``b`` form a valid S2 pair, else ``None``."""
    if a.file == b.file:
        return None
    pk = _pair_key(a, b)
    if pk in seen_pairs:
        return None
    sim = _jaccard_similarity(a.stmt_set, b.stmt_set)
    if sim < _S2_HIGH_SIM:
        return None
    signal, reason = _classify_s2([a, b], a.name, sim)
    seen_pairs.add(pk)
    return {
        "signal": signal,
        "reason": reason,
        "similarity": sim,
        "tests": [_test_entry(a), _test_entry(b)],
    }


def _is_valid_s2_group(group: list[_TestFunc]) -> bool:
    """Return ``True`` if group has ≥ _MIN_PAIR items spanning ≥ _MIN_PAIR files."""
    return len(group) >= _MIN_PAIR and len({t.file for t in group}) >= _MIN_PAIR


def _cluster_s2(
    tests: list[_TestFunc],
    seen_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """S2 — cross-file same-name with Jaccard ≥ ``_S2_HIGH_SIM``."""
    raw: list[dict[str, Any]] = []
    by_name: dict[str, list[_TestFunc]] = defaultdict(list)
    for t in tests:
        by_name[t.name].append(t)
    for group in by_name.values():
        if not _is_valid_s2_group(group):
            continue
        for a, b in combinations(group, 2):
            cluster = _try_emit_s2_pair(a, b, seen_pairs)
            if cluster is not None:
                raw.append(cluster)
    return raw


def _group_by_s1_key(
    tests: list[_TestFunc],
) -> dict[str, dict[str, list[_TestFunc]]]:
    """Group tests by ``call_sig`` then ``assert_pattern``."""
    by_call: dict[str, list[_TestFunc]] = defaultdict(list)
    for t in tests:
        if t.call_sig:
            by_call[t.call_sig].append(t)
    grouped: dict[str, dict[str, list[_TestFunc]]] = {}
    for sig, group in by_call.items():
        subgroups: dict[str, list[_TestFunc]] = defaultdict(list)
        for t in group:
            subgroups[t.assert_pattern or "<no-assert>"].append(t)
        grouped[sig] = subgroups
    return grouped


def _build_s1_cluster(
    subgroup: list[_TestFunc],
    sig: str,
    pattern: str,
    seen_pairs: set[tuple[str, str]],
) -> dict[str, Any] | None:
    """Build the S1 cluster dict for a single subgroup, or ``None`` if too small."""
    claimed: set[str] = set()
    for a, b in combinations(subgroup, 2):
        pk = _pair_key(a, b)
        if pk in seen_pairs:
            continue
        seen_pairs.add(pk)
        claimed.add(_test_key(a))
        claimed.add(_test_key(b))
    if len(claimed) < _MIN_PAIR:
        return None
    confirmed = [t for t in subgroup if _test_key(t) in claimed]
    signal, reason = _classify_s1(confirmed, sig, pattern)
    return {
        "signal": signal,
        "reason": reason,
        "similarity": 0.0,
        "tests": [_test_entry(t) for t in confirmed],
    }


def _emit_s1_clusters(
    groups: dict[str, dict[str, list[_TestFunc]]],
    seen_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Emit raw S1 cluster dicts for each ``(sig, pattern)`` group."""
    raw: list[dict[str, Any]] = []
    for sig, subgroups in groups.items():
        for pattern, subgroup in subgroups.items():
            if len(subgroup) < _MIN_PAIR:
                continue
            cluster = _build_s1_cluster(subgroup, sig, pattern, seen_pairs)
            if cluster is not None:
                raw.append(cluster)
    return raw


def _cluster_s1(
    tests: list[_TestFunc],
    seen_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """S1 — same ``call_sig`` and same ``assert_pattern``."""
    return _emit_s1_clusters(_group_by_s1_key(tests), seen_pairs)


def _cluster_s3(
    tests: list[_TestFunc],
    threshold: float,
    seen_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """S3 — intra-file Jaccard ≥ ``threshold``."""
    raw: list[dict[str, Any]] = []
    by_file: dict[str, list[_TestFunc]] = defaultdict(list)
    for t in tests:
        by_file[t.file].append(t)
    for file_tests in by_file.values():
        if len(file_tests) < _MIN_PAIR:
            continue
        for a, b in combinations(file_tests, 2):
            pk = _pair_key(a, b)
            if pk in seen_pairs:
                continue
            sim = _jaccard_similarity(a.stmt_set, b.stmt_set)
            if sim < threshold:
                continue
            signal, reason = _classify_s3([a, b], sim)
            raw.append(
                {
                    "signal": signal,
                    "reason": reason,
                    "similarity": sim,
                    "tests": [_test_entry(a), _test_entry(b)],
                }
            )
            seen_pairs.add(pk)
    return raw


def _cluster(tests: list[_TestFunc], threshold: float) -> list[dict[str, Any]]:
    """Return merged cluster dicts for *tests* across S1/S2/S3 signals."""
    seen_pairs: set[tuple[str, str]] = set()
    raw: list[dict[str, Any]] = []
    raw.extend(_cluster_s2(tests, seen_pairs))
    raw.extend(_cluster_s1(tests, seen_pairs))
    raw.extend(_cluster_s3(tests, threshold, seen_pairs))
    return _merge_clusters(raw)


def _build_union_find(
    clusters: list[dict[str, Any]],
) -> dict[int, list[int]]:
    """Return ``{root: [indices]}`` after union-find over shared tests."""
    test_to_idx: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for i, cluster in enumerate(clusters):
        for t in cluster.get("tests", []):
            key = (t.get("file"), t.get("name"), t.get("line", 0))
            test_to_idx[key].append(i)

    parent = list(range(len(clusters)))

    def find(x: int) -> int:
        """Return the root of ``x`` with path compression."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        """Merge the components containing ``x`` and ``y``."""
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for indices in test_to_idx.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(clusters)):
        groups[find(i)].append(i)
    return groups


def _pick_merged_signal(signals: list[str]) -> str:
    """Return the dominant signal for a merged group."""
    unique_signals = list(dict.fromkeys(signals))
    ambiguous = [s for s in unique_signals if s.startswith("ambiguous_")]
    if ambiguous:
        return ambiguous[0] if len(ambiguous) == 1 else "ambiguous_multi"
    if len(unique_signals) == 1:
        return unique_signals[0]
    if len(unique_signals) >= _MIN_PAIR:
        return "multi_signal"
    return ""


def _aggregate_group(
    clusters: list[dict[str, Any]],
    indices: list[int],
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], list[str], list[str], float]:
    """Collapse a union-find group into (tests_by_key, reasons, signals, max_sim)."""
    tests_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    reasons: list[str] = []
    signals: list[str] = []
    max_sim = 0.0
    for idx in indices:
        cluster = clusters[idx]
        if reason := cluster.get("reason"):
            reasons.append(reason)
        if signal := cluster.get("signal"):
            signals.append(signal)
        max_sim = max(max_sim, cluster.get("similarity") or 0.0)
        for t in cluster.get("tests", []):
            key = (t.get("file"), t.get("name"), t.get("line", 0))
            tests_by_key[key] = t
    return tests_by_key, reasons, signals, max_sim


def _merge_clusters(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union-find merge; ambiguous sub-clusters dominate the merged signal."""
    if not clusters:
        return []

    groups = _build_union_find(clusters)
    merged: list[dict[str, Any]] = []
    for indices in groups.values():
        tests_by_key, reasons, signals, max_sim = _aggregate_group(clusters, indices)
        if len(tests_by_key) < _MIN_PAIR:
            continue
        unique_reasons = list(dict.fromkeys(reasons))
        merged.append(
            {
                "signal": _pick_merged_signal(signals),
                "reason": " + ".join(unique_reasons[:3]),
                "similarity": max_sim,
                "tests": list(tests_by_key.values()),
            }
        )
    return sorted(merged, key=lambda c: -len(c["tests"]))


# ── Buckets & scoring ─────────────────────────────────────────────────


def _pairs_in_cluster(n: int) -> int:
    return n * (n - 1) // 2


def _buckets(
    tests: list[_TestFunc], clusters: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    clustered_keys: set[tuple[str, str]] = set()
    ambiguous_keys: set[tuple[str, str]] = set()
    for cluster in clusters:
        signal = cluster["signal"]
        for t in cluster["tests"]:
            key = (t["file"], t["name"])
            if signal.startswith("ambiguous_"):
                ambiguous_keys.add(key)
            else:
                clustered_keys.add(key)

    out: dict[str, list[dict[str, Any]]] = {
        "CLUSTERED": [],
        "AMBIGUOUS": [],
        "UNIQUE": [],
    }
    for t in tests:
        key = (t.file, t.name)
        entry = {"file": t.file, "name": t.name, "line": t.line}
        if key in clustered_keys:
            out["CLUSTERED"].append(entry)
        elif key in ambiguous_keys:
            out["AMBIGUOUS"].append(entry)
        else:
            out["UNIQUE"].append(entry)
    return out


# ── Collection ────────────────────────────────────────────────────────


def _collect_tests(project_path: Path) -> list[_TestFunc]:
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        return []
    out: list[_TestFunc] = []
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            source = test_file.read_text()
            tree = ast.parse(source, filename=str(test_file))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = str(test_file.relative_to(project_path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            ):
                continue
            tf = _TestFunc(file=rel, name=node.name, line=node.lineno, node=node)
            sigs, tainted = _propagate_taint(node)
            tf.call_sig = ">".join(sorted(sigs))
            tf.assert_pattern = _compute_assert_pattern(node)
            tf.stmt_set = _statement_set(node)
            tf.setup_set = _compute_setup_set(node, tainted)
            out.append(tf)
    return out


# ── Rule ──────────────────────────────────────────────────────────────


@register_rule("test_quality")
@dataclass
class DuplicateTestsRule(ProjectRule):
    """Cluster likely-duplicate test functions via structural signals."""

    ast_similarity_threshold: float = 0.8

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_DUPLICATE_TESTS"

    def check(self, project_path: Path) -> DuplicateTestsCheckResult:
        """Cluster duplicate tests in ``project_path`` and return verdicts."""
        tests = _collect_tests(project_path)
        if not tests:
            return DuplicateTestsCheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="no tests found",
                severity=Severity.INFO,
                score=100,
                metadata={
                    "clusters": [],
                    "buckets": {"CLUSTERED": [], "AMBIGUOUS": [], "UNIQUE": []},
                },
            )

        clusters = _cluster(tests, self.ast_similarity_threshold)
        buckets = _buckets(tests, clusters)
        n_clustered_pairs = sum(
            _pairs_in_cluster(len(c["tests"]))
            for c in clusters
            if not c["signal"].startswith("ambiguous_")
        )
        score = max(0, 100 - n_clustered_pairs * _SCORE_PENALTY)
        passed = n_clustered_pairs == 0
        if not clusters:
            message = "no duplicate-test clusters found"
        else:
            message = (
                f"{len(clusters)} cluster(s), {n_clustered_pairs} clustered pair(s)"
            )
        return DuplicateTestsCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            score=score,
            metadata={"clusters": clusters, "buckets": buckets},
        )
