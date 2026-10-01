"""Map changed line intervals to qualified symbols, including function bodies."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from axm_ast.core.cache import get_package
from axm_ast.models.nodes import ModuleInfo

__all__ = ["symbols_for_lines"]


def _overlaps(start: int, end: int, intervals: Sequence[tuple[int, int]]) -> bool:
    return any(
        count > 0 and line <= end and line + count - 1 >= start
        for line, count in intervals
    )


def _symbols(module: ModuleInfo) -> list[tuple[str, int, int]]:
    rows = [(fn.name, fn.line_start, fn.line_end) for fn in module.functions]
    for cls in module.classes:
        rows.append((cls.name, cls.line_start, cls.line_end))
        rows.extend(
            (cls.name + "." + fn.name, fn.line_start, fn.line_end) for fn in cls.methods
        )
    rows.extend((v.name, v.line, v.line) for v in module.variables)
    return rows


def symbols_for_lines(
    package: Path,
    file: Path,
    intervals: Sequence[tuple[int, int]],
) -> tuple[str, ...]:
    """Return stable module-qualified seeds for changed lines in an AST snapshot.

    Class containers remain seeds beside changed methods. Module-level changes
    (imports, declarations outside a symbol) conservatively seed every symbol
    of the module. Call this on both base and head to cover deleted symbols.
    """
    pkg = get_package(package)
    module = next((m for m in pkg.modules if m.path.resolve() == file.resolve()), None)
    if module is None:
        return ()
    relative = module.path.relative_to(pkg.root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    prefix = ".".join([pkg.name, *parts])
    rows = _symbols(module)
    selected = [name for name, start, end in rows if _overlaps(start, end, intervals)]
    outside = any(
        count > 0 and not any(start <= line <= end for _, start, end in rows)
        for line, count in intervals
    )
    if outside:
        selected = [name for name, _, _ in rows]
    return tuple(sorted({prefix + "." + name for name in selected}))
