"""axm-ast — AST introspection CLI for AI agents, powered by tree-sitter.

This package provides deterministic, fast parsing of Python libraries
to extract structured information (functions, classes, imports, docstrings,
call graphs) at multiple granularity levels.

Example:
    >>> from axm_ast import analyze_package
    >>> from pathlib import Path
    >>>
    >>> pkg = analyze_package(Path("src/mylib"))
    >>> [m.path.name for m in pkg.modules]
    ['__init__.py', 'core.py', 'utils.py']
"""

from axm_ast._version import __version__
from axm_ast.core.analyzer import analyze_package, search_symbols
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
    ParameterInfo,
    VariableInfo,
)

__all__ = [
    "ClassInfo",
    "FunctionInfo",
    "FunctionKind",
    "ImportInfo",
    "ModuleInfo",
    "PackageInfo",
    "ParameterInfo",
    "VariableInfo",
    "__version__",
    "analyze_package",
    "search_symbols",
]
