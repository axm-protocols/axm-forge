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
- :func:`render_result` — a full compact, lossless ``text`` walker over an
  arbitrary ``data`` payload (never raises).
- :func:`record_table` — the lossless homogeneous-record ``key | key`` table.

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
    "record_table",
    "render_result",
    "truncate",
]

_ELLIPSIS = "…"
_INDENT = "  "
_COL_SEP = "  "
_COUNT_STEP = 1000
_SIZE_STEP = 1024
_MAX_INLINE_LIST = 8
_MIN_TABLE_ROWS = 2


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


def _is_scalar(value: object) -> bool:
    """True when *value* renders on a single inline token (not dict/list)."""
    return not isinstance(value, (dict, list, tuple))


def _is_short_scalar_list(value: object) -> bool:
    """True for a short list/tuple of scalars (inline comma-join candidate)."""
    return (
        isinstance(value, (list, tuple))
        and 0 < len(value) <= _MAX_INLINE_LIST
        and all(_is_scalar(v) for v in value)
    )


def _is_flat_dict(value: object) -> bool:
    """True for a non-empty dict whose values are all inline-able."""
    return (
        isinstance(value, dict)
        and bool(value)
        and all(_is_scalar(v) or _is_short_scalar_list(v) for v in value.values())
    )


def _scalar(value: object) -> str:
    """Render a leaf value (None as '—', bool as yes/no)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _inline_list(value: object) -> str:
    """Comma-join a short scalar list/tuple (callers pass a sequence)."""
    if not isinstance(value, (list, tuple)):
        return _scalar(value)
    return ", ".join(_scalar(v) for v in value)


def _inline_field(value: object) -> str:
    """Render a scalar or short scalar-list field for an inline ``k=v``."""
    return _inline_list(value) if isinstance(value, (list, tuple)) else _scalar(value)


def _flat_dict_inline(value: object) -> str:
    """Render a flat dict as ``k=v · k=v`` on one line (callers pass a dict)."""
    if not isinstance(value, dict):
        return _scalar(value)
    return " · ".join(f"{k}={_inline_field(v)}" for k, v in value.items())


def _table_keys(seq: Sequence[object]) -> list[str] | None:
    """Shared scalar-only key order if *seq* is a homogeneous dict list, else None.

    Homogeneous = ≥2 dicts, identical key sets, all values scalar. Order is
    taken from the first record so the table reads in declaration order.
    """
    rows = [r for r in seq if isinstance(r, dict)]
    if len(rows) < _MIN_TABLE_ROWS or len(rows) != len(seq):
        return None
    keys = list(rows[0].keys())
    key_set = set(keys)
    for rec in rows:
        if set(rec.keys()) != key_set:
            return None
        if not all(_is_scalar(v) for v in rec.values()):
            return None
    return keys


def record_table(
    rows: Sequence[object],
    keys: Sequence[str],
    *,
    indent: int = 0,
) -> list[str]:
    """Render a homogeneous dict list as ``key | key`` header + value rows.

    Lossless: emits the shared *keys* once as a header line then one value row
    per record. ``None`` cells render as an em-dash, bools as yes/no. *indent*
    offsets every line by two spaces per level.
    """
    pad = _INDENT * indent
    lines = [f"{pad}{' | '.join(keys)}"]
    for rec in rows:
        row = rec if isinstance(rec, dict) else {}
        lines.append(f"{pad}{' | '.join(_scalar(row.get(k)) for k in keys)}")
    return lines


def _fmt_field(key: object, val: object, *, indent: int) -> list[str]:
    """Render one ``key: …`` entry of a (non-flat) dict."""
    pad = _INDENT * indent
    if _is_scalar(val):
        return [f"{pad}{key}: {_scalar(val)}"]
    if _is_short_scalar_list(val):
        return [f"{pad}{key}: {_inline_list(val)}"]
    if _is_flat_dict(val):
        return [f"{pad}{key}: {_flat_dict_inline(val)}"]
    return [f"{pad}{key}:", *_fmt_value(val, indent=indent + 1)]


def _fmt_item(item: object, *, indent: int) -> list[str]:
    """Render one ``- …`` entry of a (heterogeneous) list."""
    pad = _INDENT * indent
    if _is_scalar(item):
        return [f"{pad}- {_scalar(item)}"]
    if _is_flat_dict(item):
        return [f"{pad}- {_flat_dict_inline(item)}"]
    child = _fmt_value(item, indent=indent + 1)
    return [f"{pad}- {child[0].strip()}", *child[1:]]


def _fmt_dict(value: dict[object, object], *, indent: int) -> list[str]:
    """Render a (non-flat) dict: one ``key: …`` block per entry."""
    pad = _INDENT * indent
    if _is_flat_dict(value):
        return [f"{pad}{_flat_dict_inline(value)}"]
    lines: list[str] = []
    for key, val in value.items():
        lines.extend(_fmt_field(key, val, indent=indent))
    return lines or [f"{pad}(empty)"]


def _fmt_list(seq: list[object], *, indent: int) -> list[str]:
    """Render a list: inline / table (homogeneous) / bullet lines."""
    pad = _INDENT * indent
    if not seq:
        return [f"{pad}(none)"]
    if _is_short_scalar_list(seq):
        return [f"{pad}{_inline_list(seq)}"]
    keys = _table_keys(seq)
    if keys is not None:
        return record_table(seq, keys, indent=indent)
    lines: list[str] = []
    for item in seq:
        lines.extend(_fmt_item(item, indent=indent))
    return lines


def _fmt_value(value: object, *, indent: int) -> list[str]:
    """Render *value* as one or more lines, recursing into dicts/lists."""
    if isinstance(value, dict):
        return _fmt_dict(value, indent=indent)
    if isinstance(value, (list, tuple)):
        return _fmt_list(list(value), indent=indent)
    return [f"{_INDENT * indent}{_scalar(value)}"]


def render_result(tool: str, data: object, *, label: str = "") -> str:
    """Render an arbitrary tool result as compact, lossless ``text``.

    Header is ``{tool}`` (plus ``| {label}`` when *label* is given); the body
    preserves every field of *data*. A scalar-only payload collapses to the
    arrow form ``{header} → {value}``.

    Never raises: any object — including an unrenderable or self-referential
    one — yields a ``str`` (falling back to the header line on failure).
    """
    head = header(tool, label) if label else tool
    try:
        body = _fmt_value(data, indent=0)
        if len(body) == 1 and not isinstance(data, (dict, list, tuple)):
            return f"{head} → {body[0].strip()}"
        return "\n".join([head, *body])
    except Exception:  # noqa: BLE001 — never-raises contract: any object yields a str
        return head
