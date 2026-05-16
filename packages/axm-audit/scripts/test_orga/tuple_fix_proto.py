"""Prototype: deterministic test-suite auto-fixer.

Pipeline (4 stages, all deterministic; NO_PACKAGE_SYMBOL is reported but
left to a human/agent — its verdict is context-dependent):

    1. RELOCATE   (PYRAMID_LEVEL mismatch)              git mv across tiers
    2. SPLIT      (FILE_NAMING verdict=SPLIT)           axm_anvil.move_symbols
    3. COLLIDE    (FILE_NAMING verdict=COLLIDE)         axm_anvil.move_symbols
    4. RENAME     (FILE_NAMING verdict=NAME_MISMATCH)   git mv

The chain re-audits between stage 1 and stages 2-4 so SPLIT/MERGE/RENAME
act on post-RELOCATE paths.

This proto **consumes findings emitted by the rules** (AXM-1721 +
AXM-1722). No tuple detection inlined; the rules are the source of truth.

Companion to:
  * tuple_naming_proto.py       — historical integration tuple detector
  * tuple_naming_e2e_proto.py   — historical e2e CLI tuple detector
  * README_E2E_SESSION.md       — context

Usage::

    uv run --python 3.12 python tuple_fix_proto.py /tmp/proto-fix/axm-audit-copy
    uv run --python 3.12 python tuple_fix_proto.py <path> --apply
    uv run --python 3.12 python tuple_fix_proto.py <path> --rules=TEST_QUALITY_FILE_NAMING

The script defaults to --dry-run.  Pass --apply to actually mutate.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import libcst as cst
from axm_audit.core.auditor import audit_project
from axm_audit.core.rules.test_quality._shared import (
    canonical_filename,
    cli_invocation_tuple,
    first_party_symbol_counts,
    get_pkg_prefixes,
)

try:
    from axm_anvil.core.move import move_symbols
except ImportError:  # pragma: no cover
    move_symbols = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# libcst helpers — source-fidelity writes
# ---------------------------------------------------------------------------
#
# The proto reads with ast (fast, sufficient for analysis) but writes with
# libcst (preserves quote style, indentation, comments, trailing whitespace
# — everything ast.unparse silently loses). Migrating mutating helpers to
# libcst is what gives us back the triple-quoted strings, comments, and
# blank-line spacing that ast.unparse erases. axm-anvil itself works the
# same way under the hood.


def _cst_load(path: Path) -> cst.Module | None:
    """Read *path* and parse it as a libcst Module. None on parse error."""
    try:
        return cst.parse_module(path.read_text())
    except cst.ParserSyntaxError:
        return None


def _cst_save(path: Path, module: cst.Module) -> None:
    """Write *module* back to *path* using its serialised form."""
    path.write_text(module.code)


def _cst_top_level(module: cst.Module) -> list[cst.BaseStatement]:
    """Return the module's top-level body as a mutable list."""
    return list(module.body)


def _cst_unwrap(stmt: cst.BaseStatement) -> cst.BaseSmallStatement | cst.BaseCompoundStatement:
    """Unwrap a SimpleStatementLine to its first small statement, if any.

    libcst wraps top-level small statements (imports, assigns) inside
    ``SimpleStatementLine``. For comparisons / extraction we usually want
    the inner statement (Import, ImportFrom, Assign, …).
    """
    if isinstance(stmt, cst.SimpleStatementLine) and stmt.body:
        return stmt.body[0]
    return stmt  # type: ignore[return-value]

NON_DETERMINISTIC_RULES = frozenset(
    {
        # NO_PACKAGE_SYMBOL: a test that exercises no package symbol may
        # be a legitimate formal check on an artefact, or a candidate for
        # deletion. The verdict is context-dependent — use /scenario-rename
        # or inspect manually.
        "TEST_QUALITY_NO_PACKAGE_SYMBOL",
    }
)


# ---------------------------------------------------------------------------
# FileOp model
# ---------------------------------------------------------------------------


OpKind = Literal["flatten", "relocate", "split", "merge", "rename"]


@dataclass
class FileOp:
    kind: OpKind
    source: Path
    target: Path | list[Path]
    rationale: str
    source_rule: str
    # SPLIT: tuple keyed by the canonical filename a test belongs to →
    # list of test_* names that should land in that file.
    split_map: dict[str, list[str]] | None = None


@dataclass
class PipelineReport:
    ops: list[FileOp] = field(default_factory=list)
    unfixable: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False
    warnings: list[str] = field(default_factory=list)

    def by_kind(self) -> dict[str, int]:
        c: Counter[str] = Counter()
        for op in self.ops:
            c[op.kind] += 1
        return dict(c)


# ---------------------------------------------------------------------------
# Finding extraction
# ---------------------------------------------------------------------------


def _findings(check: Any) -> list[dict[str, Any]]:
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


def _abspath(p: str, project_path: Path) -> Path:
    """Normalise a finding path (which may be relative or absolute)."""
    pp = Path(p)
    return pp if pp.is_absolute() else (project_path / pp)


def _safe_filename(name: str) -> str:
    """Make a canonical filename PEP8-importable.

    The FILE_NAMING rule emits ``test_<a>-<b>.py`` (dash separator).  Python
    rejects ``-`` in module names (ruff N999), and even though pytest
    collects such files, downstream tooling (importlib, mypy, IDE) breaks.
    Substitute ``-`` with ``__`` (double underscore) — keeps the visual
    separation between top-K elements while staying a valid identifier.
    """
    if not name.endswith(".py"):
        return name
    stem = name[:-3]
    return stem.replace("-", "__") + ".py"


def _check_by_rule(project_path: Path, rule_id: str) -> list[dict[str, Any]]:
    result = audit_project(project_path, category="test_quality")
    for check in result.checks:
        if getattr(check, "rule_id", "") == rule_id:
            out = _findings(check)
            # Normalise path fields to absolute Path strings
            for d in out:
                for key in ("path", "test_file"):
                    if key in d and isinstance(d[key], str) and d[key]:
                        d[key] = str(_abspath(d[key], project_path))
                if "files" in d and isinstance(d["files"], list):
                    d["files"] = [
                        str(_abspath(f, project_path)) if isinstance(f, str) else f
                        for f in d["files"]
                    ]
            return out
    return []


# ---------------------------------------------------------------------------
# Stage 1: RELOCATE (PYRAMID_LEVEL)
# ---------------------------------------------------------------------------


def _retier(p: Path, root: Path, target_lvl: str) -> Path:
    """Compute the destination path under tests/{target_lvl}/.

    Walks the relative parts: replaces ``tests/<X>/...rest...`` by
    ``tests/<target_lvl>/...rest...``.  Tolerates absent root prefix.
    """
    rel = p.relative_to(root) if p.is_absolute() else p
    parts = list(rel.parts)
    if len(parts) >= 2 and parts[0] == "tests":
        parts[1] = target_lvl
    return root / Path(*parts)


def plan_flatten(project_path: Path) -> list[FileOp]:
    """Stage 0: detect Test* classes with divergent method tuples → flatten.

    A class whose methods don't all share the same canonical tuple is not
    a movable unit. We flatten it to top-level functions so SPLIT can
    route each method to its correct target file. Pathological classes
    (using ``self.x``, inheriting non-object, having __init__) cannot be
    flattened deterministically and emit an out-of-pipeline warning.
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    ops: list[FileOp] = []
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    # Only files flagged by FILE_NAMING are candidates (avoids scanning
    # every test_* in the project).
    candidate_paths: set[Path] = set()
    for d in findings:
        if d.get("verdict") in {"SPLIT", "COLLIDE", "NAME_MISMATCH"}:
            p = Path(d.get("path", ""))
            if p.is_absolute() and p.exists():
                candidate_paths.add(p)
            elif d.get("files"):
                for fp in d["files"]:
                    pp = Path(fp)
                    if pp.is_absolute() and pp.exists():
                        candidate_paths.add(pp)
    for src in sorted(candidate_paths):
        tier_str = src.parent.name
        if tier_str not in ("integration", "e2e"):
            continue
        tree = ast.parse(src.read_text())
        classes_to_flatten: list[str] = []
        pathological: list[tuple[str, str]] = []
        for cls in _top_level_test_classes(tree):
            if not _class_needs_flatten(
                cls, tree, tier=tier_str, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            ):
                continue
            reason = _class_is_pathological(cls)
            if reason is not None:
                pathological.append((cls.name, reason))
            else:
                classes_to_flatten.append(cls.name)
        if classes_to_flatten:
            ops.append(
                FileOp(
                    kind="flatten",
                    source=src,
                    target=src,
                    rationale=(
                        f"flatten {len(classes_to_flatten)} heterogeneous "
                        f"class(es): {classes_to_flatten}"
                    ),
                    source_rule="TEST_QUALITY_FILE_NAMING",
                    split_map={c: [] for c in classes_to_flatten},
                )
            )
        for cname, why in pathological:
            ops.append(
                FileOp(
                    kind="flatten",
                    source=src,
                    target=src,
                    rationale=f"PATHOLOGICAL {cname}: {why} — cannot flatten",
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )
    return ops


def _execute_flatten(op: FileOp, project_path: Path) -> list[str]:
    """Flatten the listed Test* classes in op.source.

    Skips pathological cases (op.split_map is None — signaled by planner).
    """
    if op.split_map is None:
        return [
            f"flatten skipped: {op.rationale} ({op.source.name})"
        ]
    if not op.source.exists():
        return [f"flatten skipped: {op.source} missing"]
    text = op.source.read_text()
    for class_name in op.split_map.keys():
        text = _flatten_class_to_top_level(text, class_name)
    op.source.write_text(text)
    _reorder_module_statements(op.source)
    return [f"flatten: rewrote {op.source.name} ({list(op.split_map.keys())})"]


def plan_relocate(project_path: Path) -> list[FileOp]:
    """Aggregate PYRAMID_LEVEL findings → 1 op per homogeneous file.

    A file whose tests classify into N≠1 distinct target levels is skipped
    (requires manual split; out of pipeline).
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_PYRAMID_LEVEL")
    per_file: dict[Path, Counter[str]] = defaultdict(Counter)
    for d in findings:
        cur, lvl = d.get("current_level"), d.get("level")
        if cur == lvl or lvl is None:
            continue
        per_file[Path(d["path"])][lvl] += 1
    ops: list[FileOp] = []
    for p, target_levels in per_file.items():
        if len(target_levels) != 1:
            continue  # mixed; needs split first
        target_lvl = next(iter(target_levels))
        n = target_levels[target_lvl]
        ops.append(
            FileOp(
                kind="relocate",
                source=p,
                target=_retier(p, project_path, target_lvl),
                rationale=f"{n} test(s) classify as {target_lvl}",
                source_rule="TEST_QUALITY_PYRAMID_LEVEL",
            )
        )
    return ops


# ---------------------------------------------------------------------------
# Stages 2-4: FILE_NAMING (SPLIT / COLLIDE / NAME_MISMATCH)
# ---------------------------------------------------------------------------


def plan_naming(project_path: Path) -> tuple[list[FileOp], list[FileOp], list[FileOp]]:
    """Read FILE_NAMING findings → (splits, merges, renames).

    Returns the three stages in *execution* order.  Each stage is mutually
    exclusive on a given file: a SPLIT victim doesn't get a RENAME (its
    children inherit canonical names from the split), and a COLLIDE victim
    doesn't get a RENAME (the merge target already has the canonical name).
    """
    findings = _check_by_rule(project_path, "TEST_QUALITY_FILE_NAMING")
    splits: list[FileOp] = []
    merges: list[FileOp] = []
    renames: list[FileOp] = []

    # Bucket by verdict
    by_verdict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in findings:
        by_verdict[d.get("verdict", "")].append(d)

    # Files that will be touched by SPLIT or COLLIDE → exempt from RENAME
    consumed: set[Path] = set()

    # 2. SPLIT
    for d in by_verdict.get("SPLIT", []):
        src = Path(d["path"])
        consumed.add(src)
        # AXM-1722 should expose `suggested_splits` (list of canonical names);
        # if absent, fall back to the file's `tuple` field flattened.
        suggested = d.get("suggested_splits") or [d.get("proposed_name", "")]
        suggested = [_safe_filename(s) for s in suggested if s]
        targets = [src.parent / s for s in suggested]
        splits.append(
            FileOp(
                kind="split",
                source=src,
                target=targets,
                rationale=f"{len(targets)} distinct tuples",
                source_rule="TEST_QUALITY_FILE_NAMING",
                split_map=d.get("split_map"),
            )
        )

    # 3. COLLIDE — one finding per collision group; pick lexically-first as anchor
    for d in by_verdict.get("COLLIDE", []):
        files = sorted(Path(p) for p in d.get("files", []))
        if len(files) < 2:
            continue
        anchor = files[0]
        for other in files[1:]:
            consumed.add(other)
            merges.append(
                FileOp(
                    kind="merge",
                    source=other,
                    target=anchor,
                    rationale=f"COLLIDE on {d.get('canonical_name', '?')} in tests/{d.get('tier', '?')}/",
                    source_rule="TEST_QUALITY_FILE_NAMING",
                )
            )

    # 4. RENAME — skip files consumed by stages 2/3
    for d in by_verdict.get("NAME_MISMATCH", []):
        src = Path(d["path"])
        if src in consumed:
            continue
        proposed = _safe_filename(d.get("proposed_name", ""))
        if not proposed or src.name == proposed:
            continue
        renames.append(
            FileOp(
                kind="rename",
                source=src,
                target=src.parent / proposed,
                rationale=f"{src.name} -> {proposed}",
                source_rule="TEST_QUALITY_FILE_NAMING",
            )
        )

    return splits, merges, renames


# ---------------------------------------------------------------------------
# Unfixable surfacing
# ---------------------------------------------------------------------------


def collect_unfixable(project_path: Path) -> list[dict[str, Any]]:
    """Re-audit and return NO_PACKAGE_SYMBOL findings.

    Defensive: post-apply, axm-audit's internal AST cache may hold stale
    paths if files were renamed in-flight. Swallow that exception — the
    caller (proto reporter) treats absence as "no unfixable findings".
    """
    try:
        result = audit_project(project_path, category="test_quality")
    except FileNotFoundError:
        return []
    out: list[dict[str, Any]] = []
    for check in result.checks:
        rid = getattr(check, "rule_id", "")
        if rid not in NON_DETERMINISTIC_RULES:
            continue
        for d in _findings(check):
            out.append({"rule_id": rid, **d})
    return out


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        shutil.move(str(src), str(dst))


def _execute_relocate(op: FileOp) -> None:
    assert isinstance(op.target, Path)
    _git_mv(op.source, op.target)


def _execute_rename(op: FileOp) -> None:
    assert isinstance(op.target, Path)
    _git_mv(op.source, op.target)


TOP_K = 2


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
    """Return test_* funcs at module level and inside Test* classes."""
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            funcs.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    funcs.append(child)
    return funcs


def _top_level_test_names(tree: ast.Module) -> set[str]:
    """test_* function names at module level only (no class methods)."""
    return {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }


def _top_level_test_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Test* classes at module level that contain test_* methods."""
    out: list[ast.ClassDef] = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name.startswith("Test")):
            continue
        if any(
            isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
            for c in node.body
        ):
            out.append(node)
    return out


def _class_is_pathological(cls: ast.ClassDef) -> str | None:
    """Return a reason if the class cannot be safely flattened, else None.

    Pathological = uses `self.<attr>` inside methods, has `__init__`,
    inherits from anything other than `object` (or empty bases).
    """
    if cls.bases:
        for b in cls.bases:
            if not (isinstance(b, ast.Name) and b.id == "object"):
                return f"inherits from non-object base ({ast.unparse(b)})"
    for child in cls.body:
        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
            return "has __init__"
    # Detect `self.<attr>` reads/writes — these would break a flatten
    for child in cls.body:
        if not (isinstance(child, ast.FunctionDef) and child.name.startswith("test_")):
            continue
        for sub in ast.walk(child):
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == "self"
            ):
                return f"method {child.name} accesses self.{sub.attr}"
    return None


def _load_project_scripts(pkg_root: Path) -> set[str]:
    pyproject = pkg_root / "pyproject.toml"
    if not pyproject.exists():
        return set()
    data = tomllib.loads(pyproject.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


def _func_canonical(
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


def _per_unit_canonical(
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
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    routes: dict[str, list[str]] = defaultdict(list)
    # Top-level funcs
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            name = _safe_filename(_func_canonical(
                node, tree, tier=tier, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            ))
            routes[name].append(node.name)
    # Test* classes — only if homogeneous (else caller should flatten)
    for cls in _top_level_test_classes(tree):
        method_canonicals = {
            _safe_filename(_func_canonical(
                c, tree, tier=tier, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            ))
            for c in cls.body
            if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
        }
        if len(method_canonicals) == 1:
            routes[next(iter(method_canonicals))].append(cls.name)
        # else: divergent — handled by Stage 0 flatten
    return dict(routes)


def _class_needs_flatten(
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
        _safe_filename(_func_canonical(
            c, tree, tier=tier, pkg_prefixes=pkg_prefixes,
            scripts=scripts, single_binary=single_binary,
        ))
        for c in cls.body
        if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
    }
    return len(canonicals) >= 2


def _flatten_class_to_top_level(source_text: str, class_name: str) -> str:
    """Transform `class TestX: def test_a(self, ...): ...` into top-level funcs.

    Removes the class wrapper; promotes each test_* method by dropping
    `self` from its parameter list. Decorators, comments and blank lines
    around each method are preserved (libcst is lossless on these).
    Other bodies inside the class (helpers, fixtures) are also promoted
    to top-level — they may conflict with module-level names; caller is
    expected to verify with _class_is_pathological first.
    """
    module = cst.parse_module(source_text)
    new_body: list[cst.BaseStatement] = []
    for stmt in module.body:
        if not (isinstance(stmt, cst.ClassDef) and stmt.name.value == class_name):
            new_body.append(stmt)
            continue
        # Drop the class wrapper; promote its body. The class body is an
        # IndentedBlock whose children are BaseStatement-level nodes.
        for child in stmt.body.body:
            promoted = _flatten_class_child(child)
            if promoted is not None:
                new_body.append(promoted)
    return module.with_changes(body=new_body).code


def _flatten_class_child(
    child: cst.BaseStatement,
) -> cst.BaseStatement | None:
    """Promote one child of a Test* class body to module level.

    Returns None to drop (class docstring); returns the (possibly
    rewritten) statement otherwise. For FunctionDef, strips the ``self``
    parameter so the promoted top-level function takes the same args
    pytest expects.
    """
    # Class docstring: SimpleStatementLine wrapping a single Expr(SimpleString)
    if isinstance(child, cst.SimpleStatementLine) and len(child.body) == 1:
        inner = child.body[0]
        if isinstance(inner, cst.Expr) and isinstance(
            inner.value, cst.SimpleString | cst.ConcatenatedString
        ):
            return None
    if isinstance(child, cst.FunctionDef):
        params = child.params
        if params.params and params.params[0].name.value == "self":
            new_params = params.with_changes(params=tuple(params.params[1:]))
            return child.with_changes(params=new_params)
    return child


def _execute_split(op: FileOp, project_path: Path) -> list[str]:
    """SPLIT a file by routing each *movable unit* to its canonical target.

    A movable unit = a top-level test_* function or a homogeneous Test*
    class. Heterogeneous Test* classes (divergent method tuples) must
    have been flattened first by Stage 0; if any remain, we bail out.

    The largest unit-group stays in source (rename handled by stage 4
    or by this function if the canonical name differs).
    """
    assert move_symbols is not None, "axm-anvil not importable"
    assert isinstance(op.target, list)
    tier_str = op.source.parent.name
    if tier_str not in ("integration", "e2e"):
        return [f"split skipped: source not under tests/integration|e2e ({op.source})"]
    if not op.source.exists():
        return [f"split skipped: source missing ({op.source})"]
    tree = ast.parse(op.source.read_text())
    # Sanity check: Stage 0 should have flattened heterogeneous classes
    pkg_prefixes = get_pkg_prefixes(project_path)
    scripts = _load_project_scripts(project_path)
    single_binary = next(iter(scripts)) if len(scripts) == 1 else None
    leftover = [
        cls.name
        for cls in _top_level_test_classes(tree)
        if _class_needs_flatten(
            cls, tree, tier=tier_str, pkg_prefixes=pkg_prefixes,
            scripts=scripts, single_binary=single_binary,
        )
    ]
    if leftover:
        return [
            f"split skipped: {op.source.name} still has heterogeneous "
            f"Test* classes after Stage 0: {leftover} (likely pathological)"
        ]
    routes = _per_unit_canonical(op.source, tier_str, project_path)
    if not routes:
        return [f"split skipped: no movable units in {op.source}"]
    if len(routes) < 2:
        return [
            f"split skipped: {op.source.name} has <2 unit-groups "
            "(file is cohesive at canonical-name level)"
        ]
    anchor = max(routes.items(), key=lambda kv: (len(kv[1]), kv[0]))[0]
    warnings: list[str] = []
    for canonical, unit_names in routes.items():
        if canonical == anchor:
            continue
        target = op.source.parent / canonical
        if not target.exists():
            # Minimal docstring — the file name already names the
            # canonical tuple, so we only record the provenance to make
            # the split traceable on review.
            target.write_text(f'"""Split from ``{op.source.name}``."""\n')
        sub_warnings, _ = _safe_move_units(
            op.source, target, unit_names, project_path
        )
        warnings.extend(sub_warnings)
    if op.source.exists() and op.source.name != anchor:
        # The residual source contains the anchor group. Rename it to
        # the anchor canonical — but if a file with that name already
        # exists (cross-file SPLIT collision), do a safe merge into it.
        target = op.source.parent / anchor
        if target.exists() and target != op.source:
            tree = ast.parse(op.source.read_text())
            residual_units = _movable_units_at_top_level(tree)
            if residual_units:
                sub_warnings, _ = _safe_move_units(
                    op.source, target, residual_units, project_path
                )
                warnings.extend(sub_warnings)
            _delete_source_if_empty_tests(op.source)
        else:
            _git_mv(op.source, target)
    return warnings


def _safe_move_units(
    source: Path,
    target: Path,
    unit_names: list[str],
    project_path: Path,
) -> tuple[list[str], list[str]]:
    """Move units from source to target, resolving cross-file name collisions.

    Strategy on each colliding name:
      * If both are test_* funcs and bodies identical → drop from source.
      * Otherwise → rename in source with suffix ``__from_<source_stem>``.

    Returns (warnings, actually_moved_names) — moved names are the
    final names anvil received (possibly with suffix).
    """
    if not unit_names:
        return [], []
    source_tree = ast.parse(source.read_text())
    target_tree = ast.parse(target.read_text())
    target_top_names = {
        n.name
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    source_funcs = {
        n.name: n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }
    target_funcs = {
        n.name: n
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }

    warnings: list[str] = []
    rename_map: dict[str, str] = {}
    final_units: list[str] = []
    suffix = f"__from_{source.stem.removeprefix('test_')}"

    for name in unit_names:
        if name not in target_top_names:
            final_units.append(name)
            continue
        # Collision detected
        if name in source_funcs and name in target_funcs:
            if _func_body_hash(source_funcs[name]) == _func_body_hash(
                target_funcs[name]
            ):
                warnings.append(
                    f"dedup: dropped {source.name}::{name} "
                    f"(identical body to {target.name}::{name})"
                )
                _delete_function_from_source(source, name)
                continue
        # Different bodies, or class collision → rename
        new_name = name + suffix
        rename_map[name] = new_name
        final_units.append(new_name)
        warnings.append(
            f"rename: {source.name}::{name} -> {new_name} "
            f"(collision with {target.name})"
        )

    if rename_map:
        _rename_top_level_in_source(source, rename_map)

    if not final_units:
        return warnings, []

    plan = move_symbols(
        source_path=source,
        target_path=target,
        symbol_names=final_units,
        workspace_root=project_path,
        shared_helpers="duplicate",
    )
    warnings.extend(plan.warnings)
    # Post-move corrections (anvil leaves some gaps that break import/runtime):
    #   - missing imports for names appearing only in type annotations
    #   - module-level assignments that reference functions defined later
    backfilled = _backfill_missing_imports(source, target, project_path)
    warnings.extend(backfilled)
    _reorder_module_statements(target)
    if source.exists():
        _reorder_module_statements(source)
    return warnings, final_units


def _func_body_hash(func: ast.FunctionDef) -> str:
    """Stable string hash of a function body (for collision dedup).

    Comparison is structural via ast.unparse on the body — ignores
    docstrings, comments, and minor formatting.
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # drop docstring
    stub = ast.Module(body=body, type_ignores=[])
    return ast.unparse(stub)


def _movable_units_at_top_level(tree: ast.Module) -> list[str]:
    """All top-level names anvil would move: test_* funcs + Test* classes."""
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            out.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            out.append(node.name)
    return out


def _execute_merge(op: FileOp, project_path: Path) -> list[str]:
    """MERGE source's units into target via _safe_move_units."""
    assert isinstance(op.target, Path)
    if not op.source.exists() or not op.target.exists():
        return [f"merge skipped: missing ({op.source} -> {op.target})"]
    source_tree = ast.parse(op.source.read_text())
    source_units = _movable_units_at_top_level(source_tree)
    if not source_units:
        return [f"merge skipped: {op.source} has no top-level movable units"]
    warnings, _ = _safe_move_units(
        op.source, op.target, source_units, project_path
    )
    _delete_source_if_empty_tests(op.source)
    return warnings


def _delete_function_from_source(source: Path, func_name: str) -> None:
    """Remove a top-level FunctionDef from source, preserving formatting."""
    module = _cst_load(source)
    if module is None:
        return
    new_body = [
        stmt
        for stmt in module.body
        if not (isinstance(stmt, cst.FunctionDef) and stmt.name.value == func_name)
    ]
    _cst_save(source, module.with_changes(body=new_body))


_BUILTINS = set(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__))


def _collect_imported_names(
    tree: ast.Module,
) -> dict[str, tuple[ast.stmt, ast.stmt | None]]:
    """Return {imported_name: (import_stmt, enclosing_block_or_None)}.

    Walks the whole module — not just top-level — so that ``if TYPE_CHECKING``
    blocks are scanned too.  ``enclosing_block`` is the ``if TYPE_CHECKING:``
    statement (or similar) wrapping the import, or None for top-level.

    For ``from x import y`` and ``from x import y as z``, the mapping uses
    the local binding name (``y`` or ``z``).
    """
    out: dict[str, tuple[ast.stmt, ast.stmt | None]] = {}

    def visit(stmts: list[ast.stmt], enclosing: ast.stmt | None) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local = alias.asname or alias.name.split(".")[0]
                    out[local] = (stmt, enclosing)
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    local = alias.asname or alias.name
                    out[local] = (stmt, enclosing)
            elif isinstance(stmt, ast.If):
                # if TYPE_CHECKING: ... — walk into both branches with self
                # as the enclosing wrapper
                visit(stmt.body, stmt)
                visit(stmt.orelse, stmt)
            elif isinstance(stmt, ast.Try):
                visit(stmt.body, stmt)
                for handler in stmt.handlers:
                    visit(handler.body, stmt)
                visit(stmt.orelse, stmt)
                visit(stmt.finalbody, stmt)

    visit(tree.body, None)
    return out


def _collect_defined_names(tree: ast.Module) -> set[str]:
    """Names defined at module top-level (functions, classes, assignments)."""
    out: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
            out.add(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.add(stmt.target.id)
    return out


def _collect_referenced_names(tree: ast.Module) -> set[str]:
    """Names actually referenced from live top-level symbols.

    Restricted to ``Name(Load)`` reachable from:
      * decorators on top-level FunctionDef / ClassDef
      * class bases and keywords
      * argument annotations + default expressions of top-level functions
      * function bodies of top-level FunctionDef / ClassDef methods
        (excluding nested string literals, which ast.walk would otherwise
        pick up if someone embedded a textwrap.dedent block)
      * top-level Assign / AnnAssign right-hand sides

    Walking the *whole module* — as the previous implementation did —
    picks up identifiers inside dead branches, string literals parsed by
    callers via ``ast.parse(some_dedent_block)``, etc. and triggers F401
    backfills for names that aren't really used.
    """
    out: set[str] = set()

    def add_names(node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                out.add(sub.id)

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            for dec in stmt.decorator_list:
                add_names(dec)
            for arg in (
                *stmt.args.posonlyargs,
                *stmt.args.args,
                *stmt.args.kwonlyargs,
            ):
                if arg.annotation is not None:
                    add_names(arg.annotation)
            if stmt.args.vararg and stmt.args.vararg.annotation:
                add_names(stmt.args.vararg.annotation)
            if stmt.args.kwarg and stmt.args.kwarg.annotation:
                add_names(stmt.args.kwarg.annotation)
            for default in (*stmt.args.defaults, *stmt.args.kw_defaults):
                if default is not None:
                    add_names(default)
            if stmt.returns is not None:
                add_names(stmt.returns)
            for child in stmt.body:
                add_names(child)
        elif isinstance(stmt, ast.ClassDef):
            for dec in stmt.decorator_list:
                add_names(dec)
            for base in stmt.bases:
                add_names(base)
            for kw in stmt.keywords:
                add_names(kw.value)
            for child in stmt.body:
                add_names(child)
        elif isinstance(stmt, ast.Assign):
            add_names(stmt.value)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.annotation is not None:
                add_names(stmt.annotation)
            if stmt.value is not None:
                add_names(stmt.value)
        elif isinstance(stmt, ast.If):
            # if TYPE_CHECKING: imports live here, not interesting; but
            # other guarded code (e.g. version checks) may reference real
            # symbols. Walk the bodies but not the test (which uses names
            # like TYPE_CHECKING that we don't want to flag).
            for child in (*stmt.body, *stmt.orelse):
                add_names(child)
    return out


_PROJECT_IMPORT_INDEX_CACHE: dict[
    Path, dict[str, tuple[ast.stmt, ast.stmt | None]]
] = {}


def _project_import_index(
    project_path: Path,
) -> dict[str, tuple[ast.stmt, ast.stmt | None]]:
    """Build (and cache) ``{name: (import_stmt, enclosing_block)}`` for the project.

    Walks every ``test_*.py`` under ``tests/`` ONCE and indexes every
    imported name. Subsequent calls reuse the cache — without it,
    ``_scan_tests_for_import`` re-parses ~170 files per missing name and
    dominates wall time (7 min+ on the corpus).

    Cache is invalidated by callers when they know files have changed
    (see ``_invalidate_import_index``). Within a stage that only adds new
    imports to already-indexed files, the cache stays consistent because
    we only ever LOOK UP names — we don't depend on which file an import
    came from beyond the AST nodes themselves.
    """
    if project_path in _PROJECT_IMPORT_INDEX_CACHE:
        return _PROJECT_IMPORT_INDEX_CACHE[project_path]
    index: dict[str, tuple[ast.stmt, ast.stmt | None]] = {}
    seen_dirs: set[Path] = set()
    for tdir in ("tests/integration", "tests/e2e", "tests/unit", "tests"):
        d = project_path / tdir
        if not d.exists() or d in seen_dirs:
            continue
        seen_dirs.add(d)
        for p in d.rglob("test_*.py"):
            try:
                tree = ast.parse(p.read_text())
            except (SyntaxError, OSError):
                continue
            for name, pair in _collect_imported_names(tree).items():
                index.setdefault(name, pair)
    _PROJECT_IMPORT_INDEX_CACHE[project_path] = index
    return index


def _invalidate_import_index(project_path: Path) -> None:
    """Drop the cached import index for *project_path*.

    Called between pipeline stages that may move files around (RELOCATE,
    SPLIT, MERGE, RENAME) — those changes could in principle add new
    imports or remove a file, and the next consumer should see a fresh
    snapshot. Cheap: the next lookup repopulates lazily.
    """
    _PROJECT_IMPORT_INDEX_CACHE.pop(project_path, None)


def _scan_tests_for_import(
    project_path: Path, name: str
) -> tuple[ast.stmt, ast.stmt | None] | None:
    """O(1) lookup of an imported *name* anywhere in the project's tests."""
    return _project_import_index(project_path).get(name)


def _backfill_missing_imports(
    source: Path, target: Path, project_path: Path | None = None
) -> list[str]:
    """Copy imports from *source* into *target* for names target uses but doesn't define.

    Falls back to scanning all test files under ``project_path`` if the
    immediate source doesn't have the import — covers cases where the
    original import was lost by an earlier move.

    Hybrid: analyse with ast (cheap, well-tested), write with libcst so
    triple-quoted strings, blank lines, and comments in the target file
    are preserved byte-for-byte.
    """
    if not target.exists():
        return []
    try:
        tgt_tree = ast.parse(target.read_text())
    except SyntaxError:
        return []
    src_tree: ast.Module | None = None
    if source.exists():
        try:
            src_tree = ast.parse(source.read_text())
        except SyntaxError:
            src_tree = None

    src_imports = _collect_imported_names(src_tree) if src_tree else {}
    tgt_imports = _collect_imported_names(tgt_tree)
    tgt_defined = _collect_defined_names(tgt_tree)
    tgt_refs = _collect_referenced_names(tgt_tree)

    missing = (
        tgt_refs
        - set(tgt_imports.keys())
        - tgt_defined
        - _BUILTINS
        - {"self", "cls", "True", "False", "None"}
    )
    recoverable: dict[str, tuple[ast.stmt, ast.stmt | None]] = {
        name: src_imports[name] for name in missing if name in src_imports
    }
    still_missing = missing - set(recoverable.keys())
    if still_missing and project_path is not None:
        for name in still_missing:
            found = _scan_tests_for_import(project_path, name)
            if found is not None:
                recoverable[name] = found

    if not recoverable:
        return []

    # Bucket recovered imports: top-level vs TYPE_CHECKING-wrapped.
    # We dedupe by ast-stmt identity, so a single ``from x import a, b``
    # that supplied two missing names is added once.
    top_level_ast: list[ast.stmt] = []
    type_checking_ast: list[ast.stmt] = []
    seen_top: set[int] = set()
    seen_tc: set[int] = set()
    msgs: list[str] = []
    for name, (stmt, enclosing) in recoverable.items():
        msgs.append(f"backfilled import for `{name}` from {source.name}")
        is_tc = (
            enclosing is not None
            and isinstance(enclosing, ast.If)
            and isinstance(enclosing.test, ast.Name)
            and enclosing.test.id == "TYPE_CHECKING"
        )
        bucket, seen = (
            (type_checking_ast, seen_tc) if is_tc else (top_level_ast, seen_top)
        )
        if id(stmt) not in seen:
            bucket.append(stmt)
            seen.add(id(stmt))

    # Convert each ast import → fresh libcst statement (we don't try to
    # transplant the source's libcst node because the source file may
    # have been mutated since the analysis read).
    top_level_cst = [_ast_import_to_cst(s) for s in top_level_ast]
    type_checking_cst = [_ast_import_to_cst(s) for s in type_checking_ast]

    cst_module = _cst_load(target)
    if cst_module is None:
        return msgs
    new_body = _insert_imports_cst(
        cst_module, top_level_cst, type_checking_cst
    )
    new_module = cst_module.with_changes(body=new_body)
    new_module = _dedupe_imports_cst(new_module)
    _cst_save(target, new_module)
    return msgs


def _ast_import_to_cst(stmt: ast.stmt) -> cst.SimpleStatementLine:
    """Convert an ast import statement to a libcst SimpleStatementLine.

    Handles ``import x``, ``import x as y``, ``import x.y``, ``from m
    import a, b as c``, and relative ``from .m import x`` forms. Any
    other ast node is wrapped as a trailing comment line — should not
    happen in practice since the buckets only contain ast.Import /
    ast.ImportFrom from ``_collect_imported_names``.
    """
    if isinstance(stmt, ast.Import):
        names = [
            cst.ImportAlias(
                name=_dotted_name_to_cst(a.name),
                asname=cst.AsName(name=cst.Name(a.asname)) if a.asname else None,
            )
            for a in stmt.names
        ]
        return cst.SimpleStatementLine(body=[cst.Import(names=names)])
    if isinstance(stmt, ast.ImportFrom):
        names = [
            cst.ImportAlias(
                name=cst.Name(a.name),
                asname=cst.AsName(name=cst.Name(a.asname)) if a.asname else None,
            )
            for a in stmt.names
        ]
        module = (
            _dotted_name_to_cst(stmt.module) if stmt.module else None
        )
        return cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=module,
                    names=names,
                    relative=[cst.Dot()] * (stmt.level or 0),
                )
            ]
        )
    # Defensive fallback: emit a placeholder comment line (parses but is
    # visually obvious). This branch should be unreachable.
    return cst.SimpleStatementLine(
        body=[cst.Expr(cst.SimpleString(value='"# unrecognised import"'))]
    )


def _dotted_name_to_cst(dotted: str) -> cst.Attribute | cst.Name:
    """Build a libcst dotted name from ``a.b.c``."""
    parts = dotted.split(".")
    node: cst.Attribute | cst.Name = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _is_cst_import(stmt: cst.BaseStatement) -> bool:
    """True iff stmt is a SimpleStatementLine wrapping Import/ImportFrom."""
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    return any(
        isinstance(small, cst.Import | cst.ImportFrom) for small in stmt.body
    )


def _is_cst_type_checking_block(stmt: cst.BaseStatement) -> bool:
    """True iff stmt is ``if TYPE_CHECKING:`` (no elif, no else conditions matter)."""
    if not isinstance(stmt, cst.If):
        return False
    test = stmt.test
    return isinstance(test, cst.Name) and test.value == "TYPE_CHECKING"


def _insert_imports_cst(
    module: cst.Module,
    top_level: list[cst.SimpleStatementLine],
    type_checking: list[cst.SimpleStatementLine],
) -> list[cst.BaseStatement]:
    """Return a new top-level body with the new imports placed sensibly.

    Top-level imports go after the last existing top-level import (or at
    the start). TYPE_CHECKING-bucket imports go into an existing
    ``if TYPE_CHECKING:`` block if present, else into a new one
    (preceded by ``from typing import TYPE_CHECKING`` if needed).
    """
    body = list(module.body)

    last_import_idx = -1
    for i, stmt in enumerate(body):
        if _is_cst_import(stmt):
            last_import_idx = i
    insert_at = last_import_idx + 1
    if top_level:
        body = body[:insert_at] + list(top_level) + body[insert_at:]

    if not type_checking:
        return body

    # Existing TYPE_CHECKING block?
    for i, stmt in enumerate(body):
        if _is_cst_type_checking_block(stmt):
            assert isinstance(stmt, cst.If)
            new_inner = list(stmt.body.body) + list(type_checking)
            body[i] = stmt.with_changes(
                body=stmt.body.with_changes(body=new_inner)
            )
            return body

    # New block needed. Add ``from typing import TYPE_CHECKING`` first
    # if it isn't already imported.
    has_tc_import = False
    for stmt in body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.ImportFrom):
                mod = small.module
                if (
                    isinstance(mod, cst.Name)
                    and mod.value == "typing"
                    and any(
                        isinstance(a.name, cst.Name)
                        and a.name.value == "TYPE_CHECKING"
                        for a in small.names
                    )
                ):
                    has_tc_import = True

    new_block = cst.If(
        test=cst.Name("TYPE_CHECKING"),
        body=cst.IndentedBlock(body=list(type_checking)),
    )
    insert_pos = last_import_idx + 1 + len(top_level)
    if has_tc_import:
        body = body[:insert_pos] + [new_block] + body[insert_pos:]
    else:
        tc_import = cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=cst.Name("typing"),
                    names=[cst.ImportAlias(name=cst.Name("TYPE_CHECKING"))],
                    relative=[],
                )
            ]
        )
        body = body[:insert_pos] + [tc_import, new_block] + body[insert_pos:]
    return body


def _dedupe_imports_cst(module: cst.Module) -> cst.Module:
    """Collapse duplicate import bindings at module top-level and in TC blocks.

    Two-level dedup:
      1. Exact-triple ``(module, name, asname)`` — the obvious case where
         the same merge re-injects an identical import.
      2. **Local-binding shadow** — when a later alias would shadow an
         earlier *local name* even though it comes from a different
         module (e.g. ``from a import X`` then ``from a.b import X``).
         Ruff's F811 catches this; we drop the later one (first import
         wins, matching Python's normal "first binding survives until
         re-bound" execution semantics — which is what authors usually
         expected when both happened to land in the same file via merges).
    """
    seen_triples: set[tuple[str, str, str | None]] = set()
    seen_locals: set[str] = set()

    def key_of(prefix: str, alias: cst.ImportAlias) -> tuple[str, str, str | None]:
        name = _cst_name_to_str(alias.name)
        asname = (
            _cst_name_to_str(alias.asname.name)
            if alias.asname is not None
            else None
        )
        return (prefix, name, asname)

    def local_name(prefix: str, alias: cst.ImportAlias) -> str:
        """The local binding name introduced by an alias."""
        if alias.asname is not None:
            return _cst_name_to_str(alias.asname.name)
        full = _cst_name_to_str(alias.name)
        # For ``import a.b.c`` the local binding is ``a``; for
        # ``from m import a.b`` (illegal but defensive) take the head.
        # For ``from m import x`` the local binding is just ``x``.
        if prefix == "":
            return full.split(".")[0]
        return full

    def is_duplicate(prefix: str, alias: cst.ImportAlias) -> bool:
        if key_of(prefix, alias) in seen_triples:
            return True
        if local_name(prefix, alias) in seen_locals:
            return True
        return False

    def record(prefix: str, alias: cst.ImportAlias) -> None:
        seen_triples.add(key_of(prefix, alias))
        seen_locals.add(local_name(prefix, alias))

    def dedupe_simple(stmt: cst.SimpleStatementLine) -> cst.SimpleStatementLine | None:
        new_small: list[cst.BaseSmallStatement] = []
        for small in stmt.body:
            if isinstance(small, cst.Import):
                kept = [a for a in small.names if not is_duplicate("", a)]
                for a in kept:
                    record("", a)
                if kept:
                    new_small.append(small.with_changes(names=kept))
            elif isinstance(small, cst.ImportFrom):
                level = len(small.relative)
                module_str = _cst_name_to_str(small.module) if small.module else ""
                prefix = "." * level + module_str
                if isinstance(small.names, cst.ImportStar):
                    new_small.append(small)
                    continue
                kept = [a for a in small.names if not is_duplicate(prefix, a)]
                for a in kept:
                    record(prefix, a)
                if kept:
                    new_small.append(small.with_changes(names=kept))
            else:
                new_small.append(small)
        if not new_small:
            return None
        return stmt.with_changes(body=new_small)

    new_body: list[cst.BaseStatement] = []
    for stmt in module.body:
        if isinstance(stmt, cst.SimpleStatementLine):
            replaced = dedupe_simple(stmt)
            if replaced is not None:
                new_body.append(replaced)
            continue
        if _is_cst_type_checking_block(stmt):
            assert isinstance(stmt, cst.If)
            new_inner: list[cst.BaseStatement] = []
            for inner in stmt.body.body:
                if isinstance(inner, cst.SimpleStatementLine):
                    replaced = dedupe_simple(inner)
                    if replaced is not None:
                        new_inner.append(replaced)
                else:
                    new_inner.append(inner)
            if new_inner:
                new_body.append(
                    stmt.with_changes(
                        body=stmt.body.with_changes(body=new_inner)
                    )
                )
            continue
        new_body.append(stmt)
    return module.with_changes(body=new_body)


def _cst_name_to_str(node: cst.BaseExpression | cst.Name | cst.Attribute) -> str:
    """Stringify a (possibly dotted) cst Name/Attribute."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_cst_name_to_str(node.value)}.{node.attr.value}"
    return ""


def _stmt_defines(stmt: ast.stmt) -> set[str]:
    """Names a top-level statement defines (for the module-level scope)."""
    out: set[str] = set()
    if isinstance(stmt, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
        out.add(stmt.name)
    elif isinstance(stmt, ast.Assign):
        for tgt in stmt.targets:
            if isinstance(tgt, ast.Name):
                out.add(tgt.id)
    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        out.add(stmt.target.id)
    elif isinstance(stmt, ast.Import):
        for alias in stmt.names:
            out.add(alias.asname or alias.name.split(".")[0])
    elif isinstance(stmt, ast.ImportFrom):
        for alias in stmt.names:
            out.add(alias.asname or alias.name)
    return out


def _stmt_references(stmt: ast.stmt) -> set[str]:
    """Names a statement references at MODULE-EXECUTION time.

    For a FunctionDef/ClassDef, this is the *decorators* and class bases,
    NOT the body (the body executes when the function is called, not at
    module import). For an Assign, this is the right-hand side.
    """
    out: set[str] = set()
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
        for dec in stmt.decorator_list:
            for sub in ast.walk(dec):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
    elif isinstance(stmt, ast.ClassDef):
        for dec in stmt.decorator_list:
            for sub in ast.walk(dec):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
        for base in stmt.bases:
            for sub in ast.walk(base):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
        for kw in stmt.keywords:
            for sub in ast.walk(kw.value):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
    elif isinstance(stmt, ast.Assign):
        for sub in ast.walk(stmt.value):
            if isinstance(sub, ast.Name):
                out.add(sub.id)
    elif isinstance(stmt, ast.AnnAssign):
        if stmt.value is not None:
            for sub in ast.walk(stmt.value):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
    elif isinstance(stmt, ast.Expr):
        for sub in ast.walk(stmt.value):
            if isinstance(sub, ast.Name):
                out.add(sub.id)
    return out


def _reorder_module_statements(path: Path) -> None:
    """Reorder a module's top-level statements so definitions precede uses.

    After SPLIT/MERGE/FLATTEN, axm-anvil can leave statements in an order
    that breaks Python's module-execution semantics:
      * ``_skip_no_tools = pytest.mark.skipif(_tools_available())`` before
        ``def _tools_available()`` → NameError at import.
      * ``@_skip_no_tools`` decorator on a class, before the assign that
        defines ``_skip_no_tools`` → NameError.

    Strategy: stable topological sort. Imports stay first (they have no
    intra-module deps). For the rest, each statement is placed after the
    last statement that defines a name it references at module-execution
    time. References inside function bodies do NOT count — they're
    deferred. Order is preserved within independent groups.

    Implementation note: we parse twice — once with libcst (the source
    of truth for formatting; what we'll write back) and once with ast
    (for cheap defines/references analysis). The libcst statements are
    reordered by index, not rebuilt, so triple-quoted strings, comments,
    and blank-line spacing all survive intact.

    Idempotent.
    """
    cst_module = _cst_load(path)
    if cst_module is None:
        return
    text = cst_module.code
    try:
        ast_tree = ast.parse(text)
    except SyntaxError:
        return
    # The two parsers MUST produce body lists of equal length — they
    # parse the same text. (cst stores top-level stmts in `module.body`,
    # ast in `tree.body`; both are 1:1 with source statements.)
    if len(cst_module.body) != len(ast_tree.body):
        return

    body_ast = ast_tree.body
    body_cst = list(cst_module.body)

    # Separate imports + leading docstring (head) from the rest.
    head_idx: list[int] = []
    rest_idx: list[int] = []
    seen_non_head = False
    for i, stmt in enumerate(body_ast):
        if not seen_non_head and isinstance(stmt, ast.Import | ast.ImportFrom):
            head_idx.append(i)
        elif (
            not seen_non_head
            and isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            head_idx.append(i)
        else:
            seen_non_head = True
            rest_idx.append(i)

    # Lift any stray imports that appear later (anvil sometimes places
    # them mid-body); they go to head — imports have no intra-module deps.
    stray_imports: list[int] = []
    rest_clean: list[int] = []
    for i in rest_idx:
        if isinstance(body_ast[i], ast.Import | ast.ImportFrom):
            stray_imports.append(i)
        else:
            rest_clean.append(i)
    head_idx = head_idx + stray_imports
    rest_idx = rest_clean

    # Names defined by the head (used to ignore self-refs when ranking rest).
    head_names: set[str] = set()
    for i in head_idx:
        head_names |= _stmt_defines(body_ast[i])

    # name → position in the rest sequence (0-based, last wins).
    name_to_pos: dict[str, int] = {}
    for pos, i in enumerate(rest_idx):
        for n in _stmt_defines(body_ast[i]):
            name_to_pos[n] = pos

    n = len(rest_idx)
    earliest: list[int] = [0] * n
    needs_change = False
    for pos, i in enumerate(rest_idx):
        refs = _stmt_references(body_ast[i]) - head_names
        min_pos = 0
        for ref in refs:
            if ref in name_to_pos:
                min_pos = max(min_pos, name_to_pos[ref] + 1)
        earliest[pos] = min_pos
        if min_pos > pos:
            needs_change = True

    if not needs_change:
        return

    # Stable sort of rest positions by (earliest, original_position).
    order = sorted(range(n), key=lambda p: (earliest[p], p))
    new_rest_idx = [rest_idx[p] for p in order]
    new_body_cst = [body_cst[i] for i in head_idx] + [
        body_cst[i] for i in new_rest_idx
    ]
    new_module = cst_module.with_changes(body=new_body_cst)
    new_text = new_module.code
    if new_text != text:
        path.write_text(new_text)


def _rename_top_level_in_source(source: Path, old_to_new: dict[str, str]) -> None:
    """Rename top-level FunctionDef / ClassDef in *source*, preserving formatting.

    Workaround for axm-anvil's ``rename=`` parameter, which validates
    target absence under the ORIGINAL name before applying the rename —
    so it cannot resolve cross-file collisions on its own. By renaming in
    source first, we hand anvil a clean conflict-free move.
    """
    if not old_to_new:
        return
    module = _cst_load(source)
    if module is None:
        return
    new_body = []
    for stmt in module.body:
        if (
            isinstance(stmt, cst.FunctionDef | cst.ClassDef)
            and stmt.name.value in old_to_new
        ):
            stmt = stmt.with_changes(
                name=cst.Name(value=old_to_new[stmt.name.value])
            )
        new_body.append(stmt)
    _cst_save(source, module.with_changes(body=new_body))


def _delete_source_if_empty_tests(source: Path) -> None:
    """git rm the source if no test_* funcs/classes remain."""
    if not source.exists():
        return
    tree = ast.parse(source.read_text())
    if _walk_test_funcs(tree):
        return
    rc = subprocess.run(
        ["git", "rm", "-q", str(source)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        source.unlink()


def execute(ops: list[FileOp], project_path: Path) -> list[str]:
    """Apply ops in order. Returns aggregated warnings."""
    warnings: list[str] = []
    for op in ops:
        if op.kind == "flatten":
            warnings.extend(_execute_flatten(op, project_path))
        elif op.kind == "relocate":
            _execute_relocate(op)
        elif op.kind == "rename":
            _execute_rename(op)
        elif op.kind == "split":
            warnings.extend(_execute_split(op, project_path))
        elif op.kind == "merge":
            warnings.extend(_execute_merge(op, project_path))
    return warnings


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(
    project_path: Path, *, apply: bool, rules: set[str]
) -> PipelineReport:
    report = PipelineReport(applied=apply)

    warnings: list[str] = []

    # Stage 0: FLATTEN heterogeneous Test* classes (FILE_NAMING preflight).
    # Done first so RELOCATE / SPLIT / MERGE / RENAME see top-level units only.
    if "TEST_QUALITY_FILE_NAMING" in rules:
        flatten_ops = plan_flatten(project_path)
        report.ops.extend(flatten_ops)
        if apply and flatten_ops:
            warnings.extend(execute(flatten_ops, project_path))
            _invalidate_import_index(project_path)

    # Stage 1: RELOCATE
    if "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        relocate_ops = plan_relocate(project_path)
        report.ops.extend(relocate_ops)
        if apply and relocate_ops:
            warnings.extend(execute(relocate_ops, project_path))
            _invalidate_import_index(project_path)

    # Stages 2-4: FILE_NAMING (planned AFTER flatten + relocate).
    # Re-plan between stages to act on post-mutation paths — the audit
    # path field becomes stale after SPLIT moves files around.
    if "TEST_QUALITY_FILE_NAMING" in rules:
        if apply:
            splits, _, _ = plan_naming(project_path)
            report.ops.extend(splits)
            warnings.extend(execute(splits, project_path))
            _invalidate_import_index(project_path)
            _, merges, _ = plan_naming(project_path)  # re-plan post-SPLIT
            report.ops.extend(merges)
            warnings.extend(execute(merges, project_path))
            _invalidate_import_index(project_path)
            _, _, renames = plan_naming(project_path)  # re-plan post-MERGE
            report.ops.extend(renames)
            warnings.extend(execute(renames, project_path))
        else:
            splits, merges, renames = plan_naming(project_path)
            report.ops.extend(splits)
            report.ops.extend(merges)
            report.ops.extend(renames)

    # Post-pipeline polish: run `ruff check --fix-only` (F401/I001/UP034
    # sweep) then `ruff format` (line wrapping). Best-effort — failures
    # surface as warnings, never abort the apply.
    if apply:
        warnings.extend(_ruff_format_tests(project_path))

    report.warnings = warnings

    report.unfixable = collect_unfixable(project_path)
    return report


def _ruff_format_tests(project_path: Path) -> list[str]:
    """Run ``ruff format`` and ``ruff check --fix-only`` on ``tests/``.

    Idempotent. ``format`` resolves E501 + UP034; ``check --fix-only``
    with safe fixes resolves F401 (unused imports the proto over-copied
    despite Fix 1, e.g. in edge cases) + I001 (import order).

    Failures are caught and turned into warnings — we never want this
    polish step to abort an otherwise-successful apply.
    """
    tests = project_path / "tests"
    if not tests.exists():
        return []
    msgs: list[str] = []
    for cmd_args, label in (
        (
            [
                "ruff", "check", "--fix-only",
                "--select", "F401,I001,UP034",
                str(tests),
            ],
            "ruff --fix F401/I001/UP034",
        ),
        (["ruff", "format", str(tests)], "ruff format"),
    ):
        try:
            rc = subprocess.run(
                cmd_args, capture_output=True, text=True, cwd=project_path
            )
        except FileNotFoundError:
            msgs.append(f"{label} skipped: ruff not on PATH")
            return msgs
        if rc.returncode not in (0, 1):
            # 0 = clean, 1 = changes applied (for --fix-only) or files
            # reformatted (for format). Anything else is an error.
            msgs.append(f"{label} returned exit {rc.returncode}: {rc.stderr[:200]}")
    return msgs


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_target(t: Path | list[Path], root: Path) -> str:
    if isinstance(t, Path):
        try:
            return str(t.relative_to(root))
        except ValueError:
            return str(t)
    return ", ".join(_fmt_target(x, root) for x in t)


def format_report(r: PipelineReport, project_path: Path) -> str:
    lines: list[str] = []
    head = "applied" if r.applied else "dry-run"
    lines.append(f"\nPipeline ({head}) on {project_path}")
    lines.append("=" * 78)
    counts = r.by_kind()
    total = sum(counts.values())
    if not total:
        lines.append("  (no deterministic ops planned)")
    else:
        for kind in ("flatten", "relocate", "split", "merge", "rename"):
            n = counts.get(kind, 0)
            if n:
                lines.append(f"  Stage {kind.upper():9s} {n} op(s)")
    if r.ops:
        lines.append("")
        lines.append("Details (first 30):")
        for op in r.ops[:30]:
            try:
                src = op.source.relative_to(project_path)
            except ValueError:
                src = op.source
            lines.append(f"  [{op.kind:8s}] {src}")
            lines.append(f"               -> {_fmt_target(op.target, project_path)}")
            lines.append(f"               rationale: {op.rationale}")
        if len(r.ops) > 30:
            lines.append(f"  ... +{len(r.ops) - 30} more")
    lines.append("")
    if r.unfixable:
        lines.append(
            f"Out of pipeline (agent-driven, {len(r.unfixable)} finding(s)):"
        )
        for u in r.unfixable[:20]:
            tf = u.get("test_file") or u.get("path") or "?"
            lines.append(f"  {u['rule_id']}: {tf}")
        if len(r.unfixable) > 20:
            lines.append(f"  ... +{len(r.unfixable) - 20} more")
        lines.append(
            "  -> Run /scenario-rename or inspect manually — these tests "
            "may be legitimate or candidates for deletion."
        )
    else:
        lines.append("Out of pipeline: 0 finding")
    if r.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(r.warnings)}):")
        for w in r.warnings[:15]:
            lines.append(f"  ! {w}")
        if len(r.warnings) > 15:
            lines.append(f"  ... +{len(r.warnings) - 15} more")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("project_path", type=Path, help="Path to package root")
    parser.add_argument(
        "--apply", action="store_true", help="Mutate the project (default: dry-run)"
    )
    parser.add_argument(
        "--rules",
        default="TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING",
        help="Comma-separated rule_ids to fix",
    )
    args = parser.parse_args()

    project_path: Path = args.project_path.resolve()
    if not project_path.exists():
        print(f"error: {project_path} does not exist", file=sys.stderr)
        return 2

    rules = {r.strip() for r in args.rules.split(",") if r.strip()}
    report = run(project_path, apply=args.apply, rules=rules)
    print(format_report(report, project_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
