"""Change impact analysis — who is affected when you modify a symbol.

Composes ``callers``, ``graph``, and ``search`` into a single
"what breaks if I change X?" answer.

Example:
    >>> from axm_ast.core.impact import analyze_impact
    >>> result = analyze_impact(Path("src/axm_ast"), "analyze_package")
    >>> print(result["score"])
    'HIGH'
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from axm_ast.models.nodes import WorkspaceInfo

from axm_ast.core.analyzer import (
    _module_dotted_name,
    analyze_package,
)
from axm_ast.core.callers import find_callers, find_callers_workspace
from axm_ast.models.nodes import ModuleInfo, PackageInfo

__all__ = [
    "analyze_impact",
    "analyze_impact_workspace",
    "find_definition",
    "find_reexports",
    "map_tests",
    "score_impact",
]


# ─── Definition finder ──────────────────────────────────────────────────────


def find_definition(pkg: PackageInfo, symbol: str) -> dict[str, Any] | None:
    """Locate where a symbol is defined.

    Args:
        pkg: Analyzed package info.
        symbol: Name of the function/class to find.

    Returns:
        Dict with module, line, kind — or None if not found.
    """
    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)

        for fn in mod.functions:
            if fn.name == symbol:
                return {
                    "module": mod_name,
                    "line": fn.line_start,
                    "kind": "function",
                    "signature": fn.signature,
                }

        for cls in mod.classes:
            if cls.name == symbol:
                return {
                    "module": mod_name,
                    "line": cls.line_start,
                    "kind": "class",
                    "name": cls.name,
                }

    return None


# ─── Re-export detection ────────────────────────────────────────────────────


def find_reexports(pkg: PackageInfo, symbol: str) -> list[str]:
    """Find modules that re-export a symbol via __all__ or imports.

    Args:
        pkg: Analyzed package info.
        symbol: Name to search for in exports.

    Returns:
        List of module names that re-export the symbol.
    """
    reexports: list[str] = []

    for mod in pkg.modules:
        mod_name = _module_dotted_name(mod.path, pkg.root)
        if _is_defined_in_module(mod, symbol):
            continue
        if _is_reexported_via_all(mod, symbol):
            reexports.append(mod_name)
        elif _is_reexported_via_import(mod, symbol):
            reexports.append(mod_name)

    return reexports


def _is_defined_in_module(mod: ModuleInfo, symbol: str) -> bool:
    """Check if symbol is defined (not just imported) in a module."""
    return any(fn.name == symbol for fn in mod.functions) or any(
        cls.name == symbol for cls in mod.classes
    )


def _is_reexported_via_all(mod: ModuleInfo, symbol: str) -> bool:
    """Check if symbol appears in module's __all__."""
    return bool(mod.all_exports and symbol in mod.all_exports)


def _is_reexported_via_import(mod: ModuleInfo, symbol: str) -> bool:
    """Check if symbol is imported in the module."""
    return any(imp.names and symbol in imp.names for imp in mod.imports)


# ─── Test file detection ────────────────────────────────────────────────────


def map_tests(symbol: str, project_root: Path) -> list[Path]:
    """Find test files that reference a given symbol.

    Scans ``tests/`` directory for test_*.py files containing
    the symbol name.

    Args:
        symbol: Name to search for in test files.
        project_root: Root of the project.

    Returns:
        List of test file paths that reference the symbol.
    """
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return []

    matching: list[Path] = []
    for test_file in sorted(tests_dir.glob("test_*.py")):
        try:
            content = test_file.read_text(encoding="utf-8")
            if symbol in content:
                matching.append(test_file)
        except OSError:
            continue

    return matching


# ─── Impact scoring ─────────────────────────────────────────────────────────


def score_impact(result: dict[str, Any]) -> str:
    """Score impact as LOW, MEDIUM, or HIGH.

    Args:
        result: Dict with callers, reexports, affected_modules.

    Returns:
        Impact level string.
    """
    caller_count = len(result.get("callers", []))
    reexport_count = len(result.get("reexports", []))
    module_count = len(result.get("affected_modules", []))

    total = caller_count + reexport_count * 2 + module_count

    if total >= 5:
        return "HIGH"
    if total >= 2:
        return "MEDIUM"
    return "LOW"


# ─── Orchestrator ────────────────────────────────────────────────────────────


def analyze_impact(
    path: Path,
    symbol: str,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Full impact analysis for a symbol.

    Combines definition location, callers, re-exports, tests,
    and an impact score.

    Args:
        path: Path to the package directory.
        symbol: Name of the symbol to analyze.
        project_root: Project root (for test detection).

    Returns:
        Complete impact analysis dict.

    Example:
        >>> result = analyze_impact(Path("src/axm_ast"), "analyze_package")
        >>> result["score"]
        'HIGH'
    """
    pkg = analyze_package(path)

    if project_root is None:
        # Infer: if path is inside src/, go up two levels
        if path.parent.name == "src":
            project_root = path.parent.parent
        else:
            project_root = path.parent

    # 1. Where is it defined?
    definition = find_definition(pkg, symbol)

    # 2. Who calls it?
    callers = find_callers(pkg, symbol)

    # 3. Where is it re-exported?
    reexports = find_reexports(pkg, symbol)

    # 4. What tests reference it?
    test_files = map_tests(symbol, project_root)

    # 5. Affected modules (unique)
    affected_modules = list({c.module for c in callers} | set(reexports))

    result = {
        "symbol": symbol,
        "definition": definition,
        "callers": [
            {
                "module": c.module,
                "line": c.line,
                "context": c.context,
                "call_expression": c.call_expression,
            }
            for c in callers
        ],
        "reexports": reexports,
        "affected_modules": sorted(affected_modules),
        "test_files": [str(t.name) for t in test_files],
        "score": "LOW",  # placeholder, computed below
    }

    result["score"] = score_impact(result)
    return result


def _collect_workspace_reexports(
    ws: WorkspaceInfo,
    symbol: str,
) -> list[str]:
    """Collect re-exports of a symbol across all workspace packages."""
    reexports: list[str] = []
    for pkg in ws.packages:
        for mod_reexport in find_reexports(pkg, symbol):
            reexports.append(f"{pkg.name}::{mod_reexport}")
    return reexports


def _collect_workspace_tests(
    ws: WorkspaceInfo,
    symbol: str,
) -> list[str]:
    """Collect test files referencing a symbol across the workspace."""
    test_files: list[str] = []
    for member_dir in ws.root.iterdir():
        if not member_dir.is_dir():
            continue
        for t in map_tests(symbol, member_dir):
            test_files.append(str(t.name))
    return sorted(set(test_files))


def analyze_impact_workspace(
    ws_path: Path,
    symbol: str,
) -> dict[str, Any]:
    """Full impact analysis for a symbol across a workspace.

    Searches all packages for definition, callers, re-exports,
    and test files. Module names include package prefix.

    Args:
        ws_path: Path to workspace root.
        symbol: Name of the symbol to analyze.

    Returns:
        Complete impact analysis dict (workspace-scoped).

    Example:
        >>> result = analyze_impact_workspace(Path("/ws"), "ToolResult")
        >>> result["score"]
        'HIGH'
    """
    from axm_ast.core.workspace import analyze_workspace

    ws = analyze_workspace(ws_path)

    # 1. Where is it defined? Search all packages.
    definition = None
    for pkg in ws.packages:
        defn = find_definition(pkg, symbol)
        if defn is not None:
            defn["package"] = pkg.name
            definition = defn
            break

    # 2. Who calls it? Cross-package.
    callers = find_callers_workspace(ws, symbol)

    # 3. Re-exports and test files.
    reexports = _collect_workspace_reexports(ws, symbol)
    test_files = _collect_workspace_tests(ws, symbol)

    # 4. Build result.
    affected_modules = sorted({c.module for c in callers} | set(reexports))

    result: dict[str, Any] = {
        "symbol": symbol,
        "workspace": ws.name,
        "definition": definition,
        "callers": [
            {
                "module": c.module,
                "line": c.line,
                "context": c.context,
                "call_expression": c.call_expression,
            }
            for c in callers
        ],
        "reexports": reexports,
        "affected_modules": affected_modules,
        "test_files": test_files,
        "score": "LOW",
    }

    result["score"] = score_impact(result)
    return result
