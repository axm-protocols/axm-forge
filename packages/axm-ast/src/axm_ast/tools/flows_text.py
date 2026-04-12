"""Text renderers for FlowsTool dual-format ToolResult."""

from __future__ import annotations

from typing import Any

__all__ = [
    "render_compact_text",
    "render_entry_points_text",
    "render_source_text",
    "render_trace_text",
]


# ─── Helpers ───────────────────────────────────────────────────────────────────────


def _header(mode: str, params: str, count: int, unit: str) -> str:
    """Build consistent header: ast_flows | {mode} | {params} | {count} {unit}."""
    return f"ast_flows | {mode} | {params} | {count} {unit}"


def _trace_params(
    entry: str,
    depth: int,
    cross_module: bool,
    truncated: bool,
) -> str:
    """Build the params segment for trace/compact/source headers."""
    parts = [f"entry={entry}", f"depth={depth}"]
    if cross_module:
        parts.append("cross_module")
    if truncated:
        parts.append("truncated")
    return " ".join(parts)


def _format_step_line(step: dict[str, Any], *, show_resolved: bool = True) -> str:
    """Format a single trace step as an indented line."""
    indent = "  " * step["depth"]
    loc = f"{step['module']}:{step['line']}"
    suffix = ""
    if show_resolved and step.get("resolved_module"):
        suffix = f" \u2192 {step['resolved_module']}"
    return f"{indent}{step['name']}  {loc}{suffix}"


def _format_entry(e: dict[str, Any]) -> str:
    """Format a single entry point inline."""
    name = e["name"]
    line = e["line"]
    kind = e["kind"]
    framework = e["framework"]

    if kind == "export" and line == 1 and framework == "all":
        label = name
    elif line != 1:
        label = f"{name}:{line}"
    else:
        label = name

    match kind:
        case "decorator":
            return f"@{framework} {label}"
        case "main_guard":
            return f"\u25b6{label}"
        case _:
            return str(label)


# ─── Public renderers ───────────────────────────────────────────────────────────────


def render_entry_points_text(entries: list[dict[str, Any]], count: int) -> str:
    """Render entry points grouped by module with default elision."""
    hdr = _header("entry_points", "", count, "entries").replace(" |  | ", " | ")

    if not entries:
        return hdr

    by_module: dict[str, list[str]] = {}
    for e in entries:
        by_module.setdefault(e["module"], []).append(_format_entry(e))

    lines = [hdr, ""]
    for module, names in sorted(by_module.items()):
        lines.append(f"{module}: {' '.join(names)}")

    lines.append("")
    lines.append(
        "Legend: name (export, line=1) | name:LINE (export)"
        " | @FW name:LINE (decorator) | \u25b6name:LINE (main_guard)"
    )
    return "\n".join(lines)


def render_trace_text(  # noqa: PLR0913
    entry: str,
    steps: list[dict[str, Any]],
    depth: int,
    cross_module: bool,
    count: int,
    truncated: bool,
) -> str:
    """Render trace steps as indented tree text."""
    params = _trace_params(entry, depth, cross_module, truncated)
    hdr = _header("trace_flow", params, count, "steps")

    lines = [hdr, ""]
    for step in steps:
        lines.append(_format_step_line(step))

    return "\n".join(lines)


def render_compact_text(  # noqa: PLR0913
    entry: str,
    compact: str,
    depth: int,
    cross_module: bool,
    count: int,
    truncated: bool,
) -> str:
    """Render compact text: header + raw format_flow_compact output."""
    params = _trace_params(entry, depth, cross_module, truncated)
    hdr = _header("compact", params, count, "steps")

    return f"{hdr}\n\n{compact}"


def render_source_text(  # noqa: PLR0913
    entry: str,
    steps: list[dict[str, Any]],
    depth: int,
    cross_module: bool,
    count: int,
    truncated: bool,
) -> str:
    """Render trace tree with inline source blocks."""
    params = _trace_params(entry, depth, cross_module, truncated)
    hdr = _header("source", params, count, "steps")

    lines = [hdr, ""]
    for step in steps:
        lines.append(_format_step_line(step))
        source = step.get("source")
        if source:
            indent = "  " * (step["depth"] + 1)
            for src_line in source.splitlines():
                lines.append(f"{indent}{src_line}")

    return "\n".join(lines)
