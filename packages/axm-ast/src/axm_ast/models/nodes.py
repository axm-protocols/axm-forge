"""Pydantic models for AST node representations.

Each model captures the structural information that AI agents need
to understand a Python library without reading its full source code.
"""

from __future__ import annotations

import enum
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class FunctionKind(enum.StrEnum):
    """Classification of a callable based on its decorators."""

    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    CLASSMETHOD = "classmethod"
    STATICMETHOD = "staticmethod"
    ABSTRACT = "abstract"


class SymbolKind(enum.StrEnum):
    """Filter enum for symbol search — superset of FunctionKind + class.

    Used by ``search_symbols`` and the ``ast_search`` MCP tool to let
    callers filter results by symbol type.
    """

    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    CLASSMETHOD = "classmethod"
    STATICMETHOD = "staticmethod"
    ABSTRACT = "abstract"
    CLASS = "class"
    VARIABLE = "variable"


def _strip_annotated(annotation: str) -> str:
    """Strip ``Annotated[T, ...]`` wrapper, returning just ``T``."""
    normalized = " ".join(annotation.split())
    if not normalized.startswith("Annotated["):
        return annotation
    # Find T by counting bracket depth after the opening '['
    start = len("Annotated[")
    depth = 1
    for i in range(start, len(normalized)):
        ch = normalized[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                # No comma found — single-arg Annotated[T]
                return normalized[start:i].strip()
        elif ch == "," and depth == 1:
            return normalized[start:i].strip()
    return annotation


class ParameterInfo(BaseModel):
    """A single function/method parameter.

    Example:
        >>> p = ParameterInfo(name="path", annotation="Path", default="None")
        >>> p.name
        'path'
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Parameter name")
    annotation: str | None = Field(
        default=None, description="Type annotation as string"
    )
    default: str | None = Field(default=None, description="Default value as string")


class FunctionInfo(BaseModel):
    """Metadata for a single function or method.

    Example:
        >>> fn = FunctionInfo(name="parse", line_start=10, line_end=25)
        >>> fn.is_public
        True
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Function/method name")
    params: list[ParameterInfo] = Field(default_factory=list, description="Parameters")
    return_type: str | None = Field(default=None, description="Return type annotation")
    docstring: str | None = Field(default=None, description="Docstring content")
    decorators: list[str] = Field(default_factory=list, description="Decorator names")
    kind: FunctionKind = Field(
        default=FunctionKind.FUNCTION, description="Callable classification"
    )
    line_start: int = Field(description="Start line (1-indexed)")
    line_end: int = Field(description="End line (1-indexed)")
    is_async: bool = Field(default=False, description="Whether function is async")
    signature: str | None = Field(default=None, description="Human-readable signature")

    @property
    def is_public(self) -> bool:
        """Whether this function is part of the public API."""
        return not self.name.startswith("_")

    def model_post_init(self, __context: Any) -> None:
        """Compute signature if not explicitly provided.

        Strips ``Annotated[T, ...]`` wrappers from parameter and return-type
        annotations so that generated signatures show only the base type.
        """
        if self.signature is None:
            params_str = ", ".join(
                p.name + (f": {_strip_annotated(p.annotation)}" if p.annotation else "")
                for p in self.params
            )
            ret_type = _strip_annotated(self.return_type) if self.return_type else None
            ret = f" -> {ret_type}" if ret_type else ""
            prefix = "async " if self.is_async else ""
            self.signature = f"{prefix}def {self.name}({params_str}){ret}"


class ClassInfo(BaseModel):
    """Metadata for a single class.

    Example:
        >>> cls = ClassInfo(name="Parser", line_start=1, line_end=50)
        >>> cls.is_public
        True
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Class name")
    bases: list[str] = Field(default_factory=list, description="Base class names")
    methods: list[FunctionInfo] = Field(default_factory=list, description="Methods")
    docstring: str | None = Field(default=None, description="Docstring content")
    decorators: list[str] = Field(default_factory=list, description="Decorator names")
    line_start: int = Field(description="Start line (1-indexed)")
    line_end: int = Field(description="End line (1-indexed)")

    @property
    def is_public(self) -> bool:
        """Whether this class is part of the public API."""
        return not self.name.startswith("_")


class ImportInfo(BaseModel):
    """A single import statement.

    Example:
        >>> imp = ImportInfo(module="pathlib", names=["Path"])
        >>> imp.is_relative
        False
    """

    model_config = ConfigDict(extra="forbid")

    module: str | None = Field(
        default=None, description="Module path (None for 'import x')"
    )
    names: list[str] = Field(default_factory=list, description="Imported names")
    alias: str | None = Field(default=None, description="Alias (as ...)")
    is_relative: bool = Field(default=False, description="Relative import")
    level: int = Field(default=0, description="Number of leading dots")


class VariableInfo(BaseModel):
    """A module-level variable or constant.

    Example:
        >>> v = VariableInfo(name="__all__", line=5)
        >>> v.name
        '__all__'
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Variable name")
    annotation: str | None = Field(default=None, description="Type annotation")
    value_repr: str | None = Field(
        default=None, description="Short repr of assigned value"
    )
    line: int = Field(description="Line number (1-indexed)")


class ModuleInfo(BaseModel):
    """Full introspection result for a single Python module.

    Example:
        >>> mod = ModuleInfo(path=Path("foo.py"))
        >>> len(mod.functions)
        0
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    path: Path = Field(description="File path")
    name: str | None = Field(default=None, description="Module name")
    docstring: str | None = Field(default=None, description="Module-level docstring")
    functions: list[Any] = Field(
        default_factory=list, description="Top-level functions"
    )
    classes: list[Any] = Field(default_factory=list, description="Top-level classes")
    imports: list[ImportInfo] = Field(
        default_factory=list, description="Import statements"
    )
    variables: list[VariableInfo] = Field(
        default_factory=list, description="Module-level variables"
    )
    all_exports: list[str] | None = Field(
        default=None,
        description="Contents of __all__, None if not defined",
    )

    @property
    def public_functions(self) -> list[FunctionInfo]:
        """Functions that are part of the public API."""
        if self.all_exports is not None:
            return [f for f in self.functions if f.name in self.all_exports]
        return [f for f in self.functions if f.is_public]

    @property
    def public_classes(self) -> list[ClassInfo]:
        """Classes that are part of the public API."""
        if self.all_exports is not None:
            return [c for c in self.classes if c.name in self.all_exports]
        return [c for c in self.classes if c.is_public]


class PackageInfo(BaseModel):
    """Full introspection result for a Python package.

    Example:
        >>> pkg = PackageInfo(name="mylib", root=Path("src/mylib"))
        >>> len(pkg.modules)
        0
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Package name")
    root: Path = Field(description="Package root directory")
    modules: list[ModuleInfo] = Field(default_factory=list, description="All modules")
    dependency_edges: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Internal import edges (from_module, to_module)",
    )

    @property
    def public_api(self) -> list[FunctionInfo | ClassInfo]:
        """All public functions and classes across the package."""
        result: list[FunctionInfo | ClassInfo] = []
        for mod in self.modules:
            result.extend(mod.public_functions)
            result.extend(mod.public_classes)
        return result

    @property
    def module_names(self) -> list[str]:
        """List of dotted module names."""
        names: list[str] = []
        for mod in self.modules:
            try:
                rel = mod.path.relative_to(self.root)
            except ValueError:
                names.append(mod.path.stem)
                continue
            parts = list(rel.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                names.append(".".join(parts))
            else:
                names.append(self.name)
        return names


class WorkspaceInfo(BaseModel):
    """Multi-package workspace introspection result.

    Aggregates multiple ``PackageInfo`` from a uv workspace.

    Example:
        >>> ws = WorkspaceInfo(name="my-ws", root=Path("/ws"))
        >>> len(ws.packages)
        0
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Workspace name")
    root: Path = Field(description="Workspace root directory")
    packages: list[PackageInfo] = Field(
        default_factory=list, description="All packages in workspace"
    )
    package_edges: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Inter-package dependency edges (from_pkg, to_pkg)",
    )
