"""Text renderers for SearchTool dual-format ToolResult."""

from __future__ import annotations

from typing import Any

__all__ = [
    "format_func_line",
    "format_symbol_line",
    "format_text_header",
    "format_variable_line",
    "render_suggestion_line",
    "render_text",
]


_FUNC_KINDS: frozenset[str] = frozenset(
    {"function", "method", "property", "classmethod", "staticmethod", "abstract"}
)

_KIND_ABBREV_LEN = 4


def format_text_header(
    *,
    search_filters: dict[str, Any],
    count: int,
    suggestion_count: int = 0,
) -> str:
    """Build the header line for text rendering."""
    name = search_filters.get("name")
    returns = search_filters.get("returns")
    kind = search_filters.get("kind")
    inherits = search_filters.get("inherits")
    parts: list[str] = []
    if name is not None:
        parts.append(f'name~"{name}"')
    if returns is not None:
        parts.append(f"returns={returns}")
    kind_str = (
        kind if isinstance(kind, str) else (kind.value if kind is not None else None)
    )
    if kind_str is not None:
        parts.append(f"kind={kind_str}")
    if inherits is not None:
        parts.append(f"inherits={inherits}")
    sections = ["ast_search"]
    if parts:
        sections.append(" · ".join(parts))
    hits_part = f"{count} hits"
    if suggestion_count > 0:
        hits_part += f" · {suggestion_count} suggestions"
    sections.append(hits_part)
    return " | ".join(sections)


def _extract_params_block(sig: str) -> str:
    """Extract the parenthesised params block from a signature string."""
    paren_start = sig.find("(")
    if paren_start == -1:
        return "()"
    rest = sig[paren_start:]
    depth = 0
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return rest[: i + 1]
    return rest


def format_func_line(sym: dict[str, Any]) -> str:
    """Format a function-like symbol as a compact text line."""
    params = _extract_params_block(sym.get("signature", ""))
    line = f"{sym['name']}{params}"
    ret = sym.get("return_type")
    if ret is not None:
        line += f" -> {ret}"
    return line


def format_variable_line(sym: dict[str, Any]) -> str:
    """Format a variable symbol as a compact text line."""
    name = sym["name"]
    ann = sym.get("annotation")
    val = sym.get("value_repr")
    if ann and val:
        return f"{name}: {ann} = {val}"
    if ann:
        return f"{name}: {ann}"
    if val:
        return f"{name} = {val}"
    return str(name)


def format_symbol_line(sym: dict[str, Any]) -> str:
    """Render one symbol dict as a compact text line."""
    kind = sym.get("kind", "")
    if kind in _FUNC_KINDS:
        return format_func_line(sym)
    if kind == "class":
        return str(sym["name"])
    return format_variable_line(sym)


def render_suggestion_line(suggestion: dict[str, Any]) -> str:
    """Render one suggestion as a compact ``?``-prefixed text line."""
    name = suggestion["name"]
    score = (
        f".{int(suggestion['score'] * 100):02d}" if suggestion["score"] < 1 else "1.0"
    )
    kind = (
        suggestion["kind"][:_KIND_ABBREV_LEN]
        if len(suggestion["kind"]) > _KIND_ABBREV_LEN
        else suggestion["kind"]
    )
    module = suggestion["module"]
    line = f"? {name} {score} {kind}"
    if module is not None:
        line += f" {module}"
    return line


def _group_symbols(
    symbols: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition symbols into (funcs, classes, variables)."""
    funcs: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    for s in symbols:
        k = s.get("kind", "")
        if k in _FUNC_KINDS:
            funcs.append(s)
        elif k == "class":
            classes.append(s)
        else:
            variables.append(s)
    return funcs, classes, variables


def render_text(
    symbols: list[dict[str, Any]],
    *,
    search_filters: dict[str, Any],
    suggestions: list[dict[str, Any]] | None = None,
) -> str:
    """Group symbols by kind and render as compact text."""
    suggestions = suggestions or []
    header = format_text_header(
        search_filters=search_filters,
        count=len(symbols),
        suggestion_count=len(suggestions),
    )
    if not symbols and not suggestions:
        return header

    if not symbols and suggestions:
        lines = [header]
        lines.extend(render_suggestion_line(s) for s in suggestions)
        return "\n".join(lines)

    funcs, classes, variables = _group_symbols(symbols)
    lines = [header]
    lines.extend(format_symbol_line(s) for s in funcs)
    if classes:
        lines.append(", ".join(format_symbol_line(s) for s in classes))
    lines.extend(format_symbol_line(s) for s in variables)
    return "\n".join(lines)
