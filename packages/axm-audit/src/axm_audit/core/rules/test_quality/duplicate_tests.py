"""Duplicate-tests rule — cluster likely-duplicate test functions.

Three clustering signals (S1/S2/S3) + six rescue anti-signals (P1-P6)
ported from the ``detect_duplicates.py`` prototype.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import TypedDict

from pydantic import Field

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "DuplicateTestsCheckResult",
    "DuplicateTestsRule",
    "_cluster_hash",
    "_jaccard_similarity",
    "_p1_rescues",
    "_p2_rescues",
    "_p3_rescues",
    "_p4_rescues",
    "_p5_rescues",
    "_p6_rescues",
    "_p7_rescues",
    "_slim_clusters",
    "render_clusters_text",
]


class _TestEntry(TypedDict, total=False):
    """Serialized test-function record used inside cluster payloads."""

    file: str
    name: str
    line: int
    call_sig: str


class _Cluster(TypedDict, total=False):
    """Cluster payload exposed via :class:`DuplicateTestsCheckResult.metadata`."""

    signal: str
    reason: str
    similarity: float
    members: list[_TestEntry]
    cluster_hash: str
    acknowledged: bool


@dataclass
class _DuplicateTestsConfig:
    """Acknowledgement config loaded from ``pyproject.toml``.

    Each entry in ``acknowledged`` is a dict ``{"hash": str, "reason": str}``.
    ``error`` is populated on malformed TOML or wrong schema; never raises.
    """

    acknowledged: list[dict[str, str]]
    error: str | None = None


_HASH_LEN = 12
_HASH_HEX_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def _cluster_hash(cluster: _Cluster) -> str:
    """Compute a stable 12-hex-char hash of a cluster's ``(file, name)`` set.

    The hash is order-independent (members are sorted before serialization)
    and line-independent (only ``file`` and ``name`` participate). This makes
    the hash robust to line drift while remaining sensitive to membership
    changes — the exact composition is the acknowledgement contract.
    """
    members: list[list[str]] = sorted(
        [str(t.get("file", "")), str(t.get("name", ""))]
        for t in cluster.get("members", [])
    )
    blob = json.dumps(members, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:_HASH_LEN]


def _load_duplicate_tests_config(project_path: Path) -> _DuplicateTestsConfig:
    """Read ``[tool.axm-audit.duplicate_tests].acknowledged`` from pyproject.

    Missing file/section → empty list. Malformed TOML or wrong schema →
    empty list + ``error``, never raises.

    Sample::

        [[tool.axm-audit.duplicate_tests.acknowledged]]
        hash = "a1b2c3d4e5f6"
        reason = "validated: distinct fixtures, parametrize would hurt"
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.is_file():
        return _DuplicateTestsConfig(acknowledged=[])
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        return _DuplicateTestsConfig(
            acknowledged=[],
            error=f"malformed pyproject.toml: {exc}",
        )
    section: object = (
        data.get("tool", {}).get("axm-audit", {}).get("duplicate_tests", {})
        if isinstance(data, dict)
        else {}
    )
    if not isinstance(section, dict) or "acknowledged" not in section:
        return _DuplicateTestsConfig(acknowledged=[])
    raw = section["acknowledged"]
    if not isinstance(raw, list):
        return _DuplicateTestsConfig(
            acknowledged=[],
            error=(
                "[tool.axm-audit.duplicate_tests] acknowledged must be a list "
                "of tables (schema error)"
            ),
        )
    parsed: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            error = "acknowledged entry must be a table (schema error)"
        elif not isinstance(entry.get("hash"), str) or not _HASH_HEX_PATTERN.match(
            entry.get("hash", "")
        ):
            error = "acknowledged.hash must be a 12-char hex string (schema error)"
        elif (
            not isinstance(entry.get("reason"), str)
            or not str(entry.get("reason", "")).strip()
        ):
            error = "acknowledged.reason must be a non-empty string (schema error)"
        else:
            error = None
        if error is not None:
            return _DuplicateTestsConfig(acknowledged=[], error=error)
        parsed.append({"hash": entry["hash"], "reason": entry["reason"]})
    return _DuplicateTestsConfig(acknowledged=parsed)


_RescuePredicate = Callable[[list["_TestFunc"]], bool]


_P1_MIN_SYMDIFF = 2
_P3_MIN_TOKEN_LEN = 4
_P3_MAX_BODY = 4
_P4_MAX_BODY = 8
_P10_LINE_DIST = 200
_P10_HIGH_JACCARD = 0.85
_P10_MIN_SHARED = 3
_P5_SETUP_DIVERGENCE_THRESHOLD = 0.5
_S2_HIGH_SIM = 0.95
_SCORE_PENALTY = 5
_MIN_PAIR = 2
_MAX_TEXT_CLUSTERS = 10
_MAX_MEMBERS_INLINE = 5


def _render_cluster_members(members: list[_TestEntry]) -> str:
    shown = members[:_MAX_MEMBERS_INLINE]
    files = {m.get("file", "") for m in shown}
    if len(files) == 1:
        file = next(iter(files))
        names = ", ".join(m.get("name", "") for m in shown)
        return f"{file}::{names}" if file else names
    return ", ".join(f"{m.get('file', '')}::{m.get('name', '')}" for m in shown)


def render_clusters_text(
    clusters: list[_Cluster],
    stale_acknowledged: list[dict[str, str]] | None = None,
) -> str:
    """Render top-N clusters (signal + ambiguous) as a compact bullet list.

    When ``stale_acknowledged`` is provided, append one warning line per
    stale entry of the form
    ``⚠ stale acknowledged cluster: <hash> (<reason>)``. Stale warnings
    are suffix-only and never affect ``passed`` / ``score`` / ``severity``.
    """
    ordered = sorted(
        clusters,
        key=lambda c: (-len(c.get("members", [])), c.get("signal", "")),
    )
    lines: list[str] = []
    for cluster in ordered[:_MAX_TEXT_CLUSTERS]:
        members = cluster.get("members", [])
        suffix = "…" if len(members) > _MAX_MEMBERS_INLINE else ""
        label = _render_cluster_members(members)
        lines.append(
            f"• cluster[{cluster.get('signal', '')}] "
            f"{len(members)} tests: {label}{suffix}"
        )
    if len(ordered) > _MAX_TEXT_CLUSTERS:
        lines.append(f"(+{len(ordered) - _MAX_TEXT_CLUSTERS} more clusters)")
    for entry in stale_acknowledged or []:
        lines.append(
            f"⚠ stale acknowledged cluster: {entry.get('hash', '')} "
            f"({entry.get('reason', '')})"
        )
    return "\n".join(lines)


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


class DuplicateTestsCheckResult(CheckResult):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """:class:`CheckResult` with cluster metadata.

    ``metadata`` keys:

    * ``clusters`` — list of cluster payloads, each with ``cluster_hash``,
      a ``members`` list of test entries, and an optional ``acknowledged``
      flag (``True`` when the hash is present in
      ``[[tool.axm-audit.duplicate_tests.acknowledged]]``). The cluster
      shape exposes ``members`` only; the legacy ``tests`` alias was
      removed in axm-1728 — consumers reading ``cluster["tests"]`` get
      a ``KeyError`` by design.
    * ``bucket_counts`` — CLUSTERED / AMBIGUOUS / UNIQUE test counts.
    * ``stale_acknowledged`` — acknowledgement entries (``{hash, reason}``)
      whose hash no longer matches any vivant cluster. Informational only:
      does not affect ``passed`` / ``score`` / ``severity``.
    * ``config_error`` — present when ``pyproject.toml`` is malformed or
      the ``[tool.axm-audit.duplicate_tests]`` schema is invalid. The audit
      falls back to "no acknowledgements" rather than crashing.
    """

    metadata: dict[str, object] = Field(default_factory=dict)

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
    class_name: str | None = None
    has_raises_block: bool = False


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
        case ast.Attribute(
            attr=attr,
            value=ast.Attribute(attr=mid, value=ast.Name(id=base)),
        ):
            return f"{base}.{mid}.{attr}({len(call.args)}{kw})"
    return None


def _is_pytest_raises_call(expr: ast.expr) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        return isinstance(func.value, ast.Name) and func.value.id == "pytest"
    return isinstance(func, ast.Name) and func.id == "raises"


def _has_pytest_raises_block(node: ast.FunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.With) and any(
            _is_pytest_raises_call(item.context_expr) for item in child.items
        ):
            return True
    return False


def collect_assert_call_sigs(node: ast.FunctionDef) -> set[str]:
    """Return ``_call_sig`` set for every :class:`ast.Call` inside an assert.

    Tests written as ``assert helper(args) == expected`` would otherwise have
    an empty ``call_sig`` (the taint-propagation pass only follows assigns).
    Including these calls lets S1/S2 group such tests by SUT.
    """
    out: set[str] = set()
    for parent in ast.walk(node):
        if not isinstance(parent, ast.Assert):
            continue
        for child in ast.walk(parent):
            if isinstance(child, ast.Call):
                sig = _call_sig(child)
                if sig is not None:
                    out.add(sig)
    return out


def _collect_raises_call_sigs(node: ast.FunctionDef) -> set[str]:
    sigs: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.With):
            continue
        if not any(_is_pytest_raises_call(item.context_expr) for item in child.items):
            continue
        for stmt in child.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                sig = _call_sig(stmt.value)
                if sig is not None:
                    sigs.add(sig)
    return sigs


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


def _p7_eligible_sut(name: str) -> bool:
    """A P7 candidate SUT is anything not a known builtin/test-infra helper.

    Looser than ``_p6_eligible_sut``: leading-underscore names are *kept*
    because internal entry points (``_shift_ppr_tracking_table``,
    ``_format_json``…) are legitimately distinct SUTs.  P6 has to exclude
    them to avoid false rescues based on fixture helpers; P7 has to keep
    them to detect distinct internal SUTs.
    """
    return name not in _P6_EXCLUDED_NAMES


def _p7_sut_set(node: ast.FunctionDef) -> frozenset[str]:
    """Set of non-builtin direct call-target names in *node*'s body."""
    out: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_target_name(child)
        if name is not None and _p7_eligible_sut(name):
            out.add(name)
    return frozenset(out)


def _p8_rescues(tests: list[_TestFunc]) -> bool:
    """P8 — clustered tests live in distinct parent classes."""
    if len(tests) < _MIN_PAIR:
        return False
    classes = {t.class_name for t in tests}
    if None in classes:
        return False
    return len(classes) >= _MIN_PAIR


def _p9_rescues(tests: list[_TestFunc]) -> bool:
    """P9 — only some clustered tests wrap their body in ``pytest.raises``."""
    if len(tests) < _MIN_PAIR:
        return False
    flags = {t.has_raises_block for t in tests}
    return len(flags) >= _MIN_PAIR


def _asserted_attr_names(node: ast.FunctionDef) -> set[str]:
    """Return the set of attribute names appearing inside assert expressions."""
    out: set[str] = set()
    for parent in ast.walk(node):
        if not isinstance(parent, ast.Assert):
            continue
        for child in ast.walk(parent):
            if isinstance(child, ast.Attribute):
                out.add(child.attr)
    return out


def _pair_is_very_strong(a: _TestFunc, b: _TestFunc) -> bool:
    """True if ``a``/``b`` carry a very strong direct duplication signal.

    A pair bypasses the locality rescue when any of the following holds:

    - ``stmt_set`` Jaccard ≥ :data:`_P10_HIGH_JACCARD`,
    - they share at least :data:`_P10_MIN_SHARED` asserted attribute names, or
    - they have the same non-empty ``call_sig`` and share at least
      :data:`_P10_MIN_SHARED` string literals.
    """
    if _jaccard_similarity(a.stmt_set, b.stmt_set) >= _P10_HIGH_JACCARD:
        return True
    shared_attrs = _asserted_attr_names(a.node) & _asserted_attr_names(b.node)
    if len(shared_attrs) >= _P10_MIN_SHARED:
        return True
    if a.call_sig and a.call_sig == b.call_sig:
        shared_lits = _string_literals(a.node) & _string_literals(b.node)
        if len(shared_lits) >= _P10_MIN_SHARED:
            return True
    return False


def p10_rescues(tests: list[_TestFunc]) -> bool:
    """Locality rescue: demote when all pairs are far apart with no strong signal.

    Returns True iff every pair in ``tests`` has line distance greater than
    :data:`_P10_LINE_DIST` AND no pair carries a very strong direct signal
    (:func:`_pair_is_very_strong`). Tests that match this pattern are almost
    always coincidental matches the user does not want flagged firmly.
    """
    if len(tests) < _MIN_PAIR:
        return False
    for a, b in combinations(tests, 2):
        if abs(a.line - b.line) <= _P10_LINE_DIST:
            return False
        if _pair_is_very_strong(a, b):
            return False
    return True


def _p7_rescues(tests: list[_TestFunc]) -> bool:
    """P7 — tests' direct-call SUT sets are not in subset relation.

    For a pair of tests, if neither side's set of direct calls is a
    subset of the other, they exercise structurally distinct entry
    points — even when the AST skeleton is otherwise identical.  This
    is the smoke-test failure mode where a side-effecting SUT does not
    appear on the assert chain (so ``call_sig`` captures a fixture
    builder instead of the real entry point), and S3 would otherwise
    cluster ``fill_highlight`` with ``_shift_ppr_tracking_table``.

    The check is *symmetric difference*-based, not strict equality:
    when set A ⊆ B (or vice-versa), the smaller set is interpreted as a
    parametrised slice of the larger one — keep clustering (a legitimate
    parametrised cluster usually has a near-equal call set).  Demote
    only when each side has a SUT the other lacks.
    """
    if len(tests) < _MIN_PAIR:
        return False
    sut_sets = [_p7_sut_set(t.node) for t in tests]
    for a, b in combinations(sut_sets, 2):
        if (a - b) and (b - a):
            return True
    return False


# ── Clustering ────────────────────────────────────────────────────────


def _pair_key(a: _TestFunc, b: _TestFunc) -> tuple[str, str]:
    """Return an order-independent identity key for a pair of test functions."""
    ka = f"{a.file}::{a.line}::{a.name}"
    kb = f"{b.file}::{b.line}::{b.name}"
    return (ka, kb) if ka < kb else (kb, ka)


def _test_key(t: _TestFunc) -> str:
    return f"{t.file}::{t.line}::{t.name}"


def _test_entry(t: _TestFunc) -> _TestEntry:
    """Serialize a test function into the cluster payload shape."""
    return {"file": t.file, "name": t.name, "line": t.line, "call_sig": t.call_sig}


_S1_RESCUES: tuple[tuple[_RescuePredicate, str, str], ...] = (
    (_p1_rescues, "ambiguous_distinct_literals", "distinct literals rescue for SUT"),
    (_p2_rescues, "ambiguous_patch_context", "patch-context rescue for SUT"),
    (_p5_rescues, "ambiguous_setup_divergence", "setup divergence rescue for SUT"),
    (_p6_rescues, "ambiguous_call_multiplicity", "call-multiplicity rescue for SUT"),
    (
        _p7_rescues,
        "ambiguous_distinct_sut",
        "distinct public SUT rescue for shared sig",
    ),
    (_p8_rescues, "ambiguous_distinct_class", "distinct parent class rescue for SUT"),
    (
        _p9_rescues,
        "ambiguous_raises_divergence",
        "pytest.raises divergence rescue for SUT",
    ),
    (p10_rescues, "ambiguous_locality", "locality rescue for SUT"),
)


def _classify_s1(tests: list[_TestFunc], sig: str, pattern: str) -> tuple[str, str]:
    for predicate, signal, label in _S1_RESCUES:
        if predicate(tests):
            return signal, f"{label} {sig}"
    tail = " + same asserts" if pattern != "<no-assert>" else ""
    return "signal1_call_assert", f"same SUT: {sig}{tail}"


_S2_RESCUES: tuple[tuple[_RescuePredicate, str, str], ...] = (
    (_p1_rescues, "ambiguous_distinct_literals", "distinct literals rescue"),
    (_p3_rescues, "ambiguous_template_pair", "template-pair rescue"),
    (_p2_rescues, "ambiguous_patch_context", "patch-context rescue"),
    (_p7_rescues, "ambiguous_distinct_sut", "distinct public SUT rescue"),
    (_p8_rescues, "ambiguous_distinct_class", "distinct parent class rescue"),
    (_p9_rescues, "ambiguous_raises_divergence", "pytest.raises divergence rescue"),
)


def _classify_s2(tests: list[_TestFunc], name: str, sim: float) -> tuple[str, str]:
    for predicate, signal, label in _S2_RESCUES:
        if predicate(tests):
            return signal, f"{label} (cross-file {name})"
    return "signal2_cross_file_name", f"cross-file duplicate ({sim:.0%}): {name}"


_S3_RESCUES: tuple[
    tuple[_RescuePredicate, str, str],
    ...,
] = (
    (_p1_rescues, "ambiguous_distinct_literals", "distinct literals rescue"),
    (_p2_rescues, "ambiguous_patch_context", "patch-context rescue"),
    (_p4_rescues, "ambiguous_body_size", "body-size delta rescue"),
    (_p5_rescues, "ambiguous_setup_divergence", "setup divergence rescue"),
    (_p6_rescues, "ambiguous_call_multiplicity", "call-multiplicity rescue"),
    (_p7_rescues, "ambiguous_distinct_sut", "distinct public SUT rescue"),
    (_p8_rescues, "ambiguous_distinct_class", "distinct parent class rescue"),
    (_p9_rescues, "ambiguous_raises_divergence", "pytest.raises divergence rescue"),
    (p10_rescues, "ambiguous_locality", "locality rescue (intra-file)"),
)


def _classify_s3(tests: list[_TestFunc], sim: float) -> tuple[str, str]:
    for predicate, signal, label in _S3_RESCUES:
        if predicate(tests):
            return signal, f"{label} (intra-file {sim:.0%})"
    return "signal3_intra_file_similarity", f"AST similarity {sim:.0%}"


def _try_emit_s2_pair(
    a: _TestFunc,
    b: _TestFunc,
    seen_pairs: set[tuple[str, str]],
) -> _Cluster | None:
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
        "members": [_test_entry(a), _test_entry(b)],
    }


def _is_valid_s2_group(group: list[_TestFunc]) -> bool:
    """Return ``True`` if group has ≥ _MIN_PAIR items spanning ≥ _MIN_PAIR files."""
    return len(group) >= _MIN_PAIR and len({t.file for t in group}) >= _MIN_PAIR


def _cluster_s2(
    tests: list[_TestFunc],
    seen_pairs: set[tuple[str, str]],
) -> list[_Cluster]:
    """S2 — cross-file same-name with Jaccard ≥ ``_S2_HIGH_SIM``."""
    raw: list[_Cluster] = []
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
) -> _Cluster | None:
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
        "members": [_test_entry(t) for t in confirmed],
    }


def _emit_s1_clusters(
    groups: dict[str, dict[str, list[_TestFunc]]],
    seen_pairs: set[tuple[str, str]],
) -> list[_Cluster]:
    """Emit raw S1 cluster dicts for each ``(sig, pattern)`` group."""
    raw: list[_Cluster] = []
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
) -> list[_Cluster]:
    """S1 — same ``call_sig`` and same ``assert_pattern``."""
    return _emit_s1_clusters(_group_by_s1_key(tests), seen_pairs)


def _cluster_s3(
    tests: list[_TestFunc],
    threshold: float,
    seen_pairs: set[tuple[str, str]],
) -> list[_Cluster]:
    """S3 — intra-file Jaccard ≥ ``threshold``."""
    raw: list[_Cluster] = []
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
                    "members": [_test_entry(a), _test_entry(b)],
                }
            )
            seen_pairs.add(pk)
    return raw


def _group_by_call_sig(tests: list[_TestFunc]) -> dict[str, list[_TestFunc]]:
    by_sig: dict[str, list[_TestFunc]] = defaultdict(list)
    for t in tests:
        if t.call_sig:
            by_sig[t.call_sig].append(t)
    return by_sig


def _new_pairs_for_group(
    group: list[_TestFunc],
    seen_pairs: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    if len(group) < _MIN_PAIR:
        return []
    if len({t.has_raises_block for t in group}) < _MIN_PAIR:
        return []
    return [
        _pair_key(a, b)
        for a, b in combinations(group, 2)
        if _pair_key(a, b) not in seen_pairs
    ]


def _build_cluster(sig: str, group: list[_TestFunc]) -> _Cluster:
    return {
        "signal": "ambiguous_raises_divergence",
        "reason": f"pytest.raises divergence rescue for SUT {sig}",
        "similarity": 0.0,
        "members": [_test_entry(t) for t in group],
    }


def _cluster_raises_divergence(
    tests: list[_TestFunc],
    seen_pairs: set[tuple[str, str]],
) -> list[_Cluster]:
    """Emit ambiguous clusters for tests sharing call_sig but divergent raises usage."""
    raw: list[_Cluster] = []
    for sig, group in _group_by_call_sig(tests).items():
        pairs = _new_pairs_for_group(group, seen_pairs)
        if not pairs:
            continue
        seen_pairs.update(pairs)
        raw.append(_build_cluster(sig, group))
    return raw


def _cluster(tests: list[_TestFunc], threshold: float) -> list[_Cluster]:
    """Return merged cluster dicts for *tests* across S1/S2/S3 signals."""
    seen_pairs: set[tuple[str, str]] = set()
    raw: list[_Cluster] = []
    raw.extend(_cluster_s2(tests, seen_pairs))
    raw.extend(_cluster_s1(tests, seen_pairs))
    raw.extend(_cluster_s3(tests, threshold, seen_pairs))
    raw.extend(_cluster_raises_divergence(tests, seen_pairs))
    return merge_clusters(raw)


def _build_union_find(
    clusters: list[_Cluster],
) -> dict[int, list[int]]:
    """Return ``{root: [indices]}`` after union-find over shared tests."""
    test_to_idx: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for i, cluster in enumerate(clusters):
        for t in cluster.get("members", []):
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
    clusters: list[_Cluster],
    indices: list[int],
) -> tuple[dict[tuple[object, ...], _TestEntry], list[str], list[str], float]:
    """Collapse a union-find group into (tests_by_key, reasons, signals, max_sim)."""
    tests_by_key: dict[tuple[object, ...], _TestEntry] = {}
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
        for t in cluster.get("members", []):
            key = (t.get("file"), t.get("name"), t.get("line", 0))
            tests_by_key[key] = t
    return tests_by_key, reasons, signals, max_sim


def merge_clusters(clusters: list[_Cluster]) -> list[_Cluster]:
    """Union-find merge; ambiguous sub-clusters dominate the merged signal."""
    if not clusters:
        return []

    groups = _build_union_find(clusters)
    merged: list[_Cluster] = []
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
                "members": list(tests_by_key.values()),
            }
        )
    return sorted(merged, key=lambda c: -len(c["members"]))


# ── Buckets & scoring ─────────────────────────────────────────────────


def _pairs_in_cluster(n: int) -> int:
    return n * (n - 1) // 2


_REASON_MAX_LEN = 200


def _bucket_counts(tests: list[_TestFunc], clusters: list[_Cluster]) -> dict[str, int]:
    """Aggregate test classification counts (CLUSTERED/AMBIGUOUS/UNIQUE)."""
    clustered_keys: set[tuple[str, str]] = set()
    ambiguous_keys: set[tuple[str, str]] = set()
    for cluster in clusters:
        signal = cluster["signal"]
        for t in cluster["members"]:
            key = (t["file"], t["name"])
            if signal.startswith("ambiguous_"):
                ambiguous_keys.add(key)
            else:
                clustered_keys.add(key)

    counts = {"CLUSTERED": 0, "AMBIGUOUS": 0, "UNIQUE": 0}
    for tf in tests:
        key = (tf.file, tf.name)
        if key in clustered_keys:
            counts["CLUSTERED"] += 1
        elif key in ambiguous_keys:
            counts["AMBIGUOUS"] += 1
        else:
            counts["UNIQUE"] += 1
    return counts


def _slim_clusters(clusters: list[_Cluster]) -> list[_Cluster]:
    """Project clusters to the minimal payload exposed via metadata.

    Drops ``call_sig`` from each member and truncates ``reason`` to
    ``_REASON_MAX_LEN`` chars to keep the metadata payload bounded for
    MCP transport. Each output cluster carries a stable ``cluster_hash``
    derived from the sorted ``(file, name)`` membership set — used as
    the acknowledgement key in ``pyproject.toml``.
    """
    slim: list[_Cluster] = []
    for cluster in clusters:
        reason = cluster.get("reason") or ""
        if len(reason) > _REASON_MAX_LEN:
            reason = reason[:_REASON_MAX_LEN]
        members: list[_TestEntry] = [
            {
                "file": t.get("file", ""),
                "name": t.get("name", ""),
                "line": t.get("line", 0),
            }
            for t in cluster.get("members", [])
        ]
        slim.append(
            {
                "signal": cluster.get("signal", ""),
                "reason": reason,
                "similarity": cluster.get("similarity", 0.0),
                "members": members,
                "cluster_hash": _cluster_hash(
                    {"members": members},
                ),
            }
        )
    return slim


# ── Collection ────────────────────────────────────────────────────────


def make_test_func(
    rel: str, node: ast.FunctionDef, class_name: str | None
) -> _TestFunc:
    tf = _TestFunc(
        file=rel,
        name=node.name,
        line=node.lineno,
        node=node,
        class_name=class_name,
    )
    sigs, tainted = _propagate_taint(node)
    sigs |= _collect_raises_call_sigs(node)
    sigs |= collect_assert_call_sigs(node)
    tf.call_sig = ">".join(sorted(sigs))
    tf.assert_pattern = _compute_assert_pattern(node)
    tf.stmt_set = _statement_set(node)
    tf.setup_set = _compute_setup_set(node, tainted)
    tf.has_raises_block = _has_pytest_raises_block(node)
    return tf


def _parse_test_file(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _iter_test_functions(
    tree: ast.Module,
) -> Iterator[tuple[ast.FunctionDef, str | None]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    yield child, node.name
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            yield node, None


def _collect_tests(project_path: Path) -> list[_TestFunc]:
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        return []
    out: list[_TestFunc] = []
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        tree = _parse_test_file(test_file)
        if tree is None:
            continue
        rel = str(test_file.relative_to(project_path))
        for node, class_name in _iter_test_functions(tree):
            out.append(make_test_func(rel, node, class_name))
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
                    "bucket_counts": {"CLUSTERED": 0, "AMBIGUOUS": 0, "UNIQUE": 0},
                },
            )

        config = _load_duplicate_tests_config(project_path)
        acknowledged_hashes: set[str] = {entry["hash"] for entry in config.acknowledged}

        clusters = _cluster(tests, self.ast_similarity_threshold)
        bucket_counts = _bucket_counts(tests, clusters)
        slim = _slim_clusters(clusters)
        for cluster in slim:
            if cluster.get("cluster_hash") in acknowledged_hashes:
                cluster["acknowledged"] = True

        vivant_hashes: set[str] = {
            c["cluster_hash"] for c in slim if "cluster_hash" in c
        }
        stale_acknowledged: list[dict[str, str]] = [
            entry for entry in config.acknowledged if entry["hash"] not in vivant_hashes
        ]

        n_clustered_pairs = sum(
            _pairs_in_cluster(len(c.get("members", [])))
            for c in slim
            if not c.get("signal", "").startswith("ambiguous_")
            and not c.get("acknowledged", False)
        )
        score = max(0, 100 - n_clustered_pairs * _SCORE_PENALTY)
        passed = n_clustered_pairs == 0
        if not clusters:
            message = "no duplicate-test clusters found"
        else:
            message = (
                f"{len(clusters)} cluster(s), {n_clustered_pairs} clustered pair(s)"
            )
        text = (
            render_clusters_text(slim, stale_acknowledged)
            if not passed or stale_acknowledged
            else None
        )
        fix_hint = (
            None
            if passed
            else (
                "Merge duplicate tests, or use parametrize, or differentiate "
                "via distinct fixtures/asserts"
            )
        )
        metadata: dict[str, object] = {
            "clusters": slim,
            "bucket_counts": bucket_counts,
            "stale_acknowledged": stale_acknowledged,
        }
        if config.error:
            metadata["config_error"] = config.error
        return DuplicateTestsCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            score=score,
            metadata=metadata,
            text=text,
            fix_hint=fix_hint,
        )
