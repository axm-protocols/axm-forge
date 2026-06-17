"""Workspace detection and multi-package analysis.

Detects uv workspaces via ``[tool.uv.workspace]`` in ``pyproject.toml``
and aggregates ``PackageInfo`` across all member packages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TypedDict

from axm_ingot.uv import parse_workspace_members, resolve_workspace

from axm_ast.core.analyzer import build_import_graph, module_dotted_name
from axm_ast.core.cache import get_package
from axm_ast.models.nodes import PackageInfo, WorkspaceInfo

logger = logging.getLogger(__name__)


class PackageSummary(TypedDict, total=False):
    """Per-package summary entry inside a :class:`WorkspaceContext`.

    ``total=False`` so depth-0 outputs (name only) remain valid.
    """

    name: str
    root: str
    module_count: int
    function_count: int
    class_count: int


class WorkspaceContext(TypedDict, total=False):
    """Aggregate workspace context returned by :func:`build_workspace_context`.

    ``total=False`` because the depth-0 view from
    :func:`format_workspace_context` drops ``package_graph``.
    """

    workspace: str
    root: str
    package_count: int
    packages: list[PackageSummary]
    package_graph: dict[str, list[str]]


# ─── Workspace Detection ────────────────────────────────────────────────────


def detect_workspace(path: Path) -> WorkspaceInfo | None:
    """Detect a uv workspace at the given path.

    Delegates uv-workspace resolution to :func:`axm_ingot.uv.resolve_workspace`
    (the canonical, stdlib-only resolver) and then *projects* the resulting
    ``ResolvedWorkspace`` onto a :class:`WorkspaceInfo` (name + root). The
    Pydantic ``WorkspaceInfo`` model stays defined in axm-ast; ingot remains
    leaf and never sees a Pydantic type. Returns ``None`` if not a workspace
    (no ``[tool.uv.workspace]`` table, missing/malformed pyproject, or no
    resolvable members).

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
    resolved = resolve_workspace(path)
    if resolved is None:
        return None

    pyproject_text = (path / "pyproject.toml").read_text()
    # A workspace must DECLARE members; an empty ``members = []`` is not a
    # workspace. ingot's ``ResolvedWorkspace`` collapses declared-but-yet-
    # unresolvable members (e.g. a glob matching nothing) to an empty tuple,
    # so the declared-members check stays on the raw text to preserve the
    # historical contract: a glob workspace with no current matches is still
    # a workspace (analyze_workspace then reports zero packages + a warning).
    if not parse_workspace_members(pyproject_text):
        return None

    ws_name = _parse_project_name(pyproject_text) or path.name

    return WorkspaceInfo(
        name=ws_name,
        root=resolved.root,
        packages=[],
        package_edges=[],
    )


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


def _package_module_names(pkg: PackageInfo) -> set[str]:
    """Return the set of dotted module names owned by *pkg*."""
    return {module_dotted_name(mod.path, pkg.root) for mod in pkg.modules}


def _resolve_target_node(
    target: str,
    pkg_name: str,
    own_modules: set[str],
    owners: dict[str, str],
) -> str:
    """Namespace an import *target* to its owning package.

    Intra-package targets keep ``pkg_name``. A target owned by another
    package gets that owner's prefix (cross-package edge, AC5). Targets
    resolvable to no package are kept under ``pkg_name`` (best-effort).
    """
    if target in own_modules:
        return f"{pkg_name}.{target}"
    owner = owners.get(target)
    if owner is not None:
        return f"{owner}.{target}"
    return f"{pkg_name}.{target}"


def _cross_package_target(
    imp_module: str | None,
    names: list[str],
    module_sets: dict[str, set[str]],
    self_name: str,
) -> str | None:
    """Resolve an absolute import to a ``{pkg}.{module}`` node in another package.

    Returns ``None`` for relative imports, self-package imports, and
    imports of packages outside the workspace (external dependencies).
    """
    if not imp_module:
        return None
    head, _, rest = imp_module.partition(".")
    if head == self_name or head not in module_sets:
        return None
    owned = module_sets[head]
    # ``import pkg.sub`` — the dotted remainder is the module.
    if rest and rest in owned:
        return f"{head}.{rest}"
    # ``from pkg import sub`` — a single imported name that is a module.
    for name in names:
        if name in owned:
            return f"{head}.{name}"
    # Fall back to the package root module.
    return f"{head}.{head}" if head in owned else head


def _collect_cross_package_edges(
    pkg: PackageInfo,
    module_sets: dict[str, set[str]],
    graph: dict[str, list[str]],
) -> None:
    """Add cross-package edges for *pkg* derived from raw module imports."""
    for mod in pkg.modules:
        src_node = f"{pkg.name}.{module_dotted_name(mod.path, pkg.root)}"
        targets = graph.setdefault(src_node, [])
        for imp in mod.imports:
            if imp.is_relative:
                continue
            target = _cross_package_target(imp.module, imp.names, module_sets, pkg.name)
            if target is not None and target not in targets:
                targets.append(target)


def build_workspace_module_graph(ws: WorkspaceInfo) -> dict[str, list[str]]:
    """Build a merged module-level import graph across all packages.

    Reuses :func:`build_import_graph` per package and namespaces every
    node as ``{package_name}.{module}``. Cross-package import targets are
    resolved to their owning package so edges stay namespaced rather than
    bare module names (lets anvil tell which package each node belongs to).

    Args:
        ws: Analyzed workspace info with ``.packages``.

    Returns:
        Adjacency-list dict mapping ``{pkg}.{module}`` to the list of
        ``{pkg}.{module}`` nodes it imports.

    Example:
        >>> graph = build_workspace_module_graph(ws)
        >>> graph["axm-mcp.cli"]
        `['axm.tools']`
    """
    module_sets = {pkg.name: _package_module_names(pkg) for pkg in ws.packages}
    owners: dict[str, str] = {}
    for pkg in ws.packages:
        for name in module_sets[pkg.name]:
            owners.setdefault(name, pkg.name)

    graph: dict[str, list[str]] = {}
    for pkg in ws.packages:
        own_modules = module_sets[pkg.name]
        for src, targets in build_import_graph(pkg).items():
            src_node = f"{pkg.name}.{src}"
            graph.setdefault(src_node, []).extend(
                _resolve_target_node(target, pkg.name, own_modules, owners)
                for target in targets
            )
    # Cross-package edges are absent from per-package dependency_edges, so
    # derive them from raw module imports (AC5).
    for pkg in ws.packages:
        _collect_cross_package_edges(pkg, module_sets, graph)
    return graph


def analyze_workspace(
    path: Path, *, detected: WorkspaceInfo | None = None
) -> WorkspaceInfo:
    """Analyze all packages in a uv workspace.

    Discovers workspace members, analyzes each with ``analyze_package()``,
    and builds inter-package dependency edges.

    Args:
        path: Path to workspace root.
        detected: A ``WorkspaceInfo`` already produced by
            :func:`detect_workspace` for the same ``path``. When provided,
            the redundant internal detection is skipped (the caller has
            already paid for it). When ``None`` (default), detection runs
            here as before.

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
    ws = detected if detected is not None else detect_workspace(path)
    if ws is None:
        msg = f"{path} is not a uv workspace"
        raise ValueError(msg)

    pyproject_text = (path / "pyproject.toml").read_text()
    raw_members = parse_workspace_members(pyproject_text)
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
    for pkg in ws.packages:
        name = pkg.name
        safe = name.replace("-", "_").replace(".", "_")
        lines.append(f'    {safe}["{name}"]')

    for src, targets in graph.items():
        safe_src = src.replace("-", "_").replace(".", "_")
        for target in targets:
            safe_target = target.replace("-", "_").replace(".", "_")
            lines.append(f"    {safe_src} --> {safe_target}")

    return "\n".join(lines)


# ─── Workspace Context ──────────────────────────────────────────────────────


def build_workspace_context(path: Path) -> WorkspaceContext:
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

    pkg_summaries: list[PackageSummary] = []
    for pkg in ws.packages:
        fn_count = sum(len(m.functions) for m in pkg.modules)
        cls_count = sum(len(m.classes) for m in pkg.modules)
        pkg_summaries.append(
            PackageSummary(
                name=pkg.name,
                root=str(pkg.root),
                module_count=len(pkg.modules),
                function_count=fn_count,
                class_count=cls_count,
            )
        )

    return WorkspaceContext(
        workspace=ws.name,
        root=str(ws.root),
        package_count=len(ws.packages),
        packages=pkg_summaries,
        package_graph=graph,
    )


def format_workspace_text(ctx: WorkspaceContext) -> str:
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


def format_workspace_context(
    ctx: WorkspaceContext, *, depth: int = 1
) -> WorkspaceContext:
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

    return WorkspaceContext(
        workspace=ctx["workspace"],
        root=ctx["root"],
        package_count=ctx["package_count"],
        packages=[PackageSummary(name=pkg["name"]) for pkg in ctx["packages"]],
    )
