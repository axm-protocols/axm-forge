"""Text renderers for DescribeTool output."""

from __future__ import annotations

from typing import Any

__all__ = [
    "render_describe_text",
]


def render_describe_text(data: dict[str, Any], detail: str) -> str:
    """Render describe data as compact text for a given detail level."""
    modules: list[dict[str, Any]] = data.get("modules", [])
    count = data.get("module_count", len(modules))
    header = f"ast_describe | {detail} | {count} modules"

    match detail:
        case "toc":
            return _render_toc(modules, header)
        case "detailed":
            return _render_detailed(modules, header)
        case _:
            return _render_summary(modules, header)


def _render_toc(modules: list[dict[str, Any]], header: str) -> str:
    if not modules:
        return header
    lines: list[str] = [header]
    for mod in modules:
        name = mod["name"]
        fn_count = mod.get("function_count", 0)
        cls_count = mod.get("class_count", 0)
        docstring = mod.get("docstring")

        parts: list[str] = []
        if fn_count:
            parts.append(f"{fn_count}fn")
        if cls_count:
            parts.append(f"{cls_count}cls")
        counts = " ".join(parts) if parts else "\u2014"

        line = f"  {name}  ({counts})"
        if docstring:
            line += f"  {docstring}"
        lines.append(line)
    return "\n".join(lines)


def _strip_def(sig: str) -> str:
    if sig.startswith("def "):
        return sig[4:]
    return sig


def _render_function_signature(fn: dict[str, Any]) -> str:
    return f"  {_strip_def(fn['signature'])}"


def _render_class_label(cls: dict[str, Any]) -> str:
    bases = ", ".join(cls["bases"]) if cls.get("bases") else ""
    label = f"class {cls['name']}({bases})" if bases else f"class {cls['name']}"
    return f"  {label}"


def _render_module_section(mod: dict[str, Any]) -> list[str] | None:
    functions = mod.get("functions", [])
    classes = mod.get("classes", [])
    if not functions and not classes:
        return None
    lines = [f"## {mod['name']}"]
    lines.extend(_render_function_signature(fn) for fn in functions)
    lines.extend(_render_class_label(cls) for cls in classes)
    return lines


def _render_summary(modules: list[dict[str, Any]], header: str) -> str:
    """Render the signature-level summary view, skipping empty modules."""
    lines: list[str] = [header]
    for mod in modules:
        section = _render_module_section(mod)
        if section is not None:
            lines.extend(section)
    return "\n".join(lines)


def _render_functions(functions: list[dict[str, Any]], lines: list[str]) -> None:
    for fn in functions:
        sig = fn["signature"]
        if sig.startswith("def "):
            sig = sig[4:]
        summary = fn.get("summary")
        if summary:
            lines.append(f"  {sig}  # {summary}")
        else:
            lines.append(f"  {sig}")


def _render_classes(classes: list[dict[str, Any]], lines: list[str]) -> None:
    for cls in classes:
        bases = ", ".join(cls["bases"]) if cls.get("bases") else ""
        label = f"class {cls['name']}({bases})" if bases else f"class {cls['name']}"
        summary = cls.get("summary")
        if summary:
            lines.append(f"  {label}  # {summary}")
        else:
            lines.append(f"  {label}")
        for method in cls.get("methods", []):
            msig = method["signature"]
            if msig.startswith("def "):
                msig = msig[4:]
            msummary = method.get("summary")
            if msummary:
                lines.append(f"    .{msig}  # {msummary}")
            else:
                lines.append(f"    .{msig}")


def _render_detailed(modules: list[dict[str, Any]], header: str) -> str:
    lines: list[str] = [header]
    for mod in modules:
        functions = mod.get("functions", [])
        classes = mod.get("classes", [])
        docstring = mod.get("docstring")

        if not functions and not classes and not docstring:
            continue

        mod_header = f"## {mod['name']}"
        if docstring:
            first_line = docstring.strip().split("\n")[0]
            mod_header += f" \u2014 {first_line}"
        lines.append(mod_header)

        _render_functions(functions, lines)
        _render_classes(classes, lines)
    return "\n".join(lines)
