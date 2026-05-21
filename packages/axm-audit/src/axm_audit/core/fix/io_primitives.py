"""Low-level I/O: libcst load/save + git mv with safety guard.

The proto reads with ast (fast, sufficient for analysis) but writes with
libcst (preserves quote style, indentation, comments, trailing whitespace
— everything ast.unparse silently loses). Migrating mutating helpers to
libcst is what gives us back the triple-quoted strings, comments, and
blank-line spacing that ast.unparse erases. axm-anvil itself works the
same way under the hood.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import libcst as cst

__all__ = [
    "_cst_load",
    "_cst_save",
    "_cst_top_level",
    "_cst_unwrap",
    "_git_mv",
]


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


def _cst_unwrap(
    stmt: cst.BaseStatement,
) -> cst.BaseSmallStatement | cst.BaseCompoundStatement:
    """Unwrap a SimpleStatementLine to its first small statement, if any.

    libcst wraps top-level small statements (imports, assigns) inside
    ``SimpleStatementLine``. For comparisons / extraction we usually want
    the inner statement (Import, ImportFrom, Assign, …).
    """
    if isinstance(stmt, cst.SimpleStatementLine) and stmt.body:
        return stmt.body[0]
    return stmt  # type: ignore[return-value]


def _git_mv(src: Path, dst: Path) -> None:
    """Move *src* to *dst* via ``git mv``, with a non-destructive fallback.

    If *dst* already exists, the fallback ``shutil.move`` used to silently
    overwrite it — losing 25+ moved tests when RENAME / RELOCATE landed
    on a file the SPLIT/MERGE stages had just populated. Refuse to
    overwrite: raise ``FileExistsError`` so the caller (e.g.
    ``_execute_rename``) can re-route through ``_safe_move_units``.

    Note: ``shutil.move`` raises its own ``shutil.Error`` when its target
    happens to exist — translate to ``FileExistsError`` so callers only
    have one exception class to catch.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise FileExistsError(
            f"refusing to overwrite existing path {dst} with {src} via git_mv"
        )
    rc = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        try:
            shutil.move(str(src), str(dst))
        except shutil.Error as exc:
            raise FileExistsError(str(exc)) from exc
