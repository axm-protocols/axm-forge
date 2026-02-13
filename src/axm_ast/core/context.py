"""One-shot project context dump for AI agents.

Detects project stack (CLI, models, tests, lint, etc.), AXM tools,
coding patterns, and module structure — all in a single command.

Example:
    >>> from axm_ast.core.context import build_context, format_context
    >>> ctx = build_context(Path("src/axm_ast"), project_root=Path("."))
    >>> print(format_context(ctx))
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from axm_ast.core.analyzer import (
    _module_dotted_name,
    analyze_package,
    build_import_graph,
)
from axm_ast.core.ranker import rank_symbols
from axm_ast.models.nodes import PackageInfo

__all__ = [
    "build_context",
    "detect_axm_tools",
    "detect_patterns",
    "detect_stack",
    "format_context",
    "format_context_json",
]


# ─── Stack categories ────────────────────────────────────────────────────────

STACK_CATEGORIES: dict[str, list[str]] = {
    "cli": ["click", "typer", "cyclopts", "argparse", "fire"],
    "models": ["pydantic", "attrs", "dataclasses-json", "marshmallow"],
    "web": ["fastapi", "flask", "django", "starlette", "litestar"],
    "parsing": ["tree-sitter", "ast", "libcst", "parso"],
    "tests": ["pytest", "unittest", "hypothesis", "ward"],
    "lint": ["ruff", "flake8", "pylint", "black", "isort"],
    "types": ["mypy", "pyright", "pytype"],
    "docs": [
        "mkdocs",
        "mkdocs-material",
        "sphinx",
        "pdoc",
        "mkdocstrings",
    ],
    "packaging": [
        "hatchling",
        "setuptools",
        "flit",
        "poetry",
        "pdm",
        "maturin",
    ],
}

AXM_TOOLS = ["axm-ast", "axm-audit", "axm-init"]


# ─── Stack detection ─────────────────────────────────────────────────────────


def detect_stack(root: Path) -> dict[str, list[str]]:
    """Parse pyproject.toml and categorize dependencies.

    Args:
        root: Project root directory containing pyproject.toml.

    Returns:
        Dict mapping category names to matched dependency names.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}

    text = pyproject.read_text(encoding="utf-8")
    deps = _extract_deps(text)
    dev_deps = _extract_dev_deps(text)
    build_deps = _extract_build_system(text)

    all_deps = deps + dev_deps + build_deps
    return _categorize_deps(all_deps)


def _extract_deps(text: str) -> list[str]:
    """Extract dependencies from [project] section."""
    return _parse_dep_list(text, "dependencies")


def _extract_dev_deps(text: str) -> list[str]:
    """Extract dev dependencies from [dependency-groups] or extras."""
    deps: list[str] = []
    # [dependency-groups] dev = [...]
    deps.extend(_parse_dep_list(text, "dev"))
    return deps


def _extract_build_system(text: str) -> list[str]:
    """Extract build system requires."""
    return _parse_dep_list(text, "requires")


def _parse_dep_list(text: str, key: str) -> list[str]:
    """Parse a TOML-like dep list: key = ["dep1", "dep2"]."""
    import re

    # Match: key = [...] across lines
    pattern = rf"{key}\s*=\s*\[(.*?)\]"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return []

    items_text = match.group(1)
    # Extract quoted strings
    names = re.findall(r'"([^"]+)"', items_text)
    # Normalize: "pytest>=8.0" → "pytest"
    return [_normalize_dep_name(n) for n in names]


def _normalize_dep_name(dep: str) -> str:
    """Normalize dep name: 'cyclopts>=3.0' → 'cyclopts'."""
    import re

    name = re.split(r"[>=<!\[;]", dep)[0].strip()
    return name.lower().replace("_", "-")


def _categorize_deps(deps: list[str]) -> dict[str, list[str]]:
    """Categorize dependency names into stack categories."""
    result: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for dep in deps:
        for category, known in STACK_CATEGORIES.items():
            for known_dep in known:
                if dep == known_dep or dep.startswith(known_dep):
                    key = (category, dep)
                    if key not in seen:
                        seen.add(key)
                        result.setdefault(category, []).append(dep)
                    break
    return result


# ─── AXM tools detection ────────────────────────────────────────────────────


def detect_axm_tools() -> dict[str, str]:
    """Detect installed AXM ecosystem tools.

    Returns:
        Dict mapping tool name to path, only for installed tools.
    """
    tools: dict[str, str] = {}
    for tool in AXM_TOOLS:
        path = shutil.which(tool)
        if path is not None:
            tools[tool] = path
    return tools


# ─── Pattern detection ───────────────────────────────────────────────────────


def detect_patterns(pkg: PackageInfo, project_root: Path) -> dict[str, Any]:
    """Detect coding patterns in the analyzed package.

    Args:
        pkg: Analyzed package info.
        project_root: Root of the project (for test detection).

    Returns:
        Dict of detected patterns.
    """
    # Count __all__ usage
    all_count = sum(1 for mod in pkg.modules if mod.all_exports is not None)

    # Detect layout type
    layout = _detect_layout(pkg, project_root)

    # Count test files
    test_count = _count_test_files(project_root)

    # Count total symbols
    func_count = sum(len(m.functions) for m in pkg.modules)
    class_count = sum(len(m.classes) for m in pkg.modules)

    return {
        "all_exports_count": all_count,
        "layout": layout,
        "test_count": test_count,
        "module_count": len(pkg.modules),
        "function_count": func_count,
        "class_count": class_count,
    }


def _detect_layout(pkg: PackageInfo, project_root: Path) -> str:
    """Detect project layout: 'src' or 'flat'."""
    root_str = str(pkg.root)
    if "/src/" in root_str or root_str.startswith(str(project_root / "src")):
        return "src"
    return "flat"


def _count_test_files(root: Path) -> int:
    """Count test_*.py files in the project."""
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return 0
    return len(list(tests_dir.glob("test_*.py")))


# ─── Context building ───────────────────────────────────────────────────────


def build_context(
    path: Path,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Build complete project context in one call.

    Orchestrates: analyze_package + detect_stack + detect_axm_tools
    + detect_patterns + rank_symbols.

    Args:
        path: Path to the package directory.
        project_root: Project root (for pyproject.toml, tests).
            Defaults to path.parent or path.parent.parent for src layout.

    Returns:
        Complete context dict with all project info.
    """
    pkg = analyze_package(path)

    # Infer project root
    if project_root is None:
        project_root = _infer_project_root(path)

    stack = detect_stack(project_root)
    axm_tools = detect_axm_tools()
    patterns = detect_patterns(pkg, project_root)
    scores = rank_symbols(pkg)
    graph = build_import_graph(pkg)

    # Build module summaries with rank stars
    modules = _build_module_summaries(pkg, scores)

    return {
        "name": pkg.name,
        "root": str(pkg.root),
        "python": _detect_python_version(project_root),
        "stack": stack,
        "axm_tools": axm_tools,
        "patterns": patterns,
        "modules": modules,
        "dependency_graph": graph,
    }


def _infer_project_root(path: Path) -> Path:
    """Infer project root from package path."""
    # If path is inside src/, go up two levels
    if path.parent.name == "src":
        return path.parent.parent
    return path.parent


def _detect_python_version(root: Path) -> str | None:
    """Extract requires-python from pyproject.toml."""
    import re

    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _build_module_summaries(
    pkg: PackageInfo,
    scores: dict[str, float],
) -> list[dict[str, Any]]:
    """Build module summaries with importance stars."""
    summaries: list[dict[str, Any]] = []

    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)

        # Collect symbols with scores
        sym_scores: list[float] = []
        sym_names: list[str] = []
        for fn in mod.functions:
            if fn.is_public:
                sym_names.append(fn.name)
                sym_scores.append(scores.get(fn.name, 0.0))
        for cls in mod.classes:
            if cls.is_public:
                sym_names.append(cls.name)
                sym_scores.append(scores.get(cls.name, 0.0))

        # Module importance = max symbol score
        max_score = max(sym_scores) if sym_scores else 0.0
        stars = _score_to_stars(max_score, len(sym_names))

        summaries.append(
            {
                "name": mod_name,
                "stars": stars,
                "symbols": sym_names,
                "symbol_count": len(sym_names),
            }
        )

    # Sort by importance
    summaries.sort(key=lambda m: m["stars"], reverse=True)
    return summaries


def _score_to_stars(score: float, symbol_count: int) -> int:
    """Convert PageRank score + symbol count to 1-5 stars."""
    if symbol_count == 0:
        return 1
    # Combine score and symbol count
    combined = score * 100 + symbol_count * 0.5
    if combined > 5:
        return 5
    if combined > 3:
        return 4
    if combined > 1.5:
        return 3
    if combined > 0.5:
        return 2
    return 1


# ─── Formatting ──────────────────────────────────────────────────────────────


def format_context(ctx: dict[str, Any]) -> str:
    """Format context as human-readable text.

    Args:
        ctx: Context dict from build_context.

    Returns:
        Formatted text string.
    """
    sections = [
        _fmt_header(ctx),
        _fmt_stack(ctx.get("stack", {})),
        _fmt_tools(ctx.get("axm_tools", {})),
        _fmt_patterns(ctx.get("patterns", {})),
        _fmt_modules(ctx.get("modules", [])),
        _fmt_graph(ctx.get("dependency_graph", {})),
    ]
    return "\n".join(s for s in sections if s)


def _fmt_header(ctx: dict[str, Any]) -> str:
    """Format the header section."""
    lines = [f"📋 {ctx['name']}"]
    patterns = ctx.get("patterns", {})
    lines.append(
        f"  layout: {patterns.get('layout', '?')}"
        f" ({patterns.get('module_count', 0)} modules,"
        f" {patterns.get('function_count', 0)} functions,"
        f" {patterns.get('class_count', 0)} classes)"
    )
    py = ctx.get("python")
    if py:
        lines.append(f"  python: {py}")
    lines.append("")
    return "\n".join(lines)


def _fmt_stack(stack: dict[str, list[str]]) -> str:
    """Format the stack section."""
    if not stack:
        return ""
    lines = ["🔧 Stack"]
    for category, deps in sorted(stack.items()):
        lines.append(f"  {category}: {', '.join(deps)}")
    lines.append("")
    return "\n".join(lines)


def _fmt_tools(axm_tools: dict[str, str]) -> str:
    """Format the AXM tools section."""
    if not axm_tools:
        return ""
    lines = ["🛠 AXM Tools"]
    for tool in sorted(axm_tools):
        lines.append(f"  {tool}: ✅")
    lines.append("")
    return "\n".join(lines)


def _fmt_patterns(patterns: dict[str, Any]) -> str:
    """Format the patterns section."""
    lines = ["📐 Patterns"]
    lines.append(
        f"  exports: __all__ in {patterns.get('all_exports_count', 0)} modules"
    )
    tests = patterns.get("test_count", 0)
    if tests:
        lines.append(f"  tests: {tests} test files")
    lines.append("")
    return "\n".join(lines)


def _fmt_modules(modules: list[dict[str, Any]]) -> str:
    """Format the modules section."""
    if not modules:
        return ""
    lines = ["📦 Modules (ranked)"]
    for mod in modules:
        stars = "★" * mod["stars"] + "☆" * (5 - mod["stars"])
        syms = _truncate_symbols(mod["symbols"])
        lines.append(f"  {mod['name']:30s} {stars}  ({syms})")
    lines.append("")
    return "\n".join(lines)


def _truncate_symbols(symbols: list[str], limit: int = 5) -> str:
    """Truncate symbol list for display."""
    text = ", ".join(symbols[:limit])
    if len(symbols) > limit:
        text += f"... (+{len(symbols) - limit})"
    return text


def _fmt_graph(graph: dict[str, list[str]]) -> str:
    """Format the dependency graph section."""
    if not graph:
        return ""
    lines = ["🔗 Dependencies"]
    for src, targets in sorted(graph.items()):
        lines.append(f"  {src} → {', '.join(targets)}")
    lines.append("")
    return "\n".join(lines)


def format_context_json(ctx: dict[str, Any]) -> dict[str, Any]:
    """Format context as JSON-serializable dict.

    Args:
        ctx: Context dict from build_context.

    Returns:
        JSON-serializable dict.
    """
    return ctx
