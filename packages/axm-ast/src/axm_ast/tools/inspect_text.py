from __future__ import annotations

from collections.abc import Mapping, Sequence

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


def _as_str(value: object, default: str = "") -> str:
    """Narrow ``object`` to ``str`` (returning ``default`` otherwise)."""
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    """Narrow ``object`` to ``int`` (returning ``default`` otherwise)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow ``object`` to ``list[str]`` (returning ``[]`` otherwise)."""
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [item for item in value if isinstance(item, str)]
    return []


def _append_source(lines: list[str], detail: Mapping[str, object]) -> None:
    """Append fenced python source block if present."""
    source = detail.get("source")
    if isinstance(source, str) and source:
        lines.append(f"```python\n{source}\n```")


def _format_param(param: Mapping[str, object]) -> str:
    """Render one parameter entry as ``name[: ann][ =default]``."""
    name = _as_str(param.get("name"))
    s = name
    ann = param.get("annotation")
    if isinstance(ann, str) and ann:
        s += f": {ann}"
    default = param.get("default")
    if default is not None:
        s += f" ={default}"
    return s


def render_function_text(detail: Mapping[str, object]) -> str:
    """Render a function detail dict as compact text."""
    name = _as_str(detail["name"])
    file = _as_str(detail["file"])
    start = _as_int(detail.get("start_line"))
    end = _as_int(detail.get("end_line"), start)

    lines = [_header(name, file, start, end)]

    sig = detail.get("signature")
    if isinstance(sig, str) and sig:
        lines.append(sig)

    doc = detail.get("docstring")
    if isinstance(doc, str) and doc:
        lines.append(_truncate_docstring(doc))

    params = detail.get("parameters")
    if isinstance(params, Sequence) and not isinstance(params, str | bytes):
        parts = [_format_param(p) for p in params if isinstance(p, Mapping)]
        if parts:
            lines.append(f"Params: {', '.join(parts)}")

    ret = detail.get("return_type")
    if isinstance(ret, str) and ret:
        lines.append(f"Returns: {ret}")

    _append_source(lines, detail)
    return "\n".join(lines)


def render_class_text(detail: Mapping[str, object]) -> str:
    """Render a class detail dict as compact text."""
    name = _as_str(detail["name"])
    file = _as_str(detail["file"])
    start = _as_int(detail.get("start_line"))
    end = _as_int(detail.get("end_line"), start)
    bases = _as_str_list(detail.get("bases"))

    suffix = f"({', '.join(bases)})" if bases else ""
    lines = [_header(name, file, start, end, suffix)]

    doc = detail.get("docstring")
    if isinstance(doc, str) and doc:
        lines.append(_truncate_docstring(doc))

    methods = _as_str_list(detail.get("methods"))
    if methods:
        lines.append(f"Methods: {', '.join(methods)}")

    _append_source(lines, detail)
    return "\n".join(lines)


def render_variable_text(detail: Mapping[str, object]) -> str:
    """Render a variable detail dict as compact text."""
    name = _as_str(detail["name"])
    file = _as_str(detail["file"])
    start = _as_int(detail.get("start_line"))
    end = _as_int(detail.get("end_line"), start)

    lines = [_header(name, file, start, end, "variable")]

    ann = detail.get("annotation")
    if isinstance(ann, str) and ann:
        lines.append(f": {ann}")

    val = detail.get("value_repr")
    if isinstance(val, str) and val:
        lines.append(f"= {val}")

    return "\n".join(lines)


def render_module_text(detail: Mapping[str, object]) -> str:
    """Render a module detail dict as compact text."""
    name = _as_str(detail["name"])
    file = _as_str(detail.get("file"))
    count = _as_int(detail.get("symbol_count"))

    lines = [f"{name}  {file}  module · {count} symbols"]

    doc = detail.get("docstring")
    if isinstance(doc, str) and doc:
        lines.append(_truncate_docstring(doc))

    funcs = _as_str_list(detail.get("functions"))
    if funcs:
        lines.append(f"Functions: {', '.join(funcs)}")

    classes = _as_str_list(detail.get("classes"))
    if classes:
        lines.append(f"Classes: {', '.join(classes)}")

    return "\n".join(lines)


def render_symbol_text(detail: Mapping[str, object]) -> str:
    """Dispatch to the correct renderer based on detail kind."""
    kind = _as_str(detail.get("kind"))
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


def render_batch_text(symbols: Sequence[Mapping[str, object]]) -> str:
    """Join individual renders with blank-line separator, handle errors."""
    if not symbols:
        return ""

    parts: list[str] = []
    for entry in symbols:
        if "error" in entry:
            name = _as_str(entry.get("name"), "?")
            error = _as_str(entry.get("error"))
            parts.append(f"{name}  ⚠ {error}")
        else:
            parts.append(render_symbol_text(entry))

    return "\n\n".join(parts)
