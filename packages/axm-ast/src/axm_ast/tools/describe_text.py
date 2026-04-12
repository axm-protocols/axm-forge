"""Text renderers for DescribeTool output."""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "render_describe_text",
]

_ANNOTATION_RE = re.compile(r":\s*[^,)=]+")


def render_describe_text(data: dict[str, Any], detail: str) -> str:
    """Render describe data as compact text for a given detail level."""
    modules: list[dict[str, Any]] = data.get("modules", [])

    match detail:
        case "toc":
            return _render_toc(modules, data.get("module_count", len(modules)))
        case "detailed":
            return _render_detailed(modules)
        case _:
            return _render_summary(modules)


def _render_toc(modules: list[dict[str, Any]], count: int) -> str:
    lines: list[str] = [f"# {count} modules"]
    for mod in modules:
        name = mod["name"]
        fc = mod.get("function_count", 0)
        cc = mod.get("class_count", 0)
        doc = mod.get("docstring", "")
        entry = f"{name}  {fc}f {cc}c"
        if doc:
            entry += f"  {doc}"
        lines.append(entry)
    return "\n".join(lines)


def _render_summary(modules: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for mod in modules:
        mod_name = mod["name"]
        funcs = mod.get("functions", [])
        classes = mod.get("classes", [])
        if not funcs and not classes:
            continue

        lines.append(mod_name)
        for fn in funcs:
            sig = fn.get("signature", "()")
            arrow = sig.rfind("->")
            if arrow != -1:
                sig = sig[:arrow].rstrip()
                depth = 0
                for i, c in enumerate(sig):
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            sig = sig[: i + 1]
                            break
            sig = _ANNOTATION_RE.sub("", sig)
            lines.append(f"  {fn['name']}{sig}")
        for cls in classes:
            lines.append(f"  {cls['name']}")
    return "\n".join(lines)


def _render_detailed(modules: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for mod in modules:
        mod_name = mod["name"]
        mod_lines: list[str] = [f"# {mod_name}"]

        doc = mod.get("docstring")
        if doc:
            first_line = doc.strip().split("\n")[0]
            mod_lines.append(f"  {first_line}")

        for fn in mod.get("functions", []):
            sig = fn.get("signature", "()")
            entry = f"{fn['name']}{sig}"
            summary = fn.get("summary")
            if summary:
                entry += f"  \u2014 {summary}"
            mod_lines.append(entry)

        for cls in mod.get("classes", []):
            bases = cls.get("bases", [])
            suffix = f"({', '.join(bases)})" if bases else ""
            entry = f"class {cls['name']}{suffix}"
            summary = cls.get("summary")
            if summary:
                entry += f"  \u2014 {summary}"
            mod_lines.append(entry)

            for method in cls.get("methods", []):
                msig = method.get("signature", "()")
                mentry = f"  {method['name']}{msig}"
                msummary = method.get("summary")
                if msummary:
                    mentry += f"  \u2014 {msummary}"
                mod_lines.append(mentry)

        parts.append("\n".join(mod_lines))
    return "\n\n".join(parts)
