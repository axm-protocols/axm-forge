"""Workspace detection and multi-package analysis.

Detects uv workspaces via ``[tool.uv.workspace]`` in ``pyproject.toml``
and aggregates ``PackageInfo`` across all member packages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from axm_ast.core.analyzer import analyze_package
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


def _parse_project_name(text: str) -> str | None:
    """Extract project name from pyproject.toml text.

    Args:
        text: Raw pyproject.toml content.

    Returns:
        Project name or None if not found.
    """
    match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def _find_package_source(member_path: Path) -> Path | None:
    """Find the Python source package directory for a workspace member.

    Checks ``src/<pkg_name>/`` first (src layout), then falls back
    to flat layout (directory with ``__init__.py``).

    Args:
        member_path: Root directory of the workspace member.

    Returns:
        Path to the source package, or None if not found.
    """
    src_dir = member_path / "src"
    if src_dir.is_dir():
        for child in sorted(src_dir.iterdir()):
            if child.is_dir() and (child / "__init__.py").exists():
                return child
            # Namespace package without __init__.py
            if child.is_dir() and any(child.glob("*.py")):
                return child

    # Flat layout: look for __init__.py directly
    for child in sorted(member_path.iterdir()):
        if (
            child.is_dir()
            and child.name not in {"tests", "docs", ".venv", ".git", "__pycache__"}
            and (child / "__init__.py").exists()
        ):
            return child

    return None


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
    members = _parse_workspace_members(pyproject_text)
    member_names: set[str] = set(members)

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
            pkg = analyze_package(pkg_src)
            packages.append(pkg)
        except Exception:
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
        members: List of member directory names.
        member_names: Set of member names for fast lookup.

    Returns:
        List of (from_pkg, to_pkg) edges.
    """
    edges: list[tuple[str, str]] = []
    for member in members:
        member_path = ws_root / member
        deps = _parse_member_deps(member_path)
        for dep in deps:
            if dep in member_names:
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
        ['axm']
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
