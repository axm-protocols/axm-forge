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
    `['__init__.py', 'core.py', 'utils.py']`
"""

from axm_ast._version import __version__
from axm_ast.core.analyzer import analyze_package, search_symbols
from axm_ast.core.callers import find_callers
from axm_ast.core.dead_code import DeadSymbol, find_dead_code
from axm_ast.core.flows import FlowStep, trace_flow
from axm_ast.core.structural_diff import StructuralDiffResult, structural_diff
from axm_ast.core.workspace import analyze_workspace, build_workspace_module_graph
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    PackageInfo,
    ParameterInfo,
    VariableInfo,
    WorkspaceInfo,
)

__all__ = [
    "CallSite",
    "ClassInfo",
    "DeadSymbol",
    "FlowStep",
    "FunctionInfo",
    "FunctionKind",
    "ImportInfo",
    "ModuleInfo",
    "PackageInfo",
    "ParameterInfo",
    "StructuralDiffResult",
    "VariableInfo",
    "WorkspaceInfo",
    "__version__",
    "analyze_package",
    "analyze_workspace",
    "build_workspace_module_graph",
    "find_callers",
    "find_dead_code",
    "search_symbols",
    "structural_diff",
    "trace_flow",
]
