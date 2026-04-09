"""Dead code detection via AST caller analysis.

Enumerates all symbols in a package and flags those with zero callers
after applying smart exemptions (dunders, tests, decorators, protocols,
overrides, ``__all__`` exports).

Example::

    >>> from axm_ast.core.analyzer import analyze_package
    >>> from axm_ast.core.dead_code import find_dead_code, format_dead_code
    >>> pkg = analyze_package(Path("src/mylib"))
    >>> dead = find_dead_code(pkg)
    >>> print(format_dead_code(dead))
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from axm_ast.models.nodes import (
        ClassInfo,
        FunctionInfo,
        ModuleInfo,
        PackageInfo,
    )

logger = logging.getLogger(__name__)

__all__ = ["DeadSymbol", "find_dead_code", "format_dead_code"]


# ─── Result model ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DeadSymbol:
    """An unreferenced symbol detected by dead code analysis."""

    name: str
    module_path: str
    line: int
    kind: str  # "function", "method", "class"


# ─── Exemptions ──────────────────────────────────────────────────────────────

# Dunder methods that always have implicit callers via the data model.
_EXEMPT_DUNDERS = frozenset(
    {
        "__init__",
        "__new__",
        "__del__",
        "__repr__",
        "__str__",
        "__bytes__",
        "__format__",
        "__hash__",
        "__bool__",
        "__len__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__iter__",
        "__next__",
        "__contains__",
        "__enter__",
        "__exit__",
        "__aenter__",
        "__aexit__",
        "__call__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__add__",
        "__radd__",
        "__sub__",
        "__mul__",
        "__truediv__",
        "__floordiv__",
        "__mod__",
        "__pow__",
        "__and__",
        "__or__",
        "__xor__",
        "__neg__",
        "__pos__",
        "__abs__",
        "__invert__",
        "__int__",
        "__float__",
        "__complex__",
        "__index__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__get__",
        "__set__",
        "__delete__",
        "__init_subclass__",
        "__class_getitem__",
        "__post_init__",
        "__set_name__",
        "__missing__",
        "__reduce__",
        "__reduce_ex__",
        "__copy__",
        "__deepcopy__",
        "__sizeof__",
        "__subclasshook__",
        "__fspath__",
        "__await__",
        "__aiter__",
        "__anext__",
    }
)

# Decorator names that mark entry points (never dead).
_ENTRY_POINT_DECORATORS = frozenset(
    {
        "property",
        "abstractmethod",
        "staticmethod",
        "classmethod",
        "overload",
        "override",
        "final",
        "cached_property",
        "validator",
        "field_validator",
        "model_validator",
        "root_validator",
    }
)


def _is_exempt_function(
    fn: FunctionInfo,
    mod: ModuleInfo,
    *,
    parent_class: ClassInfo | None = None,
) -> bool:
    """Check whether a function/method should be exempt from dead code flags.

    Exempts:
    - Dunder methods (``__repr__``, ``__init__``, etc.)
    - Test functions (``test_*``)
    - ``__all__``-exported symbols
    - Decorated functions (entry point heuristic)
    - ``@property``, ``@abstractmethod`` (via FunctionKind)
    - Methods on Protocol classes
    """
    from axm_ast.models.nodes import FunctionKind

    name = fn.name

    # Dunder methods — always implicitly called by the runtime.
    if name.startswith("__") and name.endswith("__"):
        return True

    # Test functions — by convention never "dead".
    if name.startswith("test_"):
        return True

    # Exported via __all__.
    if mod.all_exports is not None and name in mod.all_exports:
        return True

    # Property / abstractmethod, or any decorator at all.
    if fn.kind in {FunctionKind.PROPERTY, FunctionKind.ABSTRACT} or fn.decorators:
        return True

    # Methods on a Protocol class → structural typing stubs.
    return parent_class is not None and _is_protocol_class(parent_class)


def _is_exempt_class(cls: ClassInfo, mod: ModuleInfo) -> bool:
    """Check whether a class should be exempt from dead code flags.

    Exempts:
    - ``__all__``-exported classes
    - Decorated classes (entry points, e.g. ``@dataclass``)
    - Protocol classes (structural typing stubs)
    - Exception classes (always raised, rarely called directly)
    """
    if mod.all_exports is not None and cls.name in mod.all_exports:
        return True

    if cls.decorators:
        return True

    if _is_protocol_class(cls):
        return True

    # Exception subclasses: BaseException, Exception, *Error, *Warning
    _exception_bases = {"BaseException", "Exception"}
    for base in cls.bases:
        if base in _exception_bases or base.endswith(("Error", "Warning")):
            return True

    return False


def _is_protocol_class(cls: ClassInfo) -> bool:
    """Check if a class inherits from Protocol."""
    return "Protocol" in cls.bases


def _check_override(
    method_name: str,
    cls: ClassInfo,
    pkg: PackageInfo,
) -> bool:
    """Check if a method overrides a base class method that is alive.

    Searches the package for base classes of *cls* and checks whether
    *method_name* exists on any of them. If the base method has callers,
    the override is considered live. When a base class is external
    (stdlib or third-party), the override is presumed live unless the
    method is single-underscore private.

    Args:
        method_name: Name of the method to check.
        cls: Class that defines the potential override.
        pkg: Analyzed package used for base-class and caller lookup.

    Returns:
        ``True`` if the override is live (has callers or overrides an
        external base); ``False`` otherwise.
    """
    from axm_ast.core.callers import find_callers

    found_bases: set[str] = set()
    for base_name in cls.bases:
        # Find the base class in the package.
        for mod in pkg.modules:
            for other_cls in mod.classes:
                if other_cls.name == base_name:
                    found_bases.add(base_name)
                    # Check if the base class has this method.
                    for base_method in other_cls.methods:
                        if base_method.name == method_name:
                            # Base has the method — check if it's called.
                            callers = find_callers(pkg, method_name)
                            return len(callers) > 0

    # Bases not found in package are external (stdlib/third-party).
    # Methods overriding external bases are presumed live, unless private.
    external_bases = set(cls.bases) - found_bases
    if external_bases:
        is_private = method_name.startswith("_") and not method_name.startswith("__")
        if not is_private:
            return True

    return False


# ─── Entry-point exemption ───────────────────────────────────────────────────


def _find_pyproject_toml(pkg_root: Path) -> Path | None:
    """Walk up from *pkg_root* (max 4 levels) to find ``pyproject.toml``."""
    search = pkg_root
    for _ in range(4):
        candidate = search / "pyproject.toml"
        if candidate.exists():
            return candidate
        if search.parent == search:
            break
        search = search.parent
    return None


def _collect_flat_specs(
    project: dict[str, object],
    key: str,
    specs: list[str],
) -> None:
    """Collect string values from a flat dict section of project config."""
    section_data = project.get(key, {})
    if isinstance(section_data, dict):
        for spec in section_data.values():
            if isinstance(spec, str):
                specs.append(spec)


def _extract_entry_point_specs(
    project: dict[str, object],
) -> list[str]:
    """Collect all entry-point spec strings from a parsed project table."""
    specs: list[str] = []
    _collect_flat_specs(project, "scripts", specs)
    _collect_flat_specs(project, "gui-scripts", specs)
    ep_data = project.get("entry-points", {})
    if isinstance(ep_data, dict):
        for entries in ep_data.values():
            _collect_flat_specs({"_": entries}, "_", specs)
    return specs


def _load_entry_point_symbols(pkg_root: Path) -> set[str]:
    """Parse ``pyproject.toml`` entry-points to find registered symbols.

    Scans ``[project.entry-points]`` for symbol paths like
    ``"module.path:ClassName"`` and returns the set of class names
    (and their ``.execute`` method, the AXM convention).

    Args:
        pkg_root: Root directory of the package (contains ``pyproject.toml``).

    Returns:
        Set of symbol names that are registered entry points.
    """
    pyproject = _find_pyproject_toml(pkg_root)
    if pyproject is None:
        return set()

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return set()

    project = data.get("project", {})
    symbols: set[str] = set()
    for spec in _extract_entry_point_specs(project):
        if ":" in spec:
            symbol_part = spec.split(":", 1)[1]
            symbols.add(symbol_part)
            symbols.add(f"{symbol_part}.execute")
    return symbols


def _is_in_tests_dir(mod_path: Path) -> bool:
    """Check if a module is inside a ``tests/`` directory."""
    return "tests" in mod_path.parts


def _extract_lazy_imports(mod: ModuleInfo) -> set[str]:
    """Extract symbol names from imports inside function bodies.

    Parses the module source with tree-sitter and finds
    ``from ... import X`` statements that appear inside function
    definitions (lazy imports).

    Args:
        mod: Parsed module info (with path to source).

    Returns:
        Set of imported symbol names.
    """
    from axm_ast.core.parser import parse_source

    try:
        source = mod.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()

    tree = parse_source(source)
    refs: set[str] = set()
    _visit_lazy_imports(tree.root_node, refs, depth=0)
    return refs


def _visit_lazy_imports(
    node: object,
    refs: set[str],
    *,
    depth: int,
) -> None:
    """Recursively find import statements inside function bodies."""
    node_type = getattr(node, "type", "")
    children = getattr(node, "children", None) or []

    if node_type in ("function_definition", "decorated_definition"):
        depth += 1

    # Collect imports that are NOT at module level.
    if depth > 0 and node_type == "import_from_statement":
        _collect_import_names(children, refs)

    for child in children:
        _visit_lazy_imports(child, refs, depth=depth)


def _node_identifier_text(node: object) -> str | None:
    """Extract text from an identifier node, or ``None``."""
    if getattr(node, "type", "") != "identifier":
        return None
    text = getattr(node, "text", b"")
    if isinstance(text, bytes):
        return text.decode("utf-8", errors="replace")
    return None


def _collect_import_names(children: list[object], refs: set[str]) -> None:
    """Collect imported symbol names from an ``import_from_statement``."""
    for child in children:
        child_type = getattr(child, "type", "")
        if child_type == "dotted_name":
            continue  # module path, not the imported name
        if child_type == "aliased_import":
            alias_children = getattr(child, "children", None) or []
            for ac in alias_children:
                name = _node_identifier_text(ac)
                if name is not None:
                    refs.add(name)
                    break  # first identifier is the original name
        elif child_type == "identifier":
            name = _node_identifier_text(child)
            if name is not None:
                refs.add(name)


def _find_tests_dir(pkg_root: Path) -> Path | None:
    """Discover a sibling ``tests/`` directory relative to package root.

    Searches upward from *pkg_root* (max 3 levels) for a sibling
    ``tests/`` directory.

    Args:
        pkg_root: Root of the analyzed package (e.g. ``src/mypkg/``).

    Returns:
        Path to the tests directory, or ``None`` if not found.
    """
    search = pkg_root
    for _ in range(3):
        parent = search.parent
        if parent == search:
            break
        candidate = parent / "tests"
        if candidate.is_dir():
            return candidate
        search = parent
    return None


# ─── Core detection ──────────────────────────────────────────────────────────


class _ScanContext(NamedTuple):
    """Bundled scan state passed to _scan_functions/_scan_classes/_scan_methods."""

    entry_points: set[str]
    all_refs: set[str]
    extra_pkg: PackageInfo | None


def _scan_functions(
    mod: ModuleInfo,
    pkg: PackageInfo,
    ctx: _ScanContext,
) -> list[DeadSymbol]:
    """Scan top-level functions in *mod* and return dead symbols."""
    from axm_ast.core.callers import find_callers

    dead: list[DeadSymbol] = []
    mod_path = str(mod.path)
    for fn in mod.functions:
        if _is_exempt_function(fn, mod):
            continue
        if fn.name in ctx.entry_points or fn.name in ctx.all_refs:
            continue
        if find_callers(pkg, fn.name):
            continue
        if ctx.extra_pkg is not None and find_callers(ctx.extra_pkg, fn.name):
            continue
        dead.append(
            DeadSymbol(
                name=fn.name,
                module_path=mod_path,
                line=fn.line_start,
                kind="function",
            )
        )
    return dead


def _collect_base_class_names(pkg: PackageInfo) -> set[str]:
    """Collect all class names used as base classes across the package."""
    bases: set[str] = set()
    for mod in pkg.modules:
        for cls in mod.classes:
            bases.update(cls.bases)
    return bases


def _has_intra_module_refs(
    cls_name: str,
    cls_line: int,
    mod: ModuleInfo,
) -> bool:
    """Check if *cls_name* is referenced within *mod* outside its definition.

    Scans the module's tree-sitter AST for ``identifier`` nodes matching
    *cls_name* that are NOT on the class definition line.  This catches
    attribute access (``ClassName.ATTR``), type annotations
    (``x: ClassName``), and bare-name assignments (``Alias = ClassName``).
    """
    from axm_ast.core.parser import parse_source

    source = mod.path.read_text(encoding="utf-8")
    tree = parse_source(source)

    stack: list[object] = [tree.root_node]
    while stack:
        node = stack.pop()
        if getattr(node, "type", "") == "identifier":
            text = getattr(node, "text", b"")
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            if text == cls_name:
                # Exclude the class definition line itself.
                start_row = getattr(node, "start_point", (0,))[0]
                if start_row != cls_line - 1:  # tree-sitter is 0-based
                    return True
        stack.extend(getattr(node, "children", []))
    return False


def _scan_classes(
    mod: ModuleInfo,
    pkg: PackageInfo,
    ctx: _ScanContext,
) -> list[DeadSymbol]:
    """Scan classes and their methods in *mod* and return dead symbols."""
    from axm_ast.core.callers import find_callers

    all_bases = _collect_base_class_names(pkg)

    dead: list[DeadSymbol] = []
    mod_path = str(mod.path)
    for cls in mod.classes:
        if (
            cls.name in ctx.entry_points
            or cls.name in all_bases
            or cls.name in ctx.all_refs
        ):
            continue
        has_callers = bool(find_callers(pkg, cls.name))
        if not has_callers and ctx.extra_pkg is not None:
            has_callers = bool(find_callers(ctx.extra_pkg, cls.name))
        if (
            not has_callers
            and not _is_exempt_class(cls, mod)
            and not _has_intra_module_refs(cls.name, cls.line_start, mod)
        ):
            dead.append(
                DeadSymbol(
                    name=cls.name,
                    module_path=mod_path,
                    line=cls.line_start,
                    kind="class",
                )
            )
        dead.extend(_scan_methods(cls, mod, pkg, ctx))
    return dead


def _scan_methods(
    cls: ClassInfo,
    mod: ModuleInfo,
    pkg: PackageInfo,
    ctx: _ScanContext,
) -> list[DeadSymbol]:
    """Scan methods of *cls* and return those that appear dead.

    Iterates over all methods, skipping exempt ones, entry-point
    registered ones, and those with callers. Methods that override a
    live base-class method are also kept alive.

    Args:
        cls: Class whose methods are scanned.
        mod: Module containing *cls*.
        pkg: Analyzed package for caller lookup.
        ctx: Shared scan context (entry points, references, test package).

    Returns:
        List of dead method symbols found on *cls*.
    """
    from axm_ast.core.callers import find_callers

    dead: list[DeadSymbol] = []
    mod_path = str(mod.path)
    for method in cls.methods:
        if _is_exempt_function(method, mod, parent_class=cls):
            continue
        qualified = f"{cls.name}.{method.name}"
        if qualified in ctx.entry_points or method.name in ctx.all_refs:
            continue
        has_callers = bool(find_callers(pkg, method.name))
        if not has_callers and ctx.extra_pkg is not None:
            has_callers = bool(find_callers(ctx.extra_pkg, method.name))
        if not has_callers:
            if _check_override(method.name, cls, pkg):
                continue
            dead.append(
                DeadSymbol(
                    name=qualified,
                    module_path=mod_path,
                    line=method.line_start,
                    kind="method",
                )
            )
    return dead


def _gather_all_refs(
    pkg: PackageInfo,
    test_pkg: PackageInfo | None,
) -> set[str]:
    """Collect data-structure references and lazy imports from all modules.

    Merges references from both the source package and an optional
    sibling test package.

    Args:
        pkg: Analyzed source package.
        test_pkg: Optional analyzed test package.

    Returns:
        Set of all referenced symbol names.
    """
    from axm_ast.core.callers import extract_references

    all_refs: set[str] = set()
    for mod in pkg.modules:
        all_refs |= extract_references(mod)
        all_refs |= _extract_lazy_imports(mod)
    if test_pkg is not None:
        for mod in test_pkg.modules:
            all_refs |= extract_references(mod)
            all_refs |= _extract_lazy_imports(mod)
    return all_refs


def find_dead_code(
    pkg: PackageInfo,
    *,
    include_tests: bool = False,
) -> list[DeadSymbol]:
    """Detect unreferenced symbols across a package.

    Algorithm:
        1. Enumerate all functions and classes across all modules.
        2. For each symbol, check if it has any callers or references.
        3. Apply exemptions (dunders, tests, exports, decorators,
           entry points, etc.).
        4. For methods, check override chains.
        5. Also scan a sibling ``tests/`` directory for callers.
        6. Detect lazy imports inside function bodies.

    Args:
        pkg: Analyzed package from ``analyze_package()``.
        include_tests: If ``True``, also scan modules inside ``tests/``
            directories. Defaults to ``False``.

    Returns:
        List of dead symbols, sorted by module path then line number.
    """
    dead: list[DeadSymbol] = []

    test_pkg = _load_test_package(pkg.root)
    all_refs = _gather_all_refs(pkg, test_pkg)

    entry_points = _load_entry_point_symbols(pkg.root)

    # Also exempt framework-detected entry points (decorators, test_, __main__).
    from axm_ast.core.flows import find_entry_points

    for ep in find_entry_points(pkg):
        entry_points.add(ep.name)

    ctx = _ScanContext(
        entry_points=entry_points,
        all_refs=all_refs,
        extra_pkg=test_pkg,
    )

    for mod in pkg.modules:
        # Skip test files — they are consumers, not targets.
        path_name = mod.path.name
        if path_name.startswith("test_") or path_name == "conftest.py":
            continue
        if not include_tests and _is_in_tests_dir(mod.path):
            continue

        dead.extend(_scan_functions(mod, pkg, ctx))
        dead.extend(_scan_classes(mod, pkg, ctx))

    dead.sort(key=lambda d: (d.module_path, d.line))
    return dead


def _load_test_package(pkg_root: Path) -> PackageInfo | None:
    """Discover and analyze a sibling ``tests/`` directory.

    Args:
        pkg_root: Root of the analyzed source package.

    Returns:
        PackageInfo for the tests directory, or ``None`` if not found.
    """
    from axm_ast.core.analyzer import analyze_package

    tests_dir = _find_tests_dir(pkg_root)
    if tests_dir is None:
        return None
    try:
        return analyze_package(tests_dir)
    except (ValueError, OSError):
        return None


# ─── Formatting ──────────────────────────────────────────────────────────────


def format_dead_code(results: list[DeadSymbol]) -> str:
    """Format dead code results as human-readable grouped output.

    Groups results by module path, then lists each dead symbol
    with its line number and kind.

    Args:
        results: List of dead symbols from ``find_dead_code()``.

    Returns:
        Formatted string suitable for terminal display.
    """
    if not results:
        return "✅ No dead code detected."

    # Group by module.
    groups: dict[str, list[DeadSymbol]] = {}
    for sym in results:
        groups.setdefault(sym.module_path, []).append(sym)

    parts: list[str] = [f"💀 {len(results)} dead symbol(s) found:\n"]

    for mod_path, symbols in groups.items():
        parts.append(f"  📄 {mod_path}")
        for sym in symbols:
            parts.append(f"    L{sym.line:>4d}  {sym.kind:<10s}  {sym.name}")
        parts.append("")

    return "\n".join(parts)
