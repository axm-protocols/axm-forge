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

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_ast.models.nodes import (
        ClassInfo,
        FunctionInfo,
        ModuleInfo,
        PackageInfo,
    )

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
    - ``__main__`` guard functions
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

    # Property / abstractmethod / classmethod / staticmethod.
    if fn.kind in {
        FunctionKind.PROPERTY,
        FunctionKind.ABSTRACT,
    }:
        return True

    # Any decorator at all → likely an entry point / framework hook.
    if fn.decorators:
        return True

    # Methods on a Protocol class → structural typing stubs.
    if parent_class is not None and _is_protocol_class(parent_class):
        return True

    return False


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
    """Check if a method overrides a *called* base class method.

    Returns ``True`` if the base method has callers (override is NOT dead).
    Returns ``False`` if the base method is also dead or not found.
    """
    from axm_ast.core.callers import find_callers

    for base_name in cls.bases:
        # Find the base class in the package.
        for mod in pkg.modules:
            for other_cls in mod.classes:
                if other_cls.name == base_name:
                    # Check if the base class has this method.
                    for base_method in other_cls.methods:
                        if base_method.name == method_name:
                            # Base has the method — check if it's called.
                            callers = find_callers(pkg, method_name)
                            return len(callers) > 0
    return False


# ─── Entry-point exemption ───────────────────────────────────────────────────


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
    pyproject = pkg_root / "pyproject.toml"
    if not pyproject.exists():
        return set()

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return set()

    entry_points = data.get("project", {}).get("entry-points", {})
    symbols: set[str] = set()

    for _group, entries in entry_points.items():
        if not isinstance(entries, dict):
            continue
        for _name, spec in entries.items():
            if not isinstance(spec, str):
                continue
            # Format: "module.path:ClassName" or "module.path:func"
            if ":" in spec:
                symbol_part = spec.split(":", 1)[1]
                symbols.add(symbol_part)
                # AXM convention: entry point classes have .execute()
                symbols.add(f"{symbol_part}.execute")

    return symbols


def _is_in_tests_dir(mod_path: Path) -> bool:
    """Check if a module is inside a ``tests/`` directory."""
    return "tests" in mod_path.parts


# ─── Core detection ──────────────────────────────────────────────────────────


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

    Args:
        pkg: Analyzed package from ``analyze_package()``.
        include_tests: If ``True``, also scan modules inside ``tests/``
            directories. Defaults to ``False``.

    Returns:
        List of dead symbols, sorted by module path then line number.
    """
    from axm_ast.core.callers import extract_references, find_callers

    dead: list[DeadSymbol] = []

    # Collect data-structure references across all modules.
    all_refs: set[str] = set()
    for mod in pkg.modules:
        all_refs |= extract_references(mod)

    # Load entry-point symbols from pyproject.toml.
    entry_point_symbols = _load_entry_point_symbols(pkg.root)

    for mod in pkg.modules:
        mod_path = str(mod.path)

        # Skip test files — they are consumers, not targets.
        path_name = mod.path.name
        if path_name.startswith("test_") or path_name == "conftest.py":
            continue

        # Skip modules inside tests/ directory unless opted in.
        if not include_tests and _is_in_tests_dir(mod.path):
            continue

        # ── Top-level functions ──────────────────────────────────────
        for fn in mod.functions:
            if _is_exempt_function(fn, mod):
                continue

            # Skip if referenced in a data structure (dict dispatch, etc.).
            if fn.name in all_refs:
                continue

            callers = find_callers(pkg, fn.name)
            if not callers:
                dead.append(
                    DeadSymbol(
                        name=fn.name,
                        module_path=mod_path,
                        line=fn.line_start,
                        kind="function",
                    )
                )

        # ── Classes ──────────────────────────────────────────────────
        for cls in mod.classes:
            # Skip entry-point classes.
            if cls.name in entry_point_symbols:
                continue

            cls_callers = find_callers(pkg, cls.name)
            cls_is_dead = not cls_callers and not _is_exempt_class(cls, mod)

            if cls_is_dead:
                dead.append(
                    DeadSymbol(
                        name=cls.name,
                        module_path=mod_path,
                        line=cls.line_start,
                        kind="class",
                    )
                )

            # Check methods regardless of class status.
            for method in cls.methods:
                if _is_exempt_function(method, mod, parent_class=cls):
                    continue

                # Skip entry-point methods.
                qualified = f"{cls.name}.{method.name}"
                if qualified in entry_point_symbols:
                    continue

                # Skip if referenced in a data structure.
                if method.name in all_refs:
                    continue

                method_callers = find_callers(pkg, method.name)
                if not method_callers:
                    # Check override chain before flagging.
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

    dead.sort(key=lambda d: (d.module_path, d.line))
    return dead


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
