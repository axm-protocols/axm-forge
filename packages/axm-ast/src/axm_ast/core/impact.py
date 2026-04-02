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

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from axm_ast.models.nodes import WorkspaceInfo

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.cache import get_package
from axm_ast.core.callers import find_callers, find_callers_workspace
from axm_ast.core.git_coupling import git_coupled_files
from axm_ast.core.workspace import analyze_workspace
from axm_ast.models.nodes import ModuleInfo, PackageInfo

logger = logging.getLogger(__name__)

__all__ = [
    "analyze_impact",
    "analyze_impact_workspace",
    "find_definition",
    "find_reexports",
    "find_type_refs",
    "map_tests",
    "score_impact",
]


# ─── Helpers ────────────────────────────────────────────────────────────────


def _resolve_module_file(pkg: PackageInfo, mod_name: str) -> Path | None:
    """Resolve a module dotted name to its absolute file path.

    Args:
        pkg: Analyzed package info.
        mod_name: Dotted module name (e.g. ``"core.impact"``).

    Returns:
        Absolute path to the module file, or None if not found.
    """
    for mod in pkg.modules:
        dotted = module_dotted_name(mod.path, pkg.root)
        if dotted == mod_name:
            return mod.path
    return None


# ─── Definition finder ──────────────────────────────────────────────────────


def _split_dotted_symbol(symbol: str) -> tuple[str, str] | None:
    """Split a dotted symbol into (class_name, method_name).

    Returns None for bare (non-dotted) symbols.
    For deeply nested paths like ``Outer.Inner.method``,
    returns ``("Outer", "Inner.method")``.
    """
    if "." not in symbol:
        return None
    parts = symbol.split(".", 1)
    return parts[0], parts[1]


def _find_method_in_class(
    cls: Any,
    method_path: str,
    mod_name: str,
) -> dict[str, Any] | None:
    """Search a class body for a method (supports nested paths).

    Args:
        cls: ClassInfo node from the AST.
        method_path: Method name or nested path (e.g. ``"method"``
            or ``"Inner.method"``).
        mod_name: Dotted module name for the result dict.

    Returns:
        Dict with module, line, kind — or None if not found.
    """
    # Check if this is a nested path (e.g. "Inner.method")
    nested = _split_dotted_symbol(method_path)
    if nested is not None:
        inner_name, rest = nested
        # Search nested classes
        for inner_cls in getattr(cls, "classes", []):
            if inner_cls.name == inner_name:
                return _find_method_in_class(inner_cls, rest, mod_name)
        return None

    # Direct method lookup
    for method in cls.methods:
        if method.name == method_path:
            return {
                "module": mod_name,
                "line": method.line_start,
                "kind": method.kind or "method",
                "signature": method.signature,
            }
    return None


def _find_dotted_definition(
    pkg: PackageInfo,
    class_name: str,
    method_path: str,
) -> dict[str, Any] | None:
    """Resolve a dotted symbol (Class.method) definition."""
    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)
        for cls in mod.classes:
            if cls.name == class_name:
                result = _find_method_in_class(cls, method_path, mod_name)
                if result is not None:
                    return result
    return None


def _find_plain_definition(
    pkg: PackageInfo,
    symbol: str,
) -> dict[str, Any] | None:
    """Resolve a plain (non-dotted) symbol definition."""
    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)
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


def find_definition(pkg: PackageInfo, symbol: str) -> dict[str, Any] | None:
    """Locate where a symbol is defined.

    Supports dotted paths like ``ClassName.method`` to find
    methods within class bodies.  For deeply nested paths like
    ``Outer.Inner.method``, resolution is best-effort.

    Args:
        pkg: Analyzed package info.
        symbol: Name of the function/class to find.  May be
            dotted (e.g. ``"MyClass.my_method"``).

    Returns:
        Dict with module, line, kind — or None if not found.
    """
    dotted = _split_dotted_symbol(symbol)
    if dotted is not None:
        return _find_dotted_definition(pkg, dotted[0], dotted[1])
    return _find_plain_definition(pkg, symbol)


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
        mod_name = module_dotted_name(mod.path, pkg.root)
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


def _find_test_files_by_import(
    module_name: str,
    project_root: Path,
) -> list[Path]:
    """Find test files that import a given module (import-based heuristic).

    Scans ``tests/`` directory for ``test_*.py`` files whose source
    contains an import statement referencing *module_name*.  This is a
    fallback for symbols with no direct callers — the module they live
    in is often imported by test files even when the symbol name itself
    does not appear.

    Only ``tests/`` is scanned (bounded scope).  Non-test files are
    excluded.

    Args:
        module_name: Bare module name (e.g. ``"models"``, not
            ``"mypkg.models"``).
        project_root: Root of the project.

    Returns:
        Sorted list of test file paths that import the module.
    """
    import re

    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return []

    # Match import lines:  from <anything>.module_name import ...
    #                      import <anything>.module_name
    #                      from module_name import ...
    pattern = re.compile(
        rf"(?:from\s+\S*\.?{re.escape(module_name)}\s+import"
        rf"|import\s+\S*\.?{re.escape(module_name)}(?:\s|$))"
    )

    matching: list[Path] = []
    for test_file in sorted(tests_dir.glob("test_*.py")):
        try:
            content = test_file.read_text(encoding="utf-8")
            if pattern.search(content):
                matching.append(test_file)
        except OSError:
            continue

    return matching


# ─── Type reference detection ───────────────────────────────────────────────


def _type_name_pattern(type_name: str) -> re.Pattern[str]:
    """Build a word-boundary regex pattern for a type name.

    Matches ``TypeName`` as a standalone token inside annotation
    strings, including compound types like ``list[TypeName]``,
    ``TypeName | None``, ``Optional[TypeName]``, etc.

    Args:
        type_name: Exact type name to search for.

    Returns:
        Compiled regex pattern.
    """
    return re.compile(rf"(?<![\w.]){re.escape(type_name)}(?![\w.])")


def find_type_refs(
    pkg: PackageInfo,
    type_name: str,
) -> list[dict[str, Any]]:
    """Find functions that reference a type in their signatures.

    Scans all function parameters, return types, and module-level
    variable annotations for occurrences of *type_name* using
    word-boundary matching.

    Handles compound types: ``list[X]``, ``dict[str, X]``,
    ``X | None``, ``Optional[X]``, nested generics, and
    string annotations (``"X"``).

    Args:
        pkg: Analyzed package info.
        type_name: Exact type name to search for (e.g. ``"MyModel"``).

    Returns:
        List of dicts with ``function``, ``module``, ``line``,
        and ``ref_type`` (``"param"``, ``"return"``, or ``"alias"``).
    """
    pattern = _type_name_pattern(type_name)
    refs: list[dict[str, Any]] = []

    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)

        refs.extend(
            _scan_functions_for_type(
                mod.functions,
                mod_name,
                pattern,
            )
        )

        for cls in mod.classes:
            refs.extend(
                _scan_functions_for_type(
                    cls.methods,
                    mod_name,
                    pattern,
                    class_name=cls.name,
                )
            )

        # Module-level type aliases (e.g. ``type Foo = X``).
        for var in mod.variables:
            ann = var.annotation or ""
            val = var.value_repr or ""
            if pattern.search(ann) or pattern.search(val):
                refs.append(
                    {
                        "function": var.name,
                        "module": mod_name,
                        "line": var.line,
                        "ref_type": "alias",
                    }
                )

    return refs


def _match_param_type(fn: Any, pattern: re.Pattern[str]) -> bool:
    """Check whether any parameter annotation matches *pattern*."""
    return any(
        param.annotation and pattern.search(param.annotation) for param in fn.params
    )


def _scan_functions_for_type(
    functions: list[Any],
    mod_name: str,
    pattern: re.Pattern[str],
    *,
    class_name: str | None = None,
) -> list[dict[str, Any]]:
    """Scan a list of functions for type references in signatures."""
    refs: list[dict[str, Any]] = []
    for fn in functions:
        fn_label = f"{class_name}.{fn.name}" if class_name else fn.name
        if _match_param_type(fn, pattern):
            ref_type = "param"
        elif fn.return_type and pattern.search(fn.return_type):
            ref_type = "return"
        else:
            continue
        refs.append(
            {
                "function": fn_label,
                "module": mod_name,
                "line": fn.line_start,
                "ref_type": ref_type,
            }
        )
    return refs


# ─── Impact scoring ─────────────────────────────────────────────────────────


_IMPACT_HIGH_THRESHOLD = 5
_IMPACT_MEDIUM_THRESHOLD = 2


def score_impact(result: dict[str, Any]) -> str:
    """Score impact as LOW, MEDIUM, or HIGH.

    Args:
        result: Dict with callers, reexports, affected_modules,
            and optionally git_coupled and type_refs.

    Returns:
        Impact level string.
    """
    caller_count = len(result.get("callers", []))
    reexport_count = len(result.get("reexports", []))
    module_count = len(result.get("affected_modules", []))
    coupled_count = len(result.get("git_coupled", []))
    type_ref_count = len(result.get("type_refs", []))

    total = (
        caller_count
        + reexport_count * 2
        + module_count
        + coupled_count
        + type_ref_count
    )

    if total >= _IMPACT_HIGH_THRESHOLD:
        return "HIGH"
    if total >= _IMPACT_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


# ─── Orchestrator ────────────────────────────────────────────────────────────


def _resolve_project_root(path: Path, explicit: Path | None) -> Path:
    """Infer project root from package path if not given explicitly."""
    if explicit is not None:
        return explicit
    if path.parent.name == "src":
        return path.parent.parent
    return path.parent


def _add_git_coupling(
    result: dict[str, Any],
    definition: dict[str, Any] | None,
    pkg: PackageInfo,
    project_root: Path,
) -> None:
    """Enrich *result* with git change coupling data."""
    if definition is None:
        return
    mod_name = definition["module"]
    file_abs = _resolve_module_file(pkg, mod_name)
    if file_abs is None:
        return
    try:
        file_rel = file_abs.relative_to(project_root)
    except ValueError:
        return
    result["git_coupled"] = git_coupled_files(str(file_rel), project_root)


def _add_import_based_tests(
    result: dict[str, Any],
    definition: dict[str, Any] | None,
    test_files: list[Path],
    project_root: Path,
) -> None:
    """Enrich *result* with import-based test file heuristic."""
    if test_files or definition is None:
        return
    bare_module = definition["module"].rsplit(".", 1)[-1]
    import_tests = _find_test_files_by_import(bare_module, project_root)
    if import_tests:
        result["test_files_by_import"] = [str(t.name) for t in import_tests]


def _is_symbol_public(pkg: PackageInfo, symbol: str) -> bool:
    """Check if symbol is in any module's ``__all__`` within the package."""
    return any(mod.all_exports and symbol in mod.all_exports for mod in pkg.modules)


def _sibling_imports_symbol(
    sibling_dir: Path,
    source_pkg: str,
    symbol: str,
) -> bool:
    """Check if any Python file in *sibling_dir* imports *symbol* from *source_pkg*."""
    pattern = re.compile(
        rf"\bfrom\s+{re.escape(source_pkg)}\b.*\bimport\b.*\b{re.escape(symbol)}\b"
    )
    for py_file in sibling_dir.rglob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue
        if pattern.search(content):
            return True
    return False


def _find_cross_package_impact(
    path: Path,
    pkg: PackageInfo,
    symbol: str,
    project_root: Path,
) -> list[str]:
    """Find sibling packages that import a public symbol.

    Only considers symbols exported via ``__all__`` in the source
    package.  Scans each sibling directory exactly once (no recursion
    into transitive dependents), so circular dependencies cannot cause
    infinite loops.
    """
    if not _is_symbol_public(pkg, symbol):
        return []

    pkg_name = path.name
    cross_impact: list[str] = []

    for sibling in sorted(project_root.iterdir()):
        if not sibling.is_dir() or sibling.resolve() == path.resolve():
            continue
        if _sibling_imports_symbol(sibling, pkg_name, symbol):
            cross_impact.append(sibling.name)

    return cross_impact


def _is_test_module(module: str) -> bool:
    """Check if a module name belongs to a test file.

    Matches modules starting with ``tests.`` or ``test_``, and
    also matches dotted paths where any segment starts with ``test_``.
    """
    parts = module.split(".")
    return any(p.startswith("test_") or p == "tests" for p in parts)


def _resolve_effective_filter(
    test_filter: str | None,
    exclude_tests: bool,
) -> str | None:
    """Resolve effective test filter mode from dual parameters."""
    if test_filter is not None and exclude_tests:
        import warnings

        warnings.warn(
            "Both exclude_tests and test_filter set; test_filter takes precedence",
            stacklevel=2,
        )
    if test_filter is not None:
        return test_filter
    return "none" if exclude_tests else None


def _apply_test_filter(result: dict[str, Any], effective: str | None) -> None:
    """Filter test callers/type_refs from result based on effective filter."""
    if effective == "none":
        result["callers"] = [
            c for c in result["callers"] if not _is_test_module(c["module"])
        ]
        result["type_refs"] = [
            r for r in result["type_refs"] if not _is_test_module(r["module"])
        ]
    elif effective == "related":
        result["type_refs"] = [
            r for r in result["type_refs"] if not _is_test_module(r["module"])
        ]


def analyze_impact(
    path: Path,
    symbol: str,
    *,
    project_root: Path | None = None,
    exclude_tests: bool = False,
    test_filter: str | None = None,
) -> dict[str, Any]:
    """Full impact analysis for a symbol.

    Combines definition location, callers, re-exports, tests,
    and an impact score.

    Args:
        path: Path to the package directory.
        symbol: Name of the symbol to analyze.
        project_root: Project root (for test detection).
        exclude_tests: If True, filter test callers and test
            type_refs from the output.  The impact score is still
            computed on the full (unfiltered) caller set.
        test_filter: Filter mode for test callers.  ``"none"``
            excludes all test callers (same as *exclude_tests*),
            ``"all"`` keeps everything, ``"related"`` keeps only
            direct test callers.  Takes precedence over
            *exclude_tests* when both are set.

    Returns:
        Complete impact analysis dict.

    Example:
        >>> result = analyze_impact(Path("src/axm_ast"), "analyze_package")
        >>> result["score"]
        'HIGH'
    """
    pkg = get_package(path)
    root = _resolve_project_root(path, project_root)

    # For dotted symbols (Class.method), resolve definition with full
    # path but search callers/tests by the bare method name — that is
    # what appears in actual source code (self.method(), obj.method()).
    dotted = _split_dotted_symbol(symbol)
    lookup_name = dotted[1].split(".")[-1] if dotted else symbol

    definition = find_definition(pkg, symbol)
    callers = find_callers(pkg, lookup_name)
    reexports = find_reexports(pkg, lookup_name)
    test_files = map_tests(lookup_name, root)

    type_refs = find_type_refs(pkg, lookup_name)
    type_ref_modules = {r["module"] for r in type_refs}
    affected_modules = list(
        {c.module for c in callers} | set(reexports) | type_ref_modules
    )

    result: dict[str, Any] = {
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
        "type_refs": type_refs,
        "reexports": reexports,
        "affected_modules": sorted(affected_modules),
        "test_files": [str(t.name) for t in test_files],
        "git_coupled": [],
        "score": "LOW",
    }

    _add_git_coupling(result, definition, pkg, root)
    _add_import_based_tests(result, definition, test_files, root)
    if root is not None:
        result["cross_package_impact"] = _find_cross_package_impact(
            path,
            pkg,
            lookup_name,
            root,
        )
    # Score on the FULL caller set before any filtering.
    result["score"] = score_impact(result)

    effective = _resolve_effective_filter(test_filter, exclude_tests)
    _apply_test_filter(result, effective)

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


def _add_workspace_git_coupling(
    result: dict[str, Any],
    definition: dict[str, Any] | None,
    ws: WorkspaceInfo,
    ws_path: Path,
) -> None:
    """Enrich *result* with git coupling from the workspace."""
    if definition is None:
        return
    mod_name = definition["module"]
    pkg_name = definition.get("package", "")
    for pkg in ws.packages:
        if pkg.name == pkg_name:
            file_abs = _resolve_module_file(pkg, mod_name)
            if file_abs is not None:
                try:
                    file_rel = file_abs.relative_to(ws_path)
                except ValueError:
                    file_rel = None
                if file_rel is not None:
                    result["git_coupled"] = git_coupled_files(str(file_rel), ws_path)
            break


def _find_workspace_definition(
    ws: Any,
    symbol: str,
) -> dict[str, Any] | None:
    """Search all workspace packages for *symbol*'s definition."""
    for pkg in ws.packages:
        defn = find_definition(pkg, symbol)
        if defn is not None:
            defn["package"] = pkg.name
            return defn
    return None


def _resolve_effective_test_filter(
    test_filter: str | None,
    exclude_tests: bool,
) -> str | None:
    """Return the effective test-filter mode, warning on conflicts."""
    if test_filter is not None and exclude_tests:
        import warnings

        warnings.warn(
            "Both exclude_tests and test_filter set; test_filter takes precedence",
            stacklevel=2,
        )
    if test_filter is not None:
        return test_filter
    return "none" if exclude_tests else None


def _apply_caller_test_filter(
    result: dict[str, Any],
    effective: str | None,
) -> None:
    """Filter test callers from *result* in place."""
    if effective == "none":
        result["callers"] = [
            c for c in result["callers"] if not _is_test_module(c["module"])
        ]


def analyze_impact_workspace(
    ws_path: Path,
    symbol: str,
    *,
    exclude_tests: bool = False,
    test_filter: str | None = None,
) -> dict[str, Any]:
    """Full impact analysis for a symbol across a workspace.

    Searches all packages for definition, callers, re-exports,
    and test files. Module names include package prefix.

    Args:
        ws_path: Path to workspace root.
        symbol: Name of the symbol to analyze.
        exclude_tests: If True, filter test callers from the
            output.  Score is computed on the full caller set.
        test_filter: Filter mode for test callers.  ``"none"``
            excludes all, ``"all"`` keeps everything, ``"related"``
            keeps only direct test callers.  Takes precedence
            over *exclude_tests* when both are set.

    Returns:
        Complete impact analysis dict (workspace-scoped).

    Example:
        >>> result = analyze_impact_workspace(Path("/ws"), "ToolResult")
        >>> result["score"]
        'HIGH'
    """
    ws = analyze_workspace(ws_path)

    # For dotted symbols, definition uses full path but lookups
    # use the bare method name (what appears in source code).
    dotted = _split_dotted_symbol(symbol)
    lookup_name = dotted[1].split(".")[-1] if dotted else symbol

    callers = find_callers_workspace(ws, lookup_name)
    reexports = _collect_workspace_reexports(ws, lookup_name)
    test_files = _collect_workspace_tests(ws, lookup_name)
    affected_modules = sorted({c.module for c in callers} | set(reexports))

    result: dict[str, Any] = {
        "symbol": symbol,
        "workspace": ws.name,
        "definition": _find_workspace_definition(ws, symbol),
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
        "git_coupled": [],
        "score": "LOW",
    }

    _add_workspace_git_coupling(result, result["definition"], ws, ws_path)
    result["score"] = score_impact(result)

    effective = _resolve_effective_test_filter(test_filter, exclude_tests)
    _apply_caller_test_filter(result, effective)

    return result
