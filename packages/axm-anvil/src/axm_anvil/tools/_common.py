"""Shared plumbing for the anvil MCP tools (arg normalization, errors).

These helpers are duplicated-no-more across :mod:`axm_anvil.tools.move` and
:mod:`axm_anvil.tools.extract`, which expose the same CSV-symbol /
source-target signature and map the same move-pipeline exceptions to
``ToolResult(success=False)``. :mod:`axm_anvil.tools.rename` keeps its own
exception mapping (it raises a different, smaller set with distinct messages).
"""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

from axm_anvil.core.plan import (
    ImportCycleError,
    SharedHelpersError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)

__all__ = ["exception_to_result", "normalize_execute_args"]


def normalize_execute_args(
    path: str,
    symbols: str,
    from_file: str,
    to_file: str,
) -> tuple[Path, Path, Path, list[str]]:
    """Parse CSV ``symbols`` and resolve ``from_file`` / ``to_file`` vs ``path``.

    Relative source/target paths are resolved against the workspace ``root``
    (``Path(path).resolve()``); absolute paths are kept as-is. Empty symbol
    entries are dropped.
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    root = Path(path).resolve()
    src_path = Path(from_file)
    tgt_path = Path(to_file)
    if not src_path.is_absolute():
        src_path = root / src_path
    if not tgt_path.is_absolute():
        tgt_path = root / tgt_path
    return root, src_path, tgt_path, symbol_list


def exception_to_result(exc: Exception) -> ToolResult:
    """Map a move-pipeline exception to a ``ToolResult(success=False)``.

    Shared by ``anvil_move`` and ``anvil_extract``; both surface the same
    failure modes (missing symbol, collision, shared helpers, import cycle,
    unimplemented extract policy). Unknown exceptions fall through to their
    string form.
    """
    match exc:
        case SymbolNotFoundError():
            return ToolResult(
                success=False,
                error=f"Symbol {exc!s} not found in source module",
            )
        case SymbolAlreadyExistsError():
            return ToolResult(
                success=False,
                error=f"Symbol {exc!s} already exists in target module",
            )
        case SharedHelpersError():
            joined = ", ".join(exc.shared_helpers)
            return ToolResult(
                success=False,
                error=f"Shared helpers detected: {joined}",
            )
        case ImportCycleError():
            return ToolResult(success=False, error=str(exc))
        case NotImplementedError():
            return ToolResult(
                success=False,
                error=("shared_helpers='extract' is not yet implemented (Phase 3)"),
            )
        case _:
            return ToolResult(success=False, error=str(exc))
