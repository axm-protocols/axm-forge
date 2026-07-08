"""Extract pipeline: relocate symbols into a brand-new module.

``extract_symbols`` is a thin adapter over :func:`move_symbols`. The only
semantic difference between *extract* and *move* is that the target module
is **created** (it does not yet exist). All dependency resolution, caller
rewriting and atomic writing are delegated to the move pipeline — this
module never duplicates that logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import libcst as cst

from axm_anvil.core.deps import gather_source_constants, gather_source_helpers
from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import MovePlan, SymbolAlreadyExistsError

__all__ = ["extract_symbols"]


def _existing_target_symbols(target_path: Path) -> set[str]:
    """Return the top-level symbol names already defined in ``target_path``.

    An absent target contributes no names (the nominal extract case).
    """
    if not target_path.exists():
        return set()
    tree = cst.parse_module(target_path.read_text())
    names = set(gather_source_helpers(tree))
    names |= set(gather_source_constants(tree))
    return names


def _check_collision(target_path: Path, symbol_names: Sequence[str]) -> None:
    """Raise :class:`SymbolAlreadyExistsError` on a homonymous collision.

    Extracting into a *pre-existing* module that already defines one of the
    requested symbols would silently overwrite it; guard against that before
    any filesystem mutation.
    """
    existing = _existing_target_symbols(target_path)
    clashes = [name for name in symbol_names if name in existing]
    if clashes:
        raise SymbolAlreadyExistsError(", ".join(clashes))


def extract_symbols(  # noqa: PLR0913
    source_path: str | Path,
    target_path: str | Path,
    symbol_names: Sequence[str],
    dry_run: bool = False,
    workspace_root: Path | None = None,
    shared_helpers: str = "duplicate",
    shared_helpers_module: str | None = None,
    rename: dict[str, str] | None = None,
    strict: bool = False,
    insert_after: str | None = None,
    include_helpers: bool = True,
    side_effect_decorators: frozenset[str] | None = None,
) -> MovePlan:
    """Extract ``symbol_names`` from ``source_path`` into a *new* module.

    ``extract`` is the specialisation of :func:`move_symbols` where
    ``target_path`` is created rather than amended. The moved blocks and
    their transitive dependencies (imports, local helpers, constants) are
    copied into the new module, and cross-file callers are rewritten to
    import from it — all via the move pipeline.

    When ``target_path`` does not exist it is scaffolded as an empty module
    so the move pipeline can fill it. A pre-existing target that already
    defines a requested symbol raises :class:`SymbolAlreadyExistsError`
    (no silent overwrite).

    With ``dry_run=True`` the :class:`MovePlan` is computed without leaving
    any file on disk: a target scaffolded for the dry run is removed before
    returning, so the source layout is byte-identical to before the call.

    All other parameters mirror :func:`move_symbols` and are forwarded
    verbatim. ``reexport`` and ``check`` are intentionally not exposed:
    re-exporting from / cycle-checking against a freshly created module is
    meaningless for an extract.
    """
    source_path = Path(source_path)
    target_path = Path(target_path)

    _check_collision(target_path, symbol_names)

    created_scaffold = False
    created_dirs: list[Path] = []
    if not target_path.exists():
        created_dirs = _mkdir_tracking(target_path.parent)
        target_path.write_text("")
        created_scaffold = True

    try:
        plan = move_symbols(
            source_path,
            target_path,
            symbol_names,
            dry_run=dry_run,
            workspace_root=workspace_root,
            shared_helpers=shared_helpers,
            shared_helpers_module=shared_helpers_module,
            rename=rename,
            strict=strict,
            insert_after=insert_after,
            include_helpers=include_helpers,
            side_effect_decorators=side_effect_decorators,
        )
    finally:
        # A dry run must leave disk state byte-identical: drop the empty
        # scaffold file *and* any parent directories we created for it.
        if dry_run and created_scaffold:
            _cleanup_scaffold(target_path, created_dirs)

    return plan


def _mkdir_tracking(directory: Path) -> list[Path]:
    """Create ``directory`` (and parents), returning the dirs we actually made.

    The returned list is ordered leaf-last (deepest first) so a caller can
    remove them in order without hitting a non-empty parent.
    """
    created: list[Path] = []
    current = directory
    to_create: list[Path] = []
    while not current.exists():
        to_create.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    directory.mkdir(parents=True, exist_ok=True)
    created.extend(to_create)
    return created


def _cleanup_scaffold(target_path: Path, created_dirs: list[Path]) -> None:
    """Remove the dry-run scaffold file and any directories we created for it."""
    if target_path.exists():
        target_path.unlink()
    for directory in created_dirs:
        try:
            directory.rmdir()
        except OSError:
            # Not empty (something else landed here): leave it in place.
            break
