"""Audit finding ingestion + canonical-filename computation.

Wraps ``audit_project`` to surface FILE_NAMING / PYRAMID_LEVEL findings
normalised as ``list[dict]`` with absolute paths, and exposes the
per-test canonical-filename machinery (``func_canonical``,
``per_unit_canonical``, ``_class_needs_flatten``) that consumes the
audit's own ``_shared`` helpers.

``collect_unfixable`` lives here too: it re-audits post-pipeline to
report NO_PACKAGE_SYMBOL leftovers + pathological FILE_NAMING SPLIT
victims the proto can't auto-fix.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, NamedTuple

from axm_audit.core.auditor import audit_project
from axm_audit.core.rules.test_quality._shared import (
    canonical_filename,
    cli_invocation_tuple,
    first_party_symbol_counts,
    get_pkg_prefixes,
    load_project_scripts,
)

from .models import NON_DETERMINISTIC_RULES, TOP_K
from .paths import abspath, safe_filename
from .tests_ast import top_level_test_classes

__all__ = [
    "check_by_rule",
    "class_needs_flatten",
    "collect_unfixable",
    "func_canonical",
    "get_pkg_prefixes",  # re-export for callers
    "normalize_findings",
    "per_unit_canonical",
]


def normalize_findings(check: Any) -> list[dict[str, Any]]:
    """Normalise a CheckResult's findings into a list[dict]."""
    raw = None
    if hasattr(check, "details") and isinstance(check.details, dict):
        raw = check.details.get("findings")
    if raw is None:
        raw = getattr(check, "findings", None)
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for f in raw:
        if isinstance(f, dict):
            out.append(f)
        elif hasattr(f, "model_dump"):
            out.append(f.model_dump())
        else:
            out.append(vars(f))
    return out


def _absolutize_paths(finding: dict[str, Any], project_path: Path) -> None:
    for key in ("path", "test_file"):
        value = finding.get(key)
        if isinstance(value, str) and value:
            finding[key] = str(abspath(value, project_path))
    files = finding.get("files")
    if isinstance(files, list):
        finding["files"] = [
            str(abspath(f, project_path)) if isinstance(f, str) else f for f in files
        ]


def check_by_rule(project_path: Path, rule_id: str) -> list[dict[str, Any]]:
    """Run the test_quality audit and return findings for ``rule_id``.

    The returned dicts have their ``path`` / ``test_file`` / ``files``
    entries rewritten as absolute paths anchored at ``project_path`` so
    downstream planners can compare them with their own ``Path`` objects.
    """
    result = audit_project(project_path, category="test_quality")
    for check in result.checks:
        if getattr(check, "rule_id", "") != rule_id:
            continue
        out = normalize_findings(check)
        for d in out:
            _absolutize_paths(d, project_path)
        return out
    return []


def func_canonical(
    func: ast.FunctionDef,
    tree: ast.Module,
    *,
    tier: Literal["integration", "e2e"],
    pkg_prefixes: set[str],
    scripts: set[str],
    single_binary: str | None,
) -> str:
    """Canonical filename a single test function would land in."""
    if tier == "integration":
        sym_counts = first_party_symbol_counts(
            test_func=func, mod_ast=tree, pkg_prefixes=pkg_prefixes
        )
        top: list[Any] = sorted(s for s, _ in sym_counts.most_common()[:TOP_K])
    else:
        inv_counts = cli_invocation_tuple(
            test_func=func, mod_ast=tree, project_scripts=scripts
        )
        top = sorted(t for t, _ in inv_counts.most_common()[:TOP_K])
    return canonical_filename(
        symbols_or_tuples=top, tier=tier, single_binary=single_binary
    )


class _CanonicalCtx(NamedTuple):
    tree: ast.Module
    tier: Literal["integration", "e2e"]
    pkg_prefixes: set[str]
    scripts: set[str]
    single_binary: str | None


def _canonical_unit_name(func: ast.FunctionDef, ctx: _CanonicalCtx) -> str:
    """Safe canonical filename for a single test function."""
    return safe_filename(
        func_canonical(
            func,
            ctx.tree,
            tier=ctx.tier,
            pkg_prefixes=ctx.pkg_prefixes,
            scripts=ctx.scripts,
            single_binary=ctx.single_binary,
        )
    )


def _class_canonical_unit(cls: ast.ClassDef, ctx: _CanonicalCtx) -> str | None:
    """Canonical filename for a Test* class, or None if not a single unit."""
    method_canonicals = {
        _canonical_unit_name(c, ctx)
        for c in cls.body
        if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
    }
    if len(method_canonicals) != 1:
        return None
    only = next(iter(method_canonicals))
    return None if only == "test_UNKNOWN.py" else only


def per_unit_canonical(
    source: Path,
    tier: Literal["integration", "e2e"],
    project_path: Path,
) -> dict[str, list[str]]:
    """For each *movable unit*, compute its canonical filename.

    A movable unit is:
      * a top-level test_* function (anvil moves it directly), OR
      * a Test* class whose methods all share the same tuple (anvil moves
        the class as a block).

    Test* classes with divergent method tuples are NOT a single unit — the
    caller should flatten them first (Stage 0) and re-run.

    Returns {canonical_name: [unit_names]}.
    """
    tree = ast.parse(source.read_text())
    scripts = load_project_scripts(project_path)
    ctx = _CanonicalCtx(
        tree=tree,
        tier=tier,
        pkg_prefixes=get_pkg_prefixes(project_path),
        scripts=scripts,
        single_binary=next(iter(scripts)) if len(scripts) == 1 else None,
    )
    routes: dict[str, list[str]] = defaultdict(list)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            name = _canonical_unit_name(node, ctx)
            if name != "test_UNKNOWN.py":
                routes[name].append(node.name)
    for cls in top_level_test_classes(tree):
        only = _class_canonical_unit(cls, ctx)
        if only is not None:
            routes[only].append(cls.name)
    return dict(routes)


def class_needs_flatten(
    cls: ast.ClassDef,
    tree: ast.Module,
    *,
    tier: Literal["integration", "e2e"],
    pkg_prefixes: set[str],
    scripts: set[str],
    single_binary: str | None,
) -> bool:
    """True iff this class's methods have ≥2 distinct canonical filenames."""
    canonicals = {
        safe_filename(
            func_canonical(
                c,
                tree,
                tier=tier,
                pkg_prefixes=pkg_prefixes,
                scripts=scripts,
                single_binary=single_binary,
            )
        )
        for c in cls.body
        if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
    }
    return len(canonicals) >= 2


def collect_unfixable(project_path: Path) -> list[dict[str, Any]]:
    """Re-audit and return NO_PACKAGE_SYMBOL + pathological FILE_NAMING findings.

    Defensive: post-apply, axm-audit's internal AST cache may hold stale
    paths if files were renamed in-flight. Swallow that exception — the
    caller (proto reporter) treats absence as "no unfixable findings".

    Pathological FILE_NAMING cases: a Test* class with divergent
    canonicals AND a feature (``self.<x>``, custom base, ``__init__``)
    that blocks deterministic flattening. Surfaced as unfixable so the
    user invokes ``/scenario-rename`` or rewrites by hand instead of
    silently leaving the SPLIT finding unresolved.
    """
    out: list[dict[str, Any]] = []
    try:
        result = audit_project(project_path, category="test_quality")
    except FileNotFoundError:
        result = None
    if result is not None:
        for check in result.checks:
            rid = getattr(check, "rule_id", "")
            if rid not in NON_DETERMINISTIC_RULES:
                continue
            for d in normalize_findings(check):
                out.append({"rule_id": rid, **d})
    # B1: lazy import to break the findings <-> stages_plan cycle.
    from .stages_plan import plan_flatten

    for op in plan_flatten(project_path):
        if op.rationale.startswith("PATHOLOGICAL"):
            try:
                tf = str(op.source.relative_to(project_path))
            except ValueError:
                tf = str(op.source)
            out.append(
                {
                    "rule_id": "TEST_QUALITY_FILE_NAMING",
                    "verdict": "PATHOLOGICAL",
                    "test_file": tf,
                    "path": tf,
                    "reason": op.rationale,
                }
            )
    return out
