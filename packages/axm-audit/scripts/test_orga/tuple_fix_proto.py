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

    Current ``FILE_NAMING`` emits ``test_<a>__<b>.py`` (``__`` separator,
    PEP 8 compliant). This function is now a near-identity defensive
    pass: it strips any legacy ``-`` separators an older audit version
    could still produce, preserving forward compatibility without
    changing the proto's behaviour on output of the current rule.
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


def _tier_for_path(path: Path) -> str | None:
    """Return ``unit``/``integration``/``e2e`` for a test path, or None.

    Walks up the parents until a tier component is found. Tolerates
    nested test layouts like ``tests/integration/hooks/test_x.py``
    where ``path.parent.name`` is ``hooks`` rather than ``integration``.
    """
    for part in path.parts:
        if part in ("unit", "integration", "e2e"):
            return part
    return None


def flatten_tier_layout(project_path: Path) -> list[str]:
    """Flatten ``tests/integration/`` and ``tests/e2e/`` subdirectories.

    The AXM convention (CLAUDE.md) requires integration and e2e tests
    to live *directly* under their tier directory — no nested
    ``tests/integration/hooks/test_x.py``. This stage moves every
    nested ``test_*.py`` up to the tier root, renames on collision
    by prefixing the subdirectory name (``hooks/test_x.py`` →
    ``test_hooks_x.py``), rewrites importers via
    ``_rewrite_cross_test_imports``, and removes the now-empty
    subdirectories (preserving ``__init__.py`` / ``conftest.py`` by
    skipping the prune if those remain).

    Runs AFTER Stage 1 (RELOCATE) so it acts on the final tier
    classification, and BEFORE Stages 2-4 (SPLIT/MERGE/RENAME) which
    assume a flat layout.

    Unit tests intentionally MIRROR the source layout — nested
    subdirectories are correct there, so this stage skips ``tests/unit``.
    """
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    for tier in ("integration", "e2e"):
        tier_dir = tests_root / tier
        if not tier_dir.is_dir():
            continue
        msgs.extend(_flatten_single_tier(project_path, tier_dir))
    return msgs


def _flatten_single_tier(project_path: Path, tier_dir: Path) -> list[str]:
    """Move every nested ``test_*.py`` under *tier_dir* up to *tier_dir* root."""
    msgs: list[str] = []
    nested = sorted(
        p for p in tier_dir.rglob("test_*.py")
        if p.is_file() and p.parent != tier_dir
    )
    if not nested:
        return msgs
    for src in nested:
        rel_parents = src.relative_to(tier_dir).parts[:-1]
        target = tier_dir / src.name
        old_mod = _module_path_for_test_file(src, project_path)
        # Collision handling: prefix with subdir chain.
        if target.exists() and target != src:
            prefix = "_".join(rel_parents)
            stem = src.stem.removeprefix("test_")
            target = tier_dir / f"test_{prefix}_{stem}.py"
            # If even the prefixed name collides, append numeric suffix.
            counter = 2
            while target.exists():
                target = tier_dir / f"test_{prefix}_{stem}_{counter}.py"
                counter += 1
        src_depth = _file_depth_from_project(src, project_path)
        tgt_depth = _file_depth_from_project(target, project_path)
        _git_mv(src, target)
        depth_delta = tgt_depth - src_depth
        if depth_delta != 0:
            msgs.extend(_patch_file_dunder_depth(target, depth_delta))
        new_mod = _module_path_for_test_file(target, project_path)
        if old_mod and new_mod and old_mod != new_mod:
            msgs.extend(_rewrite_cross_test_imports(
                project_path, old_mod, [new_mod],
                skip_paths={src, target},
            ))
        msgs.append(
            f"flattened {src.relative_to(project_path)} -> "
            f"{target.relative_to(project_path)}"
        )
    # Prune now-empty subdirectories (keep dirs that still hold non-test
    # python files, e.g. ``__init__.py``, ``conftest.py``, helpers).
    _prune_empty_test_subdirs(tier_dir)
    return msgs


def _prune_empty_test_subdirs(tier_dir: Path) -> None:
    """Remove subdirectories under *tier_dir* that contain no ``test_*.py``.

    Walks bottom-up so empty parents become eligible after their
    children are removed. Always keeps the tier directory itself.
    ``__init__.py`` / ``conftest.py`` alone don't keep a subdir
    alive — they're scaffolding for tests that have moved out.
    """
    subdirs = sorted(
        (p for p in tier_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for sub in subdirs:
        if sub == tier_dir:
            continue
        has_test = any(
            f.is_file() and f.name.startswith("test_") and f.suffix == ".py"
            for f in sub.iterdir()
        )
        if has_test:
            continue
        # Remove scaffolding files, then the dir.
        for f in sub.iterdir():
            if f.is_file():
                rc = subprocess.run(
                    ["git", "rm", "-q", str(f)],
                    capture_output=True, text=True,
                )
                if rc.returncode != 0:
                    f.unlink()
        try:
            sub.rmdir()
        except OSError:
            pass


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
        tier_str = _tier_for_path(src)
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
        suggested = [s for s in suggested if s != "test_UNKNOWN.py"]
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
        if not proposed or src.name == proposed or proposed == "test_UNKNOWN.py":
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
    """Move *src* to *dst* via ``git mv``, with a non-destructive fallback.

    If *dst* already exists, the fallback ``shutil.move`` used to silently
    overwrite it — losing 25+ moved tests when RENAME / RELOCATE landed
    on a file the SPLIT/MERGE stages had just populated. Refuse to
    overwrite: raise ``FileExistsError`` so the caller (e.g.
    ``_execute_rename``) can re-route through ``_safe_move_units``.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file():
        raise FileExistsError(
            f"refusing to overwrite existing file {dst} with {src} via git_mv"
        )
    rc = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        shutil.move(str(src), str(dst))


def _patch_file_dunder_depth(
    file: Path,
    depth_delta: int,
) -> list[str]:
    """Rewrite ``Path(__file__).parents[N]`` / ``.parent.parent...`` after a move.

    When a file is relocated by *depth_delta* directory levels
    (``depth_delta = target_depth - source_depth``; negative if moved
    closer to project root, positive if moved deeper), any constant of
    the form ``Path(__file__).parents[N]`` or
    ``Path(__file__).parent.parent...`` will resolve to a different
    ancestor unless ``N`` is adjusted. We compute the new ``N`` so the
    constant continues to resolve to the *same* directory it did before
    the move:

        N_new = N_old + depth_delta

    Reasoning: a file at depth ``D`` has ``parents[N]`` at depth
    ``D - N - 1`` from project root. Moving the file to depth ``D'``
    means ``parents[N']`` is at ``D' - N' - 1``. For these to be equal,
    ``N' = N + (D' - D)`` = ``N + depth_delta``.

    Two surface forms supported (in order of preference, since some
    files mix them):

      * Subscript: ``Path(__file__).parents[N]`` (with optional
        ``.resolve()``). N is decremented by ``depth_delta``.
      * Chained: ``Path(__file__).parent.parent[.parent]*`` (with
        optional ``.resolve()``). The number of ``.parent`` accessors
        is reduced by ``depth_delta``.

    If the resulting N would be ``<= 0``, we leave the constant alone
    and emit a warning — the file was moved too close to root for the
    resolution to be expressible, indicating the relocate is suspect.
    """
    if depth_delta == 0 or not file.exists():
        return []
    module = _cst_load(file)
    if module is None:
        return []
    msgs: list[str] = []

    class _DunderPatcher(cst.CSTTransformer):
        def leave_Subscript(
            self,
            original_node: cst.Subscript,
            updated_node: cst.Subscript,
        ) -> cst.BaseExpression:
            # Match ``<expr>.parents[N]`` where <expr> reduces to
            # ``Path(__file__)`` (possibly via ``.resolve()``).
            value = updated_node.value
            if not isinstance(value, cst.Attribute):
                return updated_node
            if value.attr.value != "parents":
                return updated_node
            if not _is_file_dunder_chain(value.value):
                return updated_node
            slices = updated_node.slice
            if len(slices) != 1:
                return updated_node
            elt = slices[0].slice
            if not isinstance(elt, cst.Index):
                return updated_node
            n_node = elt.value
            if not isinstance(n_node, cst.Integer):
                return updated_node
            old_n = int(n_node.value)
            new_n = old_n + depth_delta
            if new_n <= 0:
                msgs.append(
                    f"file-depth-drift: refusing to patch {file.name} "
                    f"parents[{old_n}] (delta={depth_delta} would make "
                    f"N<=0; relocate suspicious)"
                )
                return updated_node
            msgs.append(
                f"file-depth-drift: {file.name} parents[{old_n}] -> "
                f"parents[{new_n}] (file moved by {depth_delta} level(s))"
            )
            return updated_node.with_changes(
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Index(value=cst.Integer(value=str(new_n)))
                    )
                ]
            )

        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:
            # Match chains ending in ``.parent`` — but only the OUTERMOST
            # ``.parent`` of a chain, so we don't double-patch nested
            # accesses. Identify by checking the parent attribute is NOT
            # itself ``.parent`` of the same chain — actually easier to
            # just rewrite the whole chain at once: count consecutive
            # ``.parent`` accessors and check the chain root is
            # ``Path(__file__)``.
            if updated_node.attr.value != "parent":
                return updated_node
            # Count chain length from this node going inward.
            count = 1
            inner: cst.BaseExpression = updated_node.value
            while (
                isinstance(inner, cst.Attribute)
                and inner.attr.value == "parent"
            ):
                count += 1
                inner = inner.value
            # `inner` is now the chain root. It must reduce to Path(__file__).
            if not _is_file_dunder_chain(inner):
                return updated_node
            # Skip if our parent (one level up) is also `.parent` — we
            # only patch the outermost chain link. Without parent info
            # here, we detect by re-entering: if `original_node` would
            # also be matched by an enclosing `leave_Attribute` call,
            # libcst visits children first — so we're the innermost
            # call by traversal order. Use a different strategy: only
            # rewrite when count > 1 AND the chain is the outermost
            # (no surrounding .parent). We can't know that from here
            # alone, so we conservatively skip count == 1 (a single
            # ``.parent`` is too ambiguous — could be re-bound) and
            # only patch chains of >= 2. The outermost-only constraint
            # is handled by a post-visit pass — see ``_PatchChainOnce``.
            return updated_node

    class _PatchChainOnce(cst.CSTTransformer):
        """Rewrite the outermost ``.parent.parent...`` chain on
        ``Path(__file__)`` exactly once.

        Two-pass alternative would be cleaner but more code; instead
        we identify outermost chains by their immediate parent context:
        if our own ``leave_Attribute`` is called for a node whose
        ``.value`` is the chain root (Path(__file__)) and whose
        outer enclosing isn't another ``.parent``, we rewrite.
        """

        def __init__(self) -> None:
            self._patched_ids: set[int] = set()

        def visit_Attribute(self, node: cst.Attribute) -> None:
            # Identify outermost chain on first pre-visit; rewrite
            # happens in leave_*.
            pass

        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:
            if id(original_node) in self._patched_ids:
                return updated_node
            if updated_node.attr.value != "parent":
                return updated_node
            # Chain root + count.
            count = 1
            inner: cst.BaseExpression = updated_node.value
            chain_ids = [id(original_node)]
            cur = original_node.value
            while (
                isinstance(inner, cst.Attribute)
                and inner.attr.value == "parent"
            ):
                count += 1
                chain_ids.append(id(cur))
                inner = inner.value
                if isinstance(cur, cst.Attribute):
                    cur = cur.value
            if not _is_file_dunder_chain(inner):
                return updated_node
            new_count = count + depth_delta
            if new_count <= 0:
                msgs.append(
                    f"file-depth-drift: refusing to patch {file.name} "
                    f"chain of {count} .parent (delta={depth_delta} "
                    f"would leave <=0 .parent; relocate suspicious)"
                )
                for cid in chain_ids:
                    self._patched_ids.add(cid)
                return updated_node
            # Rebuild: inner.parent × new_count.
            rebuilt: cst.BaseExpression = inner
            for _ in range(new_count):
                rebuilt = cst.Attribute(
                    value=rebuilt,
                    attr=cst.Name(value="parent"),
                )
            msgs.append(
                f"file-depth-drift: {file.name} "
                f".parent x{count} -> .parent x{new_count} "
                f"(file moved by {depth_delta} level(s))"
            )
            for cid in chain_ids:
                self._patched_ids.add(cid)
            return rebuilt

    # First pass: subscript form ``parents[N]``.
    new_module = module.visit(_DunderPatcher())
    assert isinstance(new_module, cst.Module)
    # Second pass: chained ``.parent.parent...`` form.
    new_module = new_module.visit(_PatchChainOnce())
    assert isinstance(new_module, cst.Module)
    if new_module.code != module.code:
        _cst_save(file, new_module)
    return msgs


def _is_file_dunder_chain(expr: cst.BaseExpression) -> bool:
    """True if *expr* is a syntactic ``Path(__file__)`` or
    ``Path(__file__).resolve()`` (possibly nested via ``Path(__file__)``)."""
    # Strip a trailing ``.resolve()`` call.
    if (
        isinstance(expr, cst.Call)
        and isinstance(expr.func, cst.Attribute)
        and expr.func.attr.value == "resolve"
        and not expr.args
    ):
        expr = expr.func.value
    # Must be ``Path(__file__)``.
    if not isinstance(expr, cst.Call):
        return False
    if not isinstance(expr.func, cst.Name) or expr.func.value != "Path":
        return False
    if len(expr.args) != 1:
        return False
    arg = expr.args[0].value
    return isinstance(arg, cst.Name) and arg.value == "__file__"


def _file_depth_from_project(path: Path, project_path: Path) -> int:
    """Number of path parts between *path*'s file and *project_path*.

    For ``/p/tests/unit/core/test_X.py`` under ``/p``, returns 4
    (``tests``, ``unit``, ``core``, ``test_X.py``). Independent of
    ``project_path``'s own depth. Used to compute ``depth_delta`` when
    a file is relocated, so ``Path(__file__).parents[N]`` constants
    can be re-pointed to the same ancestor.
    """
    try:
        rel = path.resolve().relative_to(project_path.resolve())
    except ValueError:
        return 0
    return len(rel.parts)


def _execute_relocate(op: FileOp, project_path: Path) -> list[str]:
    """RELOCATE op: ``git mv`` between pyramid tiers.

    Same collision risk as ``_execute_rename``: a target file may
    already exist (different package mapping happens to land on the
    same path). Route through ``_safe_move_units`` rather than letting
    ``_git_mv`` overwrite.
    """
    assert isinstance(op.target, Path)
    if op.target.is_file() and op.target != op.source:
        if not op.source.exists():
            return [f"relocate skipped: source missing ({op.source})"]
        warnings: list[str] = [
            f"relocate: target {op.target} already exists; "
            f"re-routing {op.source.name} through _safe_move_units"
        ]
        old_mod = _module_path_for_test_file(op.source, project_path)
        new_mod = _module_path_for_test_file(op.target, project_path)
        tree = ast.parse(op.source.read_text())
        units = _movable_units_at_top_level(tree)
        if units:
            sub_warnings, _ = _safe_move_units(
                op.source, op.target, units, project_path
            )
            warnings.extend(sub_warnings)
        _delete_source_if_empty_tests(op.source)
        if old_mod and new_mod and old_mod != new_mod and not op.source.exists():
            warnings.extend(_rewrite_cross_test_imports(
                project_path, old_mod, [new_mod],
                skip_paths={op.source, op.target},
            ))
        return warnings
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    _git_mv(op.source, op.target)
    warnings: list[str] = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod], skip_paths={op.source, op.target}
        ))
    return warnings


def _execute_rename(op: FileOp, project_path: Path) -> list[str]:
    """RENAME op: ``git mv`` the source file to its canonical name.

    When ``op.target`` already exists (typical when a prior SPLIT/MERGE
    stage created the canonical destination), a naive ``git mv`` would
    overwrite it and silently destroy the merged tests. Route through
    ``_safe_move_units`` instead — the residual source's units are
    moved into the existing target, then the source is deleted.
    """
    assert isinstance(op.target, Path)
    if op.target.is_file() and op.target != op.source:
        if not op.source.exists():
            return [
                f"rename skipped: source missing ({op.source})"
            ]
        warnings: list[str] = [
            f"rename: target {op.target.name} already exists; "
            f"re-routing {op.source.name} through _safe_move_units"
        ]
        old_mod = _module_path_for_test_file(op.source, project_path)
        new_mod = _module_path_for_test_file(op.target, project_path)
        tree = ast.parse(op.source.read_text())
        units = _movable_units_at_top_level(tree)
        if units:
            sub_warnings, _ = _safe_move_units(
                op.source, op.target, units, project_path
            )
            warnings.extend(sub_warnings)
        _delete_source_if_empty_tests(op.source)
        if old_mod and new_mod and old_mod != new_mod and not op.source.exists():
            warnings.extend(_rewrite_cross_test_imports(
                project_path, old_mod, [new_mod],
                skip_paths={op.source, op.target},
            ))
        return warnings
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    src_depth = _file_depth_from_project(op.source, project_path)
    tgt_depth = _file_depth_from_project(op.target, project_path)
    _git_mv(op.source, op.target)
    warnings = []
    depth_delta = tgt_depth - src_depth
    if depth_delta != 0:
        warnings.extend(_patch_file_dunder_depth(op.target, depth_delta))
    if old_mod and new_mod and old_mod != new_mod:
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod], skip_paths={op.source, op.target}
        ))
    return warnings


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
    # Top-level funcs. A canonical of ``test_UNKNOWN.py`` means the function
    # carries no first-party signal — leave it in the source file rather
    # than emit a nonsense target that ruff/audit will flag.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            name = _safe_filename(_func_canonical(
                node, tree, tier=tier, pkg_prefixes=pkg_prefixes,
                scripts=scripts, single_binary=single_binary,
            ))
            if name == "test_UNKNOWN.py":
                continue
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
            only = next(iter(method_canonicals))
            if only == "test_UNKNOWN.py":
                continue
            routes[only].append(cls.name)
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
    tier_str = _tier_for_path(op.source)
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
    original_source = op.source
    original_module = _module_path_for_test_file(original_source, project_path)
    post_split_paths: list[Path] = []
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
        post_split_paths.append(target)
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
        post_split_paths.append(target)
    elif op.source.exists():
        post_split_paths.append(op.source)
    # Rewrite cross-file importers — the original module path no longer
    # resolves; expand to the (possibly multiple) post-split modules.
    if original_module:
        new_modules = []
        seen: set[str] = set()
        for p in post_split_paths:
            mod = _module_path_for_test_file(p, project_path)
            if mod and mod != original_module and mod not in seen:
                new_modules.append(mod)
                seen.add(mod)
        if new_modules:
            warnings.extend(_rewrite_cross_test_imports(
                project_path, original_module, new_modules,
                skip_paths={original_source, *post_split_paths},
            ))
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
    # Two suffix forms: snake_case for functions (``test_x__from_foo``,
    # already PEP 8) and CapWords for classes (``TestX_FromFoo``).
    # Using snake_case on a class triggers ruff N801 because the
    # double-underscore disrupts CapWords parsing.
    stem = source.stem.removeprefix("test_")
    fn_suffix = f"__from_{stem}"
    # CapWords for classes: ``TestX`` + ``From`` + ``CapsStem`` =>
    # ``TestXFromCapsStem``. No leading underscore (ruff N801 reads
    # ``_`` as a CapWords break), no double-underscore.
    cls_suffix = "From" + "".join(p.capitalize() for p in stem.split("_") if p)
    source_class_names = {
        n.name for n in source_tree.body if isinstance(n, ast.ClassDef)
    }

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
        # Different bodies, or class collision → rename.
        # Pick the suffix variant that keeps the new identifier
        # lint-clean (N801 / CapWords for classes, snake_case for funcs).
        suffix = cls_suffix if name in source_class_names else fn_suffix
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

    # ----------------------------------------------------------------------
    # Helper-body conflict resolution (Bugs 1+3+4: _make_pkg / rich_pkg /
    # _make_project_with_test_callers signature drift across test files).
    #
    # The moving units carry references to top-level helpers/fixtures in
    # source. If the same name exists in target with a DIFFERENT body, the
    # moved tests bind to target's body at runtime and fail with
    # TypeError / AssertionError / "Symbol not found". Anvil's
    # ``shared_helpers="duplicate"`` doesn't help: when target already
    # declares the name, anvil skips the copy (and even if it duplicated,
    # the in-file def would shadow the import).
    #
    # Resolution: detect the conflict, rename the helper IN SOURCE (def
    # + every reference, in the whole module — both moving and remaining
    # tests get the new name in source; in target only the moved tests
    # get the new name via the copied helper). Now there's no name
    # collision, and anvil duplicates the helper cleanly.
    # ----------------------------------------------------------------------
    # Re-parse source: it may have been mutated by ``_rename_top_level_in_source``
    # above. final_units is the up-to-date list of names that will move.
    source_tree = ast.parse(source.read_text())
    helper_renames = _resolve_helper_conflicts(
        source_tree, target_tree, final_units, stem,
        target=target, project_path=project_path,
    )
    if helper_renames:
        _rename_name_in_module(source, helper_renames)
        for old, new in sorted(helper_renames.items()):
            warnings.append(
                f"helper-rename: {source.name}::{old} -> {new} "
                f"(body-mismatch with {target.name}::{old})"
            )

    # ----------------------------------------------------------------------
    # Conftest-shadowing resolution (Bug 4 residual: rich_pkg in
    # test_inspect_tool.py).
    #
    # When source has NO local def for a helper/fixture `H` (it uses a
    # conftest-provided one) but target HAS a local `H` that shadows
    # conftest, the moved tests bind to target's local `H` after the
    # move and break (different body). Resolution: rename target's
    # local `H` to ``H__local_<target_stem>`` (def + refs in target
    # ONLY, before move). Target's existing tests get the new name;
    # moved tests still reference `H` and pytest resolves to conftest.
    # ----------------------------------------------------------------------
    target_stem = target.stem.removeprefix("test_")
    target_local_renames = _resolve_conftest_shadowing(
        source_tree, target_tree, final_units,
        target, project_path, target_stem,
    )
    if target_local_renames:
        _rename_name_in_module(target, target_local_renames)
        # Re-parse target so the next steps (anvil move, post-checks)
        # see the renamed definitions.
        target_tree = ast.parse(target.read_text())
        for old, new in sorted(target_local_renames.items()):
            warnings.append(
                f"target-helper-rename: {target.name}::{old} -> {new} "
                f"(shadowed conftest fixture needed by moved tests)"
            )

    # ----------------------------------------------------------------------
    # ``@pytest.mark.usefixtures("X")`` tracking (Bug 2: _mock_flows /
    # _no_workspace).
    #
    # Anvil walks AST references on moving symbols but treats marker
    # arguments as string literals, not name references. Fixtures
    # injected via marker stay in source and disappear when source is
    # stripped to empty. We scan moving units for marker fixture names,
    # and if the fixture is defined in source and not in target (and not
    # in any conftest visible from target — for simplicity we check only
    # the test file level here), we add it to symbol_names so anvil moves
    # it alongside the tests.
    # ----------------------------------------------------------------------
    # Re-parse after possible rename so we see current state.
    source_tree = ast.parse(source.read_text())
    extra_fixtures = _collect_marker_fixtures_to_move(
        source_tree, target_tree, final_units, project_path, target
    )
    if extra_fixtures:
        final_units = list(final_units) + sorted(extra_fixtures)
        for fx in sorted(extra_fixtures):
            warnings.append(
                f"usefixtures-followup: moving fixture `{fx}` "
                f"from {source.name} alongside its dependents"
            )

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


def _top_level_helpers(
    tree: ast.Module,
) -> dict[str, tuple[str, ast.stmt]]:
    """Return ``{name: (body_hash, node)}`` for every top-level helper.

    A helper is a top-level FunctionDef / ClassDef that is NOT a test
    (``test_*`` / ``Test*``) plus single-target uppercase ``NAME = ...``
    constants. Fixtures (``@pytest.fixture``) are included — they're
    helpers from the body-conflict perspective.
    """
    out: dict[str, tuple[str, ast.stmt]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("test_"):
                continue
            out[node.name] = (_helper_body_hash(node), node)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("Test"):
                continue
            out[node.name] = (_helper_body_hash(node), node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id.isupper():
                out[tgt.id] = (_const_value_hash(node), node)
    return out


def _names_referenced_in_unit(node: ast.stmt) -> set[str]:
    """Return every ``ast.Name`` id referenced inside *node*.

    Used to determine which top-level helpers a moving unit (test_*
    function or Test* class) depends on. We also pick up marker
    arguments — ``@pytest.mark.usefixtures("X")`` is a string literal
    inside the decorator, NOT an ast.Name, so it's handled separately
    by ``_marker_fixtures_in_unit``.
    """
    return {
        n.id for n in ast.walk(node)
        if isinstance(n, ast.Name)
    }


def _resolve_helper_conflicts(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    source_stem: str,
    target: Path | None = None,
    project_path: Path | None = None,
) -> dict[str, str]:
    """Build a rename map for helpers whose body differs between source & target.

    For every top-level helper ``H`` referenced by a moving unit:

      * If ``H`` is in source AND in target with a different body hash
        (Bug 1/3 case), rename ``H`` in source to ``H__from_<stem>``.
        Anvil's ``shared_helpers="duplicate"`` then copies the renamed
        helper to target without collision.

      * If ``H`` is in source but NOT in target AND a conftest on
        target's ancestor chain provides a fixture named ``H``
        (Bug 4 residual: ``rich_pkg``), rename in source too. Reason:
        anvil would duplicate source's ``H`` into target, shadowing
        conftest — breaking any test in target (whether pre-existing
        or moved later) that relies on conftest's body. Renaming
        source's ``H`` keeps both worlds working: moved tests bind to
        the renamed helper (their original body), target's other
        tests bind to conftest.

    Helpers that are identical in source and target (same body_hash)
    don't need renaming — anvil's duplicate logic correctly skips the
    copy. Helpers only in source with no conftest shadow get
    duplicated as-is.
    """
    source_helpers = _top_level_helpers(source_tree)
    target_helpers = _top_level_helpers(target_tree)
    moving_nodes = [
        n for n in source_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
        and n.name in set(moving_unit_names)
    ]
    referenced: set[str] = set()
    for node in moving_nodes:
        referenced |= _names_referenced_in_unit(node)
        referenced |= _marker_fixtures_in_unit(node)
    conftest_fixtures: set[str] = set()
    if target is not None and project_path is not None:
        conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    rename: dict[str, str] = {}
    suffix = f"__from_{source_stem}"
    for name in sorted(referenced):
        if name not in source_helpers:
            continue
        if name in target_helpers:
            if source_helpers[name][0] == target_helpers[name][0]:
                continue
            # Different body in target → source-rename to avoid collision.
        elif name not in conftest_fixtures:
            continue
        new_name = name + suffix
        # If the renamed form already exists in source (idempotent re-run)
        # or in target (very rare), skip — leave the operator to inspect.
        if new_name in source_helpers or new_name in target_helpers:
            continue
        rename[name] = new_name
    return rename


def _resolve_conftest_shadowing(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    target: Path,
    project_path: Path,
    target_stem: str,
) -> dict[str, str]:
    """Build a rename map for target-local helpers that shadow conftest.

    Resolves Bug 4 residual (``rich_pkg`` in ``test_inspect_tool.py``).
    When a moved test references ``H`` (via parameter injection or
    ``@pytest.mark.usefixtures("H")``) AND:

      * source has no top-level ``H`` definition → source's tests
        relied on conftest's ``H``;
      * target has a top-level ``H`` definition → it would shadow
        conftest, binding the moved tests to the wrong body;
      * a conftest on target's ancestor chain provides ``H``.

    Then we rename target's local ``H`` to ``H__local_<target_stem>``
    (def + every reference inside target's existing tests). Target's
    own tests keep working with the renamed local; the soon-to-be-moved
    tests reference ``H`` and pytest resolves to conftest's version.
    """
    moving = set(moving_unit_names)
    moving_nodes = [
        n for n in source_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
        and n.name in moving
    ]
    if not moving_nodes:
        return {}
    referenced: set[str] = set()
    for node in moving_nodes:
        referenced |= _names_referenced_in_unit(node)
        referenced |= _marker_fixtures_in_unit(node)
    source_helpers = _top_level_helpers(source_tree)
    target_helpers = _top_level_helpers(target_tree)
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    rename: dict[str, str] = {}
    suffix = f"__local_{target_stem}"
    for name in sorted(referenced):
        if name in source_helpers:
            continue
        if name not in target_helpers:
            continue
        if name not in conftest_fixtures:
            continue
        new_name = name + suffix
        if new_name in target_helpers:
            continue
        rename[name] = new_name
    return rename


def _rename_name_in_module(path: Path, old_to_new: dict[str, str]) -> None:
    """Rename every occurrence of name X across module *path* (def + refs).

    Renames at three sites simultaneously:
      * the ``cst.FunctionDef`` / ``cst.ClassDef`` definition itself,
      * every ``cst.Name`` reference in the module body,
      * marker-argument string literals like
        ``@pytest.mark.usefixtures("X")`` so usefixtures still resolves
        after the rename.

    Preserves formatting via libcst. Unlike
    ``_rename_top_level_in_source`` (which only renames the def header
    — needed for cross-file move collisions), this rewrites references
    too — needed when source helpers get renamed to avoid colliding with
    target's same-named helpers.
    """
    if not old_to_new:
        return
    module = _cst_load(path)
    if module is None:
        return

    class _Renamer(cst.CSTTransformer):
        def __init__(self, mapping: dict[str, str]) -> None:
            self.mapping = mapping

        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.BaseExpression:
            if updated_node.value in self.mapping:
                return updated_node.with_changes(
                    value=self.mapping[updated_node.value]
                )
            return updated_node

        def leave_FunctionDef(
            self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef,
        ) -> cst.BaseStatement:
            if updated_node.name.value in self.mapping:
                return updated_node.with_changes(
                    name=cst.Name(
                        value=self.mapping[updated_node.name.value]
                    )
                )
            return updated_node

        def leave_ClassDef(
            self,
            original_node: cst.ClassDef,
            updated_node: cst.ClassDef,
        ) -> cst.BaseStatement:
            if updated_node.name.value in self.mapping:
                return updated_node.with_changes(
                    name=cst.Name(
                        value=self.mapping[updated_node.name.value]
                    )
                )
            return updated_node

        def leave_SimpleString(
            self,
            original_node: cst.SimpleString,
            updated_node: cst.SimpleString,
        ) -> cst.BaseExpression:
            # Rewrite ``@pytest.mark.usefixtures("X", "Y")`` argument
            # strings. Conservative: only rewrite the bare quoted value
            # if it matches a renamed name exactly. Pytest accepts both
            # single and double quotes; libcst preserves the prefix.
            raw = updated_node.value
            if len(raw) < 2:
                return updated_node
            quote = raw[0]
            if quote not in {'"', "'"}:
                return updated_node
            inner = raw[1:-1]
            if inner in self.mapping:
                return updated_node.with_changes(
                    value=f"{quote}{self.mapping[inner]}{quote}"
                )
            return updated_node

    new_module = module.visit(_Renamer(old_to_new))
    assert isinstance(new_module, cst.Module)
    _cst_save(path, new_module)


def _marker_fixtures_in_unit(node: ast.stmt) -> set[str]:
    """Return fixture names declared via ``@pytest.mark.usefixtures("X", ...)``.

    Scans the unit's decorator list (and its methods' decorator lists if
    it's a class) for ``pytest.mark.usefixtures`` calls and collects
    every string-literal argument. Other markers (``pytest.mark.parametrize``,
    ``pytest.mark.skipif``, ...) are ignored.
    """
    out: set[str] = set()
    nodes_to_scan: list[ast.AST] = [node]
    if isinstance(node, ast.ClassDef):
        nodes_to_scan.extend(
            sub for sub in node.body
            if isinstance(sub, ast.FunctionDef)
        )
    for n in nodes_to_scan:
        decorators = getattr(n, "decorator_list", []) or []
        for deco in decorators:
            if not isinstance(deco, ast.Call):
                continue
            # Match ``<...>.usefixtures(...)``
            fn = deco.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "usefixtures"):
                continue
            for arg in deco.args:
                if (
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                ):
                    out.add(arg.value)
    return out


def _collect_marker_fixtures_to_move(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    project_path: Path,
    target: Path,
) -> set[str]:
    """Return source-defined fixtures referenced via usefixtures markers.

    A fixture qualifies for follow-up move when:
      * It is referenced via ``@pytest.mark.usefixtures("X")`` on one
        of the moving units.
      * It is defined as a ``@pytest.fixture``-decorated function at
        the top level of *source*.
      * It is NOT already defined at the top level of *target* and NOT
        defined in a conftest visible to *target* (ancestor-chain).
    """
    moving = set(moving_unit_names)
    needed: set[str] = set()
    for node in source_tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name in moving:
            needed |= _marker_fixtures_in_unit(node)
    if not needed:
        return set()
    source_fixtures: dict[str, ast.FunctionDef] = {}
    for node in source_tree.body:
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node):
            source_fixtures[node.name] = node
    target_top_names = {
        n.name
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    return {
        name for name in needed
        if name in source_fixtures
        and name not in target_top_names
        and name not in conftest_fixtures
    }


def _collect_conftest_fixtures(target: Path, project_path: Path) -> set[str]:
    """Return fixtures defined in any conftest on target's ancestor chain.

    Walks from target's parent up to ``project_path`` (inclusive),
    parsing every ``conftest.py`` and collecting top-level
    ``@pytest.fixture``-decorated function names. Used to short-circuit
    follow-up moves when the marker fixture is already provided.
    """
    out: set[str] = set()
    cur = target.parent
    try:
        root = project_path.resolve()
    except OSError:
        return out
    while True:
        conftest = cur / "conftest.py"
        if conftest.exists():
            try:
                tree = ast.parse(conftest.read_text())
            except (SyntaxError, OSError):
                pass
            else:
                for node in tree.body:
                    if (
                        isinstance(node, ast.FunctionDef)
                        and _is_pytest_fixture(node)
                    ):
                        out.add(node.name)
        try:
            if cur.resolve() == root:
                break
        except OSError:
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return out


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
    old_mod = _module_path_for_test_file(op.source, project_path)
    new_mod = _module_path_for_test_file(op.target, project_path)
    warnings, _ = _safe_move_units(
        op.source, op.target, source_units, project_path
    )
    _delete_source_if_empty_tests(op.source)
    if old_mod and new_mod and old_mod != new_mod and not op.source.exists():
        warnings.extend(_rewrite_cross_test_imports(
            project_path, old_mod, [new_mod],
            skip_paths={op.source, op.target},
        ))
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


def _synth_import_from_helpers(
    name: str, project_path: Path, target: Path
) -> tuple[ast.stmt, ast.stmt | None] | None:
    """Synthesize ``from tests.<tier>._helpers import <name>`` if defined there.

    Scans every ``tests/<tier>/_helpers.py`` for a top-level ``def name``
    or ``class name`` or ``NAME = ...`` and returns a freshly-parsed
    ``ast.ImportFrom`` node ready to be transplanted by
    ``_backfill_missing_imports``. The second tuple element (enclosing
    block) is always ``None`` — these synthesized imports are top-level.
    """
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return None
    for tier in ("integration", "e2e", "unit"):
        helpers = tests_root / tier / "_helpers.py"
        if not helpers.is_file():
            continue
        try:
            tree = ast.parse(helpers.read_text())
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            defined = (
                (isinstance(node, ast.FunctionDef | ast.ClassDef)
                 and node.name == name)
                or (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == name
                )
            )
            if not defined:
                continue
            module = _module_path_for_test_file(helpers, project_path)
            if module is None:
                return None
            stmt = ast.parse(f"from {module} import {name}").body[0]
            return (stmt, None)
    return None


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
        # Last-resort fallback: scan ``tests/<tier>/_helpers.py`` for the
        # *definition* of ``name``. Covers the case where a freshly
        # extracted helper (promoted into ``_helpers.py``) is referenced
        # by another freshly extracted helper (promoted into ``conftest.py``
        # or another ``_helpers.py``) — neither donor file imports the
        # name, so the import-index fallback doesn't surface it. We
        # synthesise an ``from tests.<tier>._helpers import <name>``
        # statement so the destination ends up self-contained.
        still_missing2 = (
            missing - set(recoverable.keys())
        )
        if still_missing2 and project_path is not None:
            for name in still_missing2:
                synth = _synth_import_from_helpers(
                    name, project_path, target
                )
                if synth is not None:
                    recoverable[name] = synth

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


def _module_path_for_test_file(path: Path, project_path: Path) -> str | None:
    """Return the dotted module path used by ``from`` imports for *path*.

    For ``project/tests/integration/test_foo.py`` this returns
    ``tests.integration.test_foo``. Returns None if *path* is not under
    ``project_path/tests/``.
    """
    try:
        rel = path.resolve().relative_to(project_path.resolve())
    except ValueError:
        return None
    parts = rel.with_suffix("").parts
    if not parts or parts[0] != "tests":
        return None
    return ".".join(parts)


def _rewrite_cross_test_imports(
    project_path: Path,
    old_module: str,
    new_modules: list[str],
    skip_paths: set[Path],
) -> list[str]:
    """Rewrite ``from <old_module> import ...`` across the project.

    When a SPLIT/MERGE/RENAME changes which file owns the symbols
    previously imported via ``from tests.<old_stem> import <names>``,
    the importing test files must be rewritten or pytest collection
    breaks (real bug observed on axm-init: ``test_workspace_checks`` was
    split into N files but ``tests/unit/checks/test_workspace.py``
    still tried to import the now-missing module).

    Args:
        old_module: dotted module the importer used to reference.
        new_modules: replacement modules. For RENAME/MERGE this is a
            single-element list. For SPLIT this is the post-split list
            of canonical module paths.
        skip_paths: paths to skip (typically op.source, op.target).

    Returns: list of human-readable rewrite messages.
    """
    if not new_modules:
        return []
    skip_resolved = {p.resolve() for p in skip_paths}
    msgs: list[str] = []
    for py in project_path.rglob("*.py"):
        if py.resolve() in skip_resolved:
            continue
        try:
            text = py.read_text()
        except OSError:
            continue
        if old_module not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        # Locate the matching ImportFrom node(s).
        edits: list[tuple[ast.ImportFrom, str]] = []
        text_lines = text.splitlines()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == old_module
            ):
                names_segment = ", ".join(
                    a.name if a.asname is None else f"{a.name} as {a.asname}"
                    for a in node.names
                )
                # Preserve a trailing ``# noqa`` (or any other tail
                # comment) from the original import line — useful for
                # ``from x import *  # noqa: F403`` patterns.
                trailing = ""
                orig_line = text_lines[node.lineno - 1] if 0 <= node.lineno - 1 < len(text_lines) else ""
                hash_idx = orig_line.find("#")
                if hash_idx != -1:
                    trailing = "  " + orig_line[hash_idx:].rstrip()
                replacement_lines = [
                    f"from {mod} import {names_segment}{trailing}"
                    for mod in new_modules
                ]
                edits.append((node, "\n".join(replacement_lines)))
        if not edits:
            continue
        lines = text.splitlines(keepends=True)
        # Sort descending by lineno so earlier edits don't shift later offsets.
        edits.sort(key=lambda e: e[0].lineno, reverse=True)
        for node, replacement in edits:
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            # Preserve trailing newline of the original block.
            had_trailing_nl = lines[end - 1].endswith("\n")
            tail = "\n" if had_trailing_nl else ""
            lines[start:end] = [replacement + tail]
        py.write_text("".join(lines))
        msgs.append(
            f"rewrote import in {py.relative_to(project_path)}: "
            f"{old_module} -> {new_modules}"
        )
    return msgs


def _extract_shared_helpers(project_path: Path) -> list[str]:
    """Iterate ``_extract_shared_helpers_once`` until fixed-point.

    A single pass cannot catch every duplicate: promoting helper A can
    expose helper B as duplicate (e.g. A's body referenced B locally,
    so B looked non-shared until A moved out). Loop until no further
    extraction happens. Capped at ``_EXTRACT_MAX_ITERS`` to fail loud
    on a buggy fixed-point.

    ``ambiguous fixture`` messages are re-emitted on every iteration
    (the same fixtures stay ambiguous forever) — collapse them so the
    operator sees each one exactly once.
    """
    all_msgs: list[str] = []
    seen_ambiguous: set[str] = set()
    for _ in range(_EXTRACT_MAX_ITERS):
        msgs = _extract_shared_helpers_once(project_path)
        # Real progress = any non-ambiguous message produced.
        progress = [m for m in msgs if "ambiguous fixture" not in m]
        deduped: list[str] = list(progress)
        for m in msgs:
            if "ambiguous fixture" in m and m not in seen_ambiguous:
                seen_ambiguous.add(m)
                deduped.append(m)
        all_msgs.extend(deduped)
        if not progress:
            break
    return all_msgs


_EXTRACT_MAX_ITERS = 10


def _extract_shared_helpers_once(project_path: Path) -> list[str]:
    """Promote helpers duplicated across a tier into ``tests/<tier>/_helpers.py``.

    Anvil's ``shared_helpers="duplicate"`` mode (the only one currently
    implemented — ``"extract"`` is reserved for Phase 3) leaves a copy
    of every shared helper in each post-move file. After SPLIT this
    means N identical copies of helpers like ``gold_project``, ``_make_result``.
    We collapse those copies into a single module-level definition in
    ``tests/<tier>/_helpers.py`` and rewrite call sites with an import.

    Algorithm:
        1. For each tier (integration, e2e, unit), walk every test file
           and collect top-level *helper* defs — i.e. ``def name(...)`` /
           ``class Name(...)`` that does NOT start with ``test_`` /
           ``Test`` (so we never touch test functions themselves).
        2. Group by ``(name, body_hash)``. If a group has >=2 files,
           the helper is a real duplicate (same body, different files).
        3. Move the canonical definition to ``tests/<tier>/_helpers.py``
           (append if file exists, create otherwise). Strip the
           duplicated def from each file, prepend an import.
        4. Helpers whose names collide across tiers but with different
           bodies are left alone (rare; safer than guessing).

    We deliberately do NOT convert helpers into ``@pytest.fixture``
    here — fixture migration requires per-call-site signature analysis
    (uniform args? multiple calls per test? cascade dependencies?)
    and is the proper job of ``axm-anvil`` Phase 3. See
    README_FIX_PROTO.md for the rationale.

    Returns: list of human-readable extraction messages.
    """
    msgs: list[str] = []
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return msgs
    for tier in ("integration", "e2e", "unit"):
        tier_dir = tests_root / tier
        if not tier_dir.is_dir():
            continue
        msgs.extend(_extract_shared_helpers_in_tier(project_path, tier_dir))
    return msgs


def _extract_shared_helpers_in_tier(
    project_path: Path, tier_dir: Path
) -> list[str]:
    """Process a single tier. Splitting per-tier keeps imports local."""
    # Gather candidate helper defs per file. We capture the source text
    # NOW (before any mutation) so subsequent strip operations on one
    # file don't invalidate cached lineno/col offsets of helpers
    # discovered in other files. We also tag each helper as ``fixture``
    # (decorated with ``@pytest.fixture``) or ``pure`` — the destination
    # differs: fixtures go to ``conftest.py`` (pytest auto-discovery
    # requires it), pures go to ``_helpers.py`` with explicit import.
    per_file: dict[Path, dict[str, tuple[str, str, str]]] = {}
    # Names that were ignored upstream (e.g. ``FIXTURES = Path(__file__)...``)
    # — never enter ``by_name`` but cascade-skipped consumers must see
    # them as unavailable dependencies.
    location_skipped_names: set[str] = set()
    for py in tier_dir.rglob("*.py"):
        if py.name in {"__init__.py", "conftest.py", "_helpers.py"}:
            continue
        try:
            text = py.read_text()
            tree = ast.parse(text)
        except (SyntaxError, OSError):
            continue
        helpers: dict[str, tuple[str, str, str]] = {}
        for node in tree.body:
            name: str | None = None
            body_hash: str | None = None
            kind: str = "pure"
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    continue
                name, body_hash = node.name, _helper_body_hash(node)
                if _is_pytest_fixture(node):
                    kind = "fixture"
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("Test"):
                    continue
                name, body_hash = node.name, _helper_body_hash(node)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and tgt.id.isupper():
                    # Skip constants that reference ``__file__`` — their
                    # value depends on the file's *physical location*.
                    # Promoting ``FIXTURES = Path(__file__).parent.parent``
                    # from a tests/unit/foo.py file to tests/unit/_helpers.py
                    # silently breaks downstream consumers because
                    # ``Path(__file__).parent.parent`` now resolves to the
                    # tests dir instead of the package root. Each
                    # original file must keep its own copy.
                    if _references_file_dunder(node.value):
                        # Record the name so cascade skips can see it as
                        # an unavailable dependency of other candidates.
                        location_skipped_names.add(tgt.id)
                        continue
                    name, body_hash = tgt.id, _const_value_hash(node)
            if name is None or body_hash is None:
                continue
            src_seg = _source_segment_with_decorators(text, node)
            if src_seg is None:
                continue
            helpers[name] = (src_seg, body_hash, kind)
        if helpers:
            per_file[py] = helpers
    # Group by (name, body_hash) → list of files, keyed by kind too so
    # that an extracted fixture doesn't collide with a same-named pure
    # helper in another file (unlikely but cheap to be defensive).
    by_signature: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for py, helpers in per_file.items():
        for h_name, (_, body_hash, kind) in helpers.items():
            by_signature[(h_name, body_hash, kind)].append(py)
    # Only true duplicates (>=2 files with same body) qualify for extraction.
    # When the same name has multiple bodies, the policy depends on kind:
    #   * pure helpers — pick the largest group, leave the minority bodies
    #     in place. They're a different helper that happens to share the
    #     name; promoting the majority wins most of the deduplication
    #     without overwriting divergent semantics.
    #   * fixtures — refuse to extract entirely. Multiple bodies for
    #     a fixture name almost always indicate an intentional override
    #     pattern (a richer local fixture overriding a baseline conftest),
    #     and stripping the local one silently regresses the dependent
    #     tests. Report these as ``ambiguous_fixtures`` for the operator.
    skip_msgs: list[str] = []
    # Names that won't make it into ``_helpers.py`` — used to detect
    # cascading dependencies (a constant that references a skipped name
    # would NameError after extraction). Seeded with names already
    # filtered out upstream (e.g. ``Path(__file__)`` constants).
    skipped_names: set[str] = set(location_skipped_names)
    by_name: dict[str, list[tuple[str, str, list[Path]]]] = defaultdict(list)
    for (h_name, body_hash, kind), files in by_signature.items():
        by_name[h_name].append((body_hash, kind, files))
    # Collect dependency edges: for every candidate, which other
    # candidates (or already-skipped names) does it reference in its
    # body? Used to cascade skips when an extractable constant
    # depends on a non-extractable one (e.g. ``SAMPLE_PKG = FIXTURES / "x"``
    # where ``FIXTURES`` was skipped for using ``Path(__file__)``).
    deps_by_name: dict[str, set[str]] = defaultdict(set)
    known_names = set(by_name) | location_skipped_names
    for py, helpers_dict in per_file.items():
        for h_name, (src_text, _hash, _kind) in helpers_dict.items():
            try:
                sub_tree = ast.parse(src_text)
            except SyntaxError:
                continue
            referenced = {
                n.id for n in ast.walk(sub_tree)
                if isinstance(n, ast.Name) and n.id != h_name
            }
            deps_by_name[h_name] |= referenced & known_names
    duplicates: dict[tuple[str, str, str], list[Path]] = {}
    for h_name, groups in by_name.items():
        kinds = {k for _, k, _ in groups}
        # Refuse to extract any helper (fixture, pure function, class,
        # constant) whose name has divergent bodies across the tier.
        # Multi-body means callers depend on *different* implementations
        # — picking the majority and stripping the minority silently
        # breaks the minority's consumers. Real cases observed:
        #   * fixtures with intentional local override (gold_project)
        #   * helpers ``_make_pkg`` whose signature evolved across
        #     files (axm-ast: 11 TypeError unexpected keyword)
        #   * fixtures ``workspace_repo`` that commit vs. don't commit
        if len(groups) > 1:
            # Build a per-body inventory so the operator can review
            # without grepping. Each line lists the body hash and its
            # host files, so divergence is visible at a glance.
            groups.sort(key=lambda g: (-len(g[2]), g[0]))
            kind_label = (
                "fixture" if "fixture" in kinds
                else "helper" if "pure" in kinds
                else "constant"
            )
            body_lines = []
            for idx, (body_hash, _kind, files) in enumerate(groups, 1):
                files_rel = sorted(
                    str(f.relative_to(project_path)) for f in files
                )
                body_lines.append(
                    f"    body#{idx} ({body_hash[:8]}, {len(files)} file(s)): "
                    + ", ".join(files_rel)
                )
            file_count = sum(len(files) for _, _, files in groups)
            skip_msgs.append(
                f"ambiguous {kind_label} `{h_name}` not extracted: "
                f"{len(groups)} divergent bodies across {file_count} files "
                "(likely intentional override or signature drift — "
                "review manually):\n"
                + "\n".join(body_lines)
                + "\n    Resolution: keep each body where its callers "
                "depend on it, or unify the bodies and remove the "
                "others; consumers of the wrong body fail silently "
                "with state-mismatch / TypeError, not ImportError."
            )
            skipped_names.add(h_name)
            continue
        # Largest group wins; ties broken by hash for determinism.
        groups.sort(key=lambda g: (-len(g[2]), g[0]))
        winning_hash, winning_kind, winning_files = groups[0]
        if len(winning_files) < 2:
            continue
        duplicates[(h_name, winning_hash, winning_kind)] = winning_files
    # Cascade skips: if a candidate references any already-skipped
    # name, extracting it would NameError at import time of
    # ``_helpers.py``. Propagate to fixpoint.
    changed = True
    while changed:
        changed = False
        for h_name, refs in deps_by_name.items():
            if h_name in skipped_names:
                continue
            cascade_blockers = refs & skipped_names
            if cascade_blockers:
                # Find and remove this name from duplicates if present.
                for sig in list(duplicates):
                    if sig[0] == h_name:
                        del duplicates[sig]
                        skip_msgs.append(
                            f"cascading skip `{h_name}` not extracted: "
                            f"references skipped name(s) "
                            f"{sorted(cascade_blockers)} — extracting it "
                            "alone would NameError at import time."
                        )
                        skipped_names.add(h_name)
                        changed = True
                        break

    if not duplicates and not skip_msgs:
        return []
    if not duplicates:
        return skip_msgs
    msgs: list[str] = []
    helpers_path = tier_dir / "_helpers.py"
    # Fixtures land in the tests-root conftest so that cross-tier
    # ``from tests.<tier>.X import *`` re-exports (the pattern used to
    # satisfy ``PRACTICE_TEST_MIRROR``) still find them. Tier-local
    # conftest would scope-out unit/e2e consumers of an integration
    # fixture and break them silently.
    conftest_path = tier_dir.parent / "conftest.py"
    helpers_module_path = _module_path_for_test_file(helpers_path, project_path)
    if helpers_module_path is None:
        return []
    # Two destinations: pure helpers go to ``_helpers.py`` (explicit
    # import in each consumer), fixtures go to ``conftest.py`` (pytest
    # auto-discovery, no import needed). Routing by ``kind`` preserves
    # pytest semantics — extracting a fixture into ``_helpers.py``
    # would break ``def test_x(my_fixture)`` injection.
    helpers_module = _load_or_create_helpers_module(
        helpers_path, tier_dir.name, helpers_module_path
    )
    conftest_module = _load_or_create_conftest_module(conftest_path)
    if helpers_module is None or conftest_module is None:
        return []
    helpers_existing = {
        s.name.value
        for s in helpers_module.body
        if isinstance(s, cst.FunctionDef | cst.ClassDef)
    }
    conftest_existing = {
        s.name.value
        for s in conftest_module.body
        if isinstance(s, cst.FunctionDef | cst.ClassDef)
    }
    helpers_body = list(helpers_module.body)
    conftest_body = list(conftest_module.body)
    helpers_touched = False
    conftest_touched = False
    sorted_dups = sorted(duplicates.items(), key=lambda kv: kv[0][0])
    for (name, _, kind), files in sorted_dups:
        canonical_file = sorted(files)[0]
        canonical_src = per_file[canonical_file][name][0]
        try:
            parsed = cst.parse_module(canonical_src).body
        except cst.ParserSyntaxError:
            continue
        if kind == "fixture":
            if name not in conftest_existing:
                conftest_body.extend(parsed)
                conftest_existing.add(name)
                conftest_touched = True
                msgs.append(
                    f"extracted fixture `{name}` -> "
                    f"{conftest_path.relative_to(project_path)} "
                    f"(was duplicated in {len(files)} files)"
                )
            # Fixtures: strip from each file. NO import needed — pytest
            # auto-discovers via conftest in the test's directory tree.
            for f in files:
                _strip_def_only(f, name)
        else:
            if name not in helpers_existing:
                helpers_body.extend(parsed)
                helpers_existing.add(name)
                helpers_touched = True
                msgs.append(
                    f"extracted helper `{name}` -> "
                    f"{helpers_path.relative_to(project_path)} "
                    f"(was duplicated in {len(files)} files)"
                )
            # Pure helpers: strip + add explicit import.
            for f in files:
                _strip_def_and_inject_import(
                    f, name, helpers_module_path, project_path
                )
    if helpers_touched:
        _cst_save(helpers_path, helpers_module.with_changes(body=helpers_body))
    if conftest_touched:
        _cst_save(conftest_path, conftest_module.with_changes(body=conftest_body))
    # Backfill any names referenced by the freshly-added defs but not
    # yet imported in the destination module. Each destination is
    # backfilled from an arbitrary donor file in the tier — names lived
    # there originally; ``_scan_tests_for_import`` is the cross-file
    # fallback for everything else.
    donor = next(iter(per_file.keys()), None)
    if donor is not None:
        if helpers_touched:
            msgs.extend(
                _backfill_missing_imports(donor, helpers_path, project_path)
            )
        if conftest_touched:
            msgs.extend(
                _backfill_missing_imports(donor, conftest_path, project_path)
            )
    # Surface skipped ambiguous fixtures so the operator can decide.
    msgs.extend(skip_msgs)
    return msgs


def _is_pytest_fixture(node: ast.FunctionDef) -> bool:
    """True if *node* has a ``@pytest.fixture`` (or bare ``@fixture``) decorator."""
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        # ``@pytest.fixture`` / ``@pytest.fixture(...)``
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "pytest"
            and target.attr == "fixture"
        ):
            return True
        # ``@fixture`` / ``@fixture(...)`` (when imported directly)
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def _load_or_create_helpers_module(
    helpers_path: Path, tier_name: str, helpers_module_path: str
) -> cst.Module | None:
    if helpers_path.exists():
        return _cst_load(helpers_path)
    return cst.parse_module(
        f'"""Shared helpers for ``tests/{tier_name}``.\n\n'
        "Promoted from duplicate top-level defs found across files.\n"
        f"Import explicitly: ``from {helpers_module_path} import <name>``.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def _load_or_create_conftest_module(conftest_path: Path) -> cst.Module | None:
    if conftest_path.exists():
        return _cst_load(conftest_path)
    return cst.parse_module(
        '"""Pytest fixtures auto-discovered by tests in this directory.\n\n'
        "Promoted from duplicate ``@pytest.fixture`` definitions originally\n"
        "scattered across multiple test files.\n"
        '"""\n\n'
        "from __future__ import annotations\n"
    )


def _strip_def_only(file: Path, name: str) -> None:
    """Remove the top-level def of *name* from *file* without injecting an import.

    Used for fixtures whose new home (``conftest.py``) is auto-discovered
    by pytest — no import would be valid syntactically (it would shadow
    the injected fixture parameter) and none is needed.
    """
    module = _cst_load(file)
    if module is None:
        return
    new_body: list[cst.BaseStatement] = []
    stripped = False
    for stmt in module.body:
        if (
            isinstance(stmt, cst.FunctionDef | cst.ClassDef)
            and stmt.name.value == name
        ):
            stripped = True
            continue
        new_body.append(stmt)
    if stripped:
        _cst_save(file, module.with_changes(body=new_body))


def _source_segment_with_decorators(text: str, node: ast.AST) -> str | None:
    """Like ``ast.get_source_segment`` but includes the decorator lines.

    ``ast.get_source_segment`` returns the segment starting at ``node.lineno``,
    which for a decorated function/class is the ``def``/``class`` line —
    decorators are lost. We extend the start back to the first decorator's
    lineno so that ``@pytest.fixture()`` is preserved when relocating a
    fixture to ``conftest.py``.
    """
    base = ast.get_source_segment(text, node)
    if base is None:
        return None
    decorators = getattr(node, "decorator_list", None)
    if not decorators:
        return base
    first_deco_line = min(d.lineno for d in decorators)
    lines = text.splitlines(keepends=True)
    prefix = "".join(lines[first_deco_line - 1 : node.lineno - 1])
    return prefix + base


def _helper_body_hash(node: ast.FunctionDef | ast.ClassDef) -> str:
    """Hash a helper's body via ast.dump (stable, ignores comments).

    We hash body only so that two functions with identical body but
    different decorators are still treated as duplicates — decorator
    order/format is irrelevant to runtime semantics for normal helpers.
    """
    import hashlib
    body_repr = "\n".join(ast.dump(s, annotate_fields=False) for s in node.body)
    return hashlib.sha1(body_repr.encode()).hexdigest()[:12]


def _const_value_hash(node: ast.Assign) -> str:
    """Hash a module-level constant assignment."""
    import hashlib
    return hashlib.sha1(ast.dump(node.value).encode()).hexdigest()[:12]


def _references_file_dunder(node: ast.AST) -> bool:
    """True if *node* tree contains any reference to ``__file__``."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == "__file__":
            return True
    return False


def _strip_def_and_inject_import(
    file: Path, name: str, helpers_module: str, project_path: Path
) -> None:
    """Remove the top-level def of ``name`` from *file* and import it instead."""
    module = _cst_load(file)
    if module is None:
        return
    new_body: list[cst.BaseStatement] = []
    stripped = False
    for stmt in module.body:
        if (
            isinstance(stmt, cst.FunctionDef | cst.ClassDef)
            and stmt.name.value == name
        ):
            stripped = True
            continue
        # Module-level constant: ``NAME = ...`` (single-target Assign)
        if (
            isinstance(stmt, cst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], cst.Assign)
            and len(stmt.body[0].targets) == 1
            and isinstance(stmt.body[0].targets[0].target, cst.Name)
            and stmt.body[0].targets[0].target.value == name
        ):
            stripped = True
            continue
        new_body.append(stmt)
    if not stripped:
        return
    # Inject ``from <helpers_module> import <name>`` after the existing
    # top-level imports (or at the very top after the docstring).
    import_stmt = cst.parse_statement(
        f"from {helpers_module} import {name}"
    )
    assert isinstance(import_stmt, cst.SimpleStatementLine)
    insert_at = 0
    for idx, stmt in enumerate(new_body):
        if _is_cst_import(stmt) or (
            isinstance(stmt, cst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], cst.Expr)
            and isinstance(stmt.body[0].value, cst.SimpleString | cst.ConcatenatedString)
        ):
            insert_at = idx + 1
        else:
            break
    new_body.insert(insert_at, import_stmt)
    new_module = module.with_changes(body=new_body)
    new_module = _dedupe_imports_cst(new_module)
    _cst_save(file, new_module)


def execute(ops: list[FileOp], project_path: Path) -> list[str]:
    """Apply ops in order. Returns aggregated warnings."""
    warnings: list[str] = []
    for op in ops:
        if op.kind == "flatten":
            warnings.extend(_execute_flatten(op, project_path))
        elif op.kind == "relocate":
            warnings.extend(_execute_relocate(op, project_path))
        elif op.kind == "rename":
            warnings.extend(_execute_rename(op, project_path))
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

    # Stage 1.5: FLATTEN_LAYOUT. Bring nested ``tests/integration/<subdir>/``
    # and ``tests/e2e/<subdir>/`` files up to the tier root so Stages 2-4
    # operate on the AXM-standard flat layout. Skipped for unit tests
    # which intentionally mirror src/ structure.
    if apply and "TEST_QUALITY_PYRAMID_LEVEL" in rules:
        flatten_msgs = flatten_tier_layout(project_path)
        if flatten_msgs:
            warnings.extend(flatten_msgs)
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

    # Post-pipeline polish: extract shared helpers (collapse duplicates
    # left by anvil's ``shared_helpers="duplicate"`` into a single
    # ``tests/<tier>/_helpers.py`` module), then run ruff fix + format.
    if apply:
        extraction_msgs = _extract_shared_helpers(project_path)
        warnings.extend(extraction_msgs)
        # Each extracted helper retroactively resolves any anvil
        # ``Helper '<name>' ... — duplicated in target`` warning for
        # that same name. Drop the obsolete warnings to keep the
        # report aligned with the final state on disk.
        extracted_names = {
            m.split("`")[1] for m in extraction_msgs
            if (
                m.startswith("extracted helper `")
                or m.startswith("extracted fixture `")
            )
            and "`" in m
        }
        if extracted_names:
            warnings = [
                w for w in warnings
                if not (
                    "duplicated in target" in w
                    and any(f"Helper '{n}'" in w for n in extracted_names)
                )
            ]
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
