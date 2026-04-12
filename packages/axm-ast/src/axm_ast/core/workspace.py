"""Workspace detection and multi-package analysis.

Detects uv workspaces via ``[tool.uv.workspace]`` in ``pyproject.toml``
and aggregates ``PackageInfo`` across all member packages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from axm_ast.core.cache import get_package
from axm_ast.models.nodes import PackageInfo, WorkspaceInfo

logger = logging.getLogger(__name__)


# ─── Workspace Detection ────────────────────────────────────────────────────


def detect_workspace(path: Path) -> WorkspaceInfo | None:
    """Detect a uv workspace at the given path.

    Reads ``pyproject.toml`` looking for ``[tool.uv.workspace]`` members.
    If found, resolves each member's source package directory and returns
    a populated ``WorkspaceInfo``. Returns ``None`` if not a workspace.

    Args:
        path: Path to potential workspace root.

    Returns:
        WorkspaceInfo if workspace detected, None otherwise.

    Example:
        >>> ws = detect_workspace(Path("/path/to/workspace"))
        >>> ws is not None
        True
    """
    path = Path(path).resolve()
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return None

    text = pyproject.read_text()
    members = _parse_workspace_members(text)
    if not members:
        return None

    ws_name = _parse_project_name(text) or path.name

    return WorkspaceInfo(
        name=ws_name,
        root=path,
        packages=[],
        package_edges=[],
    )


def _parse_workspace_members(text: str) -> list[str]:
    """Extract workspace member names from pyproject.toml text.

    Parses the ``[tool.uv.workspace]`` members list.

    Args:
        text: Raw pyproject.toml content.

    Returns:
        List of member directory names, empty if not found.
    """
    # Match [tool.uv.workspace] section
    match = re.search(
        r"\[tool\.uv\.workspace\]\s*\n\s*members\s*=\s*\[([^\]]*)\]",
        text,
        re.DOTALL,
    )
    if not match:
        return []

    raw = match.group(1)
    return [m.strip().strip("\"'") for m in raw.split(",") if m.strip().strip("\"'")]


def _expand_workspace_members(root: Path, raw_members: list[str]) -> list[str]:
    """Expand glob patterns in workspace member list to concrete directory paths.

    Entries containing glob characters (``*``, ``?``, ``[``) are expanded
    via :meth:`Path.glob`. Literal entries are passed through unchanged.
    Only directories are kept; files matching a glob are filtered out.

    Args:
        root: Workspace root directory.
        raw_members: Raw member strings, possibly containing globs.

    Returns:
        List of expanded relative directory paths.
    """
    expanded: list[str] = []
    glob_chars = {"*", "?", "["}
    for member in raw_members:
        if any(c in member for c in glob_chars):
            matches = sorted(p for p in root.glob(member) if p.is_dir())
            if not matches:
                logger.warning("Glob pattern %r matched no directories", member)
            for match in matches:
                expanded.append(str(match.relative_to(root)))
        else:
            expanded.append(member)
    return expanded


def _parse_project_name(text: str) -> str | None:
    """Extract project name from pyproject.toml text.

    Args:
        text: Raw pyproject.toml content.

    Returns:
        Project name or None if not found.
    """
    match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def _is_python_package(path: Path) -> bool:
    """Check if a directory is a Python package or namespace package."""
    if not path.is_dir():
        return False
    return (path / "__init__.py").exists() or any(path.glob("*.py"))


_FLAT_LAYOUT_EXCLUDE = {"tests", "docs", ".venv", ".git", "__pycache__"}


def _find_in_src_layout(member_path: Path) -> Path | None:
    """Search for a Python package under ``src/``."""
    src_dir = member_path / "src"
    if not src_dir.is_dir():
        return None
    for child in sorted(src_dir.iterdir()):
        if _is_python_package(child):
            return child
    return None


def _find_in_flat_layout(member_path: Path) -> Path | None:
    """Search for a Python package at the member root (flat layout)."""
    for child in sorted(member_path.iterdir()):
        if (
            child.is_dir()
            and child.name not in _FLAT_LAYOUT_EXCLUDE
            and (child / "__init__.py").exists()
        ):
            return child
    return None


def _find_package_source(member_path: Path) -> Path | None:
    """Find the Python source package directory for a workspace member.

    Checks ``src/<pkg_name>/`` first (src layout), then falls back
    to flat layout (directory with ``__init__.py``).

    Args:
        member_path: Root directory of the workspace member.

    Returns:
        Path to the source package, or None if not found.
    """
    return _find_in_src_layout(member_path) or _find_in_flat_layout(member_path)


def _parse_member_deps(member_path: Path) -> list[str]:
    """Extract dependencies from a member's pyproject.toml.

    Only returns dependency names (normalized), without version specs.

    Args:
        member_path: Root directory of the workspace member.

    Returns:
        List of dependency names.
    """
    pyproject = member_path / "pyproject.toml"
    if not pyproject.exists():
        return []

    text = pyproject.read_text()
    match = re.search(
        r"\[project\].*?dependencies\s*=\s*\[([^\]]*)\]",
        text,
        re.DOTALL,
    )
    if not match:
        return []

    raw = match.group(1)
    deps: list[str] = []
    for dep in raw.split(","):
        dep = dep.strip().strip("\"'")
        if dep:
            # Normalize: strip version specs, extras, etc.
            name = re.split(r"[>=<!\[;]", dep)[0].strip()
            if name:
                deps.append(name)
    return deps


# ─── Workspace Analysis ─────────────────────────────────────────────────────


def analyze_workspace(path: Path) -> WorkspaceInfo:
    """Analyze all packages in a uv workspace.

    Discovers workspace members, analyzes each with ``analyze_package()``,
    and builds inter-package dependency edges.

    Args:
        path: Path to workspace root.

    Returns:
        WorkspaceInfo with all packages and dependency edges.

    Raises:
        ValueError: If path is not a workspace root.

    Example:
        >>> ws = analyze_workspace(Path("/path/to/workspace"))
        >>> len(ws.packages) > 0
        True
    """
    path = Path(path).resolve()
    ws = detect_workspace(path)
    if ws is None:
        msg = f"{path} is not a uv workspace"
        raise ValueError(msg)

    pyproject_text = (path / "pyproject.toml").read_text()
    raw_members = _parse_workspace_members(pyproject_text)
    members = _expand_workspace_members(path, raw_members)

    # Build member_names from project names in each member's pyproject.toml
    member_names: set[str] = set()
    for member in members:
        member_pyproject = path / member / "pyproject.toml"
        if member_pyproject.exists():
            name = _parse_project_name(member_pyproject.read_text())
            if name:
                member_names.add(name)
        member_names.add(Path(member).name)

    packages: list[PackageInfo] = []
    for member in members:
        member_path = path / member
        if not member_path.is_dir():
            logger.warning("Workspace member %s not found, skipping", member)
            continue

        pkg_src = _find_package_source(member_path)
        if pkg_src is None:
            logger.warning("No source package found in %s, skipping", member)
            continue

        try:
            pkg = get_package(pkg_src)
            packages.append(pkg)
        except (OSError, ValueError):
            logger.warning("Failed to analyze %s, skipping", member, exc_info=True)

    # Build inter-package dependency edges
    package_edges = _build_package_edges(path, members, member_names)

    ws.packages = packages
    ws.package_edges = package_edges
    return ws


def _build_package_edges(
    ws_root: Path,
    members: list[str],
    member_names: set[str],
) -> list[tuple[str, str]]:
    """Build inter-package dependency edges from pyproject.toml deps.

    Args:
        ws_root: Workspace root directory.
        members: List of member directory paths (may include subdirs).
        member_names: Set of known package names for fast lookup.

    Returns:
        List of (from_pkg, to_pkg) edges.
    """
    # Build lookup from project name → member path, falling back to dir basename
    name_to_member: dict[str, str] = {}
    for member in members:
        member_path = ws_root / member
        pyproject = member_path / "pyproject.toml"
        if pyproject.exists():
            proj_name = _parse_project_name(pyproject.read_text())
            if proj_name:
                name_to_member[proj_name] = member
        name_to_member.setdefault(Path(member).name, member)

    all_names = member_names | set(name_to_member)

    edges: list[tuple[str, str]] = []
    for member in members:
        member_path = ws_root / member
        deps = _parse_member_deps(member_path)
        for dep in deps:
            if dep in all_names:
                edges.append((member, dep))
    return edges


def build_workspace_dep_graph(ws: WorkspaceInfo) -> dict[str, list[str]]:
    """Build an adjacency-list dependency graph between packages.

    Args:
        ws: Analyzed workspace info.

    Returns:
        Dict mapping package dir name to list of packages it depends on.

    Example:
        >>> graph = build_workspace_dep_graph(ws)
        >>> graph["axm-mcp"]
        `['axm']`
    """
    graph: dict[str, list[str]] = {}
    for src, target in ws.package_edges:
        graph.setdefault(src, []).append(target)
    return graph


def format_workspace_graph_mermaid(ws: WorkspaceInfo) -> str:
    """Format the inter-package dependency graph as Mermaid.

    Args:
        ws: Analyzed workspace info.

    Returns:
        Mermaid diagram string.
    """
    graph = build_workspace_dep_graph(ws)
    lines = ["graph TD"]

    # Add package nodes
    pkg_names = {e[0] for e in ws.package_edges} | {e[1] for e in ws.package_edges}
    for pkg in ws.packages:
        name = pkg.name
        if name not in pkg_names:
            # Also include packages without edges
            safe = name.replace("-", "_").replace(".", "_")
            lines.append(f'    {safe}["{name}"]')

    for src, targets in graph.items():
        safe_src = src.replace("-", "_").replace(".", "_")
        for target in targets:
            safe_target = target.replace("-", "_").replace(".", "_")
            lines.append(f"    {safe_src} --> {safe_target}")

    return "\n".join(lines)


# ─── Workspace Context ──────────────────────────────────────────────────────


def build_workspace_context(path: Path) -> dict[str, Any]:
    """Build complete workspace context in one call.

    Lists all packages, their mutual dependencies, per-package stats,
    and the workspace-level dependency graph.

    Args:
        path: Path to workspace root.

    Returns:
        Workspace context dict.
    """
    ws = analyze_workspace(path)
    graph = build_workspace_dep_graph(ws)

    pkg_summaries = []
    for pkg in ws.packages:
        fn_count = sum(len(m.functions) for m in pkg.modules)
        cls_count = sum(len(m.classes) for m in pkg.modules)
        pkg_summaries.append(
            {
                "name": pkg.name,
                "root": str(pkg.root),
                "module_count": len(pkg.modules),
                "function_count": fn_count,
                "class_count": cls_count,
            }
        )

    return {
        "workspace": ws.name,
        "root": str(ws.root),
        "package_count": len(ws.packages),
        "packages": pkg_summaries,
        "package_graph": graph,
    }


def format_workspace_text(ctx: dict[str, Any]) -> str:
    """Format workspace context as compact plain text for ToolResult.text.

    Args:
        ctx: Workspace context dict from :func:`build_workspace_context`
            or :func:`format_workspace_context`.

    Returns:
        Compact text string.
    """
    lines: list[str] = []
    lines.append(
        f"{ctx.get('workspace', '')} | workspace | "
        f"{ctx.get('package_count', 0)} packages"
    )

    packages = ctx.get("packages", [])
    if packages:
        lines.append("")
        lines.append("Packages:")
        for pkg in packages:
            mod_c = pkg.get("module_count")
            if mod_c is not None:
                fn_c = pkg.get("function_count", 0)
                cls_c = pkg.get("class_count", 0)
                lines.append(f"  {pkg['name']}: {mod_c} mod, {fn_c} fn, {cls_c} cls")
            else:
                lines.append(f"  {pkg['name']}")

    graph = ctx.get("package_graph", {})
    if graph:
        lines.append("")
        lines.append("Dependencies:")
        for src in sorted(graph):
            lines.append(f"  {src} → {', '.join(graph[src])}")

    return "\n".join(lines)


def format_workspace_context(ctx: dict[str, Any], *, depth: int = 1) -> dict[str, Any]:
    """Apply depth-based filtering to workspace context.

    Args:
        ctx: Full workspace context from :func:`build_workspace_context`.
        depth: Detail level. 0 = compact (names only, no graph),
            >= 1 = full output.

    Returns:
        Filtered workspace context dict.
    """
    if depth >= 1:
        return ctx

    return {
        "workspace": ctx["workspace"],
        "root": ctx["root"],
        "package_count": ctx["package_count"],
        "packages": [{"name": pkg["name"]} for pkg in ctx["packages"]],
    }
