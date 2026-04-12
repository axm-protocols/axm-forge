from __future__ import annotations

from typing import Any

__all__ = [
    "render_batch_text",
    "render_class_text",
    "render_function_text",
    "render_module_text",
    "render_symbol_text",
    "render_variable_text",
]

_MAX_DOC_LEN = 200


def _truncate_docstring(doc: str) -> str:
    """Return first paragraph, truncated to ~200 chars."""
    first_para = doc.split("\n\n")[0].strip()
    if len(first_para) <= _MAX_DOC_LEN:
        return first_para
    return first_para[:_MAX_DOC_LEN] + "..."


def _header(name: str, file: str, start: int, end: int, suffix: str = "") -> str:
    """Build consistent header: {name}  {file}:{start}-{end}{suffix}."""
    loc = f"{file}:{start}-{end}" if start != end else f"{file}:{start}"
    parts = [name, f"  {loc}"]
    if suffix:
        parts.append(f"  {suffix}")
    return "".join(parts)


def _append_source(lines: list[str], detail: dict[str, Any]) -> None:
    """Append fenced python source block if present."""
    source = detail.get("source")
    if source:
        lines.append(f"```python\n{source}\n```")


def render_function_text(detail: dict[str, Any]) -> str:
    """Render a function detail dict as compact text."""
    name = detail["name"]
    file = detail["file"]
    start = detail.get("start_line", 0)
    end = detail.get("end_line", start)

    lines = [_header(name, file, start, end)]

    sig = detail.get("signature")
    if sig:
        lines.append(sig)

    doc = detail.get("docstring")
    if doc:
        lines.append(_truncate_docstring(doc))

    params = detail.get("parameters")
    if params:
        parts = []
        for p in params:
            s = p["name"]
            ann = p.get("annotation")
            if ann:
                s += f": {ann}"
            default = p.get("default")
            if default is not None:
                s += f" ={default}"
            parts.append(s)
        lines.append(f"Params: {', '.join(parts)}")

    ret = detail.get("return_type")
    if ret:
        lines.append(f"Returns: {ret}")

    _append_source(lines, detail)
    return "\n".join(lines)


def render_class_text(detail: dict[str, Any]) -> str:
    """Render a class detail dict as compact text."""
    name = detail["name"]
    file = detail["file"]
    start = detail.get("start_line", 0)
    end = detail.get("end_line", start)
    bases = detail.get("bases", [])

    suffix = f"({', '.join(bases)})" if bases else ""
    lines = [_header(name, file, start, end, suffix)]

    doc = detail.get("docstring")
    if doc:
        lines.append(_truncate_docstring(doc))

    methods = detail.get("methods", [])
    if methods:
        lines.append(f"Methods: {', '.join(methods)}")

    _append_source(lines, detail)
    return "\n".join(lines)


def render_variable_text(detail: dict[str, Any]) -> str:
    """Render a variable detail dict as compact text."""
    name = detail["name"]
    file = detail["file"]
    start = detail.get("start_line", 0)
    end = detail.get("end_line", start)

    lines = [_header(name, file, start, end, "variable")]

    ann = detail.get("annotation")
    if ann:
        lines.append(f": {ann}")

    val = detail.get("value_repr")
    if val:
        lines.append(f"= {val}")

    return "\n".join(lines)


def render_module_text(detail: dict[str, Any]) -> str:
    """Render a module detail dict as compact text."""
    name = detail["name"]
    file = detail.get("file", "")
    count = detail.get("symbol_count", 0)

    lines = [f"{name}  {file}  module \u00b7 {count} symbols"]

    doc = detail.get("docstring")
    if doc:
        lines.append(_truncate_docstring(doc))

    funcs = detail.get("functions", [])
    if funcs:
        lines.append(f"Functions: {', '.join(funcs)}")

    classes = detail.get("classes", [])
    if classes:
        lines.append(f"Classes: {', '.join(classes)}")

    return "\n".join(lines)


def render_symbol_text(detail: dict[str, Any]) -> str:
    """Dispatch to the correct renderer based on detail kind."""
    kind = detail.get("kind", "")
    match kind:
        case "function" | "method":
            return render_function_text(detail)
        case "class":
            return render_class_text(detail)
        case "variable":
            return render_variable_text(detail)
        case "module":
            return render_module_text(detail)
        case _:
            return render_function_text(detail)


def render_batch_text(symbols: list[dict[str, Any]]) -> str:
    """Join individual renders with blank-line separator, handle errors."""
    if not symbols:
        return ""

    parts: list[str] = []
    for entry in symbols:
        if "error" in entry:
            parts.append(f"{entry.get('name', '?')}  \u26a0 {entry['error']}")
        else:
            parts.append(render_symbol_text(entry))

    return "\n\n".join(parts)
