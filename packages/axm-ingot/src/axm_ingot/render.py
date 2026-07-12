"""Compact ``ToolResult`` text primitives (stdlib-strict).

Factored out of the duplicated ``_render.py`` copies that lived in
``axm-backtest``, ``axm-route`` and friends. Each AXM tool fills ``data`` (a
Pydantic ``model_dump``) but often leaves ``text=None``, so the MCP server falls
back to a verbose JSON dump. These primitives compose into a few-line métier
renderer that emits a compact, token-cheap ``text``:

- :func:`header` — the ``{tool} | {summary}`` first line.
- :func:`labeled_block` — a label followed by indented lines.
- :func:`compact_table` — an aligned columns table for homogeneous rows.
- :func:`truncate` — bounded text with a trailing ellipsis.
- :func:`format_count` / :func:`format_size` — human-readable numbers.

Strictly stdlib — no runtime dependency is added by importing this module.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "compact_table",
    "format_count",
    "format_size",
    "header",
    "labeled_block",
    "truncate",
]

_ELLIPSIS = "…"
_INDENT = "  "
_COL_SEP = "  "
_COUNT_STEP = 1000
_SIZE_STEP = 1024


def _cell(value: object) -> str:
    """Render one value as a string, mapping ``None`` to the empty string."""
    return "" if value is None else str(value)


def header(tool: str, summary: str) -> str:
    """Render the compact header line ``{tool} | {summary}``.

    >>> header("audit", "3 findings")
    'audit | 3 findings'
    """
    return f"{tool} | {summary}"


def labeled_block(label: str, lines: Sequence[str | None]) -> str:
    """Render *label* followed by *lines*, each indented two spaces.

    An empty *lines* yields an empty string so no dangling label is emitted.
    ``None`` entries render as blank lines rather than the literal ``"None"``.
    """
    if not lines:
        return ""
    body = [f"{_INDENT}{_cell(line)}" for line in lines]
    return "\n".join([label, *body])


def compact_table(
    rows: Sequence[Sequence[object]],
    headers: Sequence[object] | None = None,
) -> str:
    """Render *rows* as a column-aligned table, optionally with a *headers* row.

    Tolerates ragged rows (short rows are padded) and arbitrarily wide cells.
    ``None`` cells render as empty, never as the literal ``"None"``.
    """
    matrix: list[list[str]] = []
    if headers is not None:
        matrix.append([_cell(h) for h in headers])
    matrix.extend([_cell(c) for c in row] for row in rows)
    if not matrix:
        return ""
    ncols = max(len(row) for row in matrix)
    for row in matrix:
        row.extend([""] * (ncols - len(row)))
    widths = [max(len(row[col]) for row in matrix) for col in range(ncols)]
    out = []
    for row in matrix:
        line = _COL_SEP.join(row[col].ljust(widths[col]) for col in range(ncols))
        out.append(line.rstrip())
    return "\n".join(out)


def truncate(text: str, limit: int) -> str:
    """Bound *text* to *limit* chars, appending an ellipsis when it overflows.

    Text at or under *limit* is returned unchanged. The overflow result has at
    most ``limit + 1`` characters and ends with the ellipsis marker.
    """
    bound = max(limit, 0)
    if len(text) <= bound:
        return text
    return text[:bound] + _ELLIPSIS


def format_count(n: int) -> str:
    """Render an item count, abbreviating thousands (``1500`` → ``'1.5K'``)."""
    magnitude = abs(n)
    if magnitude < _COUNT_STEP:
        return str(n)
    for unit, divisor in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if magnitude >= divisor:
            return f"{n / divisor:.1f}{unit}"
    return str(n)


def format_size(num_bytes: int) -> str:
    """Render a byte count in human units (``2048`` → ``'2.0 KB'``)."""
    size = float(num_bytes)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if abs(size) < _SIZE_STEP or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= _SIZE_STEP
    return f"{num_bytes} B"
