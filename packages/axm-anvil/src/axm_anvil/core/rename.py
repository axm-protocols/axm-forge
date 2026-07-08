"""In-place symbol rename across a workspace.

:func:`rename_symbols` renames one or more top-level symbols *in place* in
their defining module (definition + internal usages) and rewrites every
cross-file caller that imports the renamed names from that module. Unlike
:func:`axm_anvil.core.move.move_symbols`, no block is copied between files:
the symbol keeps its module, only its name changes.

The rewrite reuses :class:`axm_anvil._cst.transformers.RenameSymbols` for
both the defining module and the callers. Applied to a caller, ``RenameSymbols``
rewrites the imported alias (``from mod import Old`` -> ``from mod import New``)
and every bare-name usage in a single pass; attribute *members* (``obj.Old``)
are deliberately left untouched.

Caller discovery is **pattern-based on the import statement** (it scans for
``from <module> import <name>`` via :func:`_discover_callers`). The following
cases are intentionally NOT handled and are deferred to Tier 2.1:

* shadowing — a local binding named like a renamed symbol in a caller is
  rewritten blindly (no scope analysis on the rename path);
* aliased imports / alias chains — ``from mod import Old as O`` rewrites the
  ``Old`` token but downstream ``O`` usages are not reconciled;
* re-exports / star imports — symbols reached through ``import *`` or a
  re-export module are not discovered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst

from axm_anvil._cst.transformers import RenameSymbols
from axm_anvil.core.callers import (
    CallerRewrite,
    _discover_callers,
    _module_path_from_file,
)
from axm_anvil.core.move import batch_edit
from axm_anvil.core.plan import (
    MoveValidationError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)

__all__ = ["RenamePlan", "rename_symbols"]


@dataclass
class RenamePlan:
    """Result of a :func:`rename_symbols` call.

    Carries the rewritten text of the defining module, the names that were
    actually renamed (``old -> new``), the caller-file rewrites and any
    non-fatal warnings (e.g. a requested symbol that was absent in
    non-strict mode).
    """

    source_text_new: str
    renamed: dict[str, str]
    callers_updated: list[CallerRewrite] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


def _top_level_names(tree: cst.Module) -> set[str]:
    """Return the names of top-level functions, classes and assignments."""
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
            names.add(stmt.name.value)
        elif isinstance(stmt, cst.SimpleStatementLine):
            for small in stmt.body:
                names.update(_assignment_targets(small))
    return names


def _assignment_targets(node: cst.BaseSmallStatement) -> set[str]:
    """Return bare-name targets bound by an assignment small-statement."""
    targets: set[str] = set()
    if isinstance(node, cst.Assign):
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                targets.add(target.target.value)
    elif isinstance(node, cst.AnnAssign) and isinstance(node.target, cst.Name):
        targets.add(node.target.value)
    return targets


def _resolve_mapping(
    present: set[str], mapping: dict[str, str], *, strict: bool
) -> tuple[dict[str, str], list[str]]:
    """Split ``mapping`` into present renames and skip warnings.

    A requested ``old`` name absent from the module's top-level symbols is
    skipped with a warning (non-strict) or raises
    :class:`SymbolNotFoundError` (strict).
    """
    active: dict[str, str] = {}
    warnings: list[str] = []
    for old, new in mapping.items():
        if old not in present:
            if strict:
                raise SymbolNotFoundError(old)
            warnings.append(f"symbol {old!r} not found in module; skipped")
            continue
        if new != old and new in present:
            # Renaming onto an existing top-level name would produce two
            # definitions of ``new`` in the same module (the second silently
            # shadows the first at import). Refuse the collision.
            raise SymbolAlreadyExistsError(new)
        active[old] = new
    return active, warnings


def _render_renamed(text: str, mapping: dict[str, str]) -> str:
    """Apply ``RenameSymbols`` to ``text`` and validate the result parses."""
    tree = cst.parse_module(text)
    wrapper = cst.MetadataWrapper(tree)
    new_tree = wrapper.visit(RenameSymbols(mapping))
    rendered = new_tree.code
    try:
        cst.parse_module(rendered)
    except Exception as exc:
        raise MoveValidationError(rendered, exc) from exc
    return rendered


def _rewrite_callers(
    root: Path,
    source_path: Path,
    mapping: dict[str, str],
) -> tuple[dict[Path, tuple[str, str]], list[CallerRewrite]]:
    """Rewrite every caller importing a renamed name from ``source_path``.

    Returns ``(caller_texts, rewrites)`` where ``caller_texts`` maps each
    caller path to ``(original_text, new_text)`` for the atomic write.
    """
    try:
        from_module = _module_path_from_file(source_path, root)
    except ValueError:
        return {}, []
    callers = _discover_callers(root, list(mapping), from_module, exclude=[source_path])
    caller_texts: dict[Path, tuple[str, str]] = {}
    rewrites: list[CallerRewrite] = []
    for caller_path in callers:
        try:
            original = caller_path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        rewritten = _render_renamed(original, mapping)
        if rewritten == original:
            continue
        caller_texts[caller_path] = (original, rewritten)
        rel = _caller_relpath(caller_path, root)
        rewrites.append(
            CallerRewrite(file=rel, line=0, old=from_module, new=from_module)
        )
    return caller_texts, rewrites


def _caller_relpath(caller_path: Path, root: Path) -> str:
    try:
        return str(caller_path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(caller_path)


def rename_symbols(  # noqa: PLR0913
    path: str | Path,
    file: str | Path,
    mapping: dict[str, str],
    *,
    dry_run: bool = False,
    workspace_root: Path | None = None,
    strict: bool = False,
) -> RenamePlan:
    """Rename top-level symbols in ``file`` and rewrite cross-file callers.

    Parameters
    ----------
    path:
        Workspace root used to resolve a relative ``file`` and to constrain
        caller discovery.
    file:
        Python file defining the symbols. Relative paths resolve against
        ``path``.
    mapping:
        ``{old_name: new_name}`` for the top-level symbols to rename.
    dry_run:
        When ``True``, compute the :class:`RenamePlan` without writing.
    workspace_root:
        Explicit workspace root; falls back to the nearest ancestor with a
        ``pyproject.toml`` when ``None``.
    strict:
        When ``True`` a requested ``old`` name absent from the module raises
        :class:`SymbolNotFoundError`; when ``False`` (default) it is skipped
        with a warning on :attr:`RenamePlan.warnings`.

    Returns
    -------
    RenamePlan
        The rewritten module text, the active renames, caller rewrites and
        warnings. Caller rewriting is pattern-based on imports; see the
        module docstring for the uncovered cases.
    """
    root = Path(workspace_root) if workspace_root is not None else Path(path).resolve()
    source_path = Path(file)
    if not source_path.is_absolute():
        source_path = root / source_path

    source_text = source_path.read_text()
    source_tree = cst.parse_module(source_text)

    active, warnings = _resolve_mapping(
        _top_level_names(source_tree), mapping, strict=strict
    )
    if not active:
        return RenamePlan(
            source_text_new=source_text,
            renamed={},
            warnings=warnings,
            files_modified=[],
        )

    source_text_new = _render_renamed(source_text, active)
    caller_texts, caller_rewrites = _rewrite_callers(root, source_path, active)

    files_modified = [str(source_path), *(str(p) for p in caller_texts)]
    plan = RenamePlan(
        source_text_new=source_text_new,
        renamed=active,
        callers_updated=caller_rewrites,
        warnings=warnings,
        files_modified=files_modified,
    )
    if dry_run:
        return plan

    _write_rename(root, source_path, source_text, source_text_new, caller_texts)
    return plan


def _write_rename(
    root: Path,
    source_path: Path,
    source_text: str,
    source_text_new: str,
    caller_texts: dict[Path, tuple[str, str]],
) -> None:
    """Atomically rewrite the defining module and every caller via batch_edit.

    Unlike a move, a rename touches each file exactly once, so a single
    ``replace`` op per distinct file (defining module + callers) is emitted.
    """
    edits: dict[Path, tuple[str, str]] = {source_path: (source_text, source_text_new)}
    edits.update(caller_texts)
    operations: list[dict[str, object]] = []
    for file_path, (old_text, new_text) in edits.items():
        try:
            rel = file_path.resolve().relative_to(root.resolve())
        except ValueError:
            rel = file_path
        operations.append(
            {
                "op": "replace",
                "file": str(rel),
                "edits": [{"old": old_text, "new": new_text}],
            }
        )
    batch_edit(str(root), operations)
