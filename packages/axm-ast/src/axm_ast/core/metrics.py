"""Structural code metrics over a :class:`PackageInfo` — language-agnostic.

These are *facts* about code structure (how big a class is, how many modules a
module depends on), not quality judgments. axm-ast is the source of truth for
such facts; a consumer like axm-audit reads them and applies a threshold. They
work for any language whose backend populates the shared symbol model and the
package dependency graph (Python, TypeScript, …), so the same metric powers the
Python and node coupling/god-class rules from one implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from axm_ast.models.nodes import PackageInfo

__all__ = [
    "CouplingMetrics",
    "GodClass",
    "ModuleCoupling",
    "compute_coupling",
    "find_god_classes",
]

# Default thresholds (match the Python ARCH_GOD_CLASS / ARCH_COUPLING rules).
DEFAULT_MAX_LINES = 500
DEFAULT_MAX_METHODS = 15
DEFAULT_FAN_OUT_THRESHOLD = 10


class GodClass(BaseModel):
    """A class exceeding the size/method thresholds (a structural fact)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Class name")
    file: str = Field(description="Module path (relative or name)")
    lines: int = Field(description="Line span of the class")
    methods: int = Field(description="Number of methods")


class ModuleCoupling(BaseModel):
    """Fan-in / fan-out of a single module in the dependency graph."""

    model_config = ConfigDict(extra="forbid")

    module: str = Field(description="Module name")
    fan_in: int = Field(description="Number of modules that import this one")
    fan_out: int = Field(description="Number of modules this one imports")


class CouplingMetrics(BaseModel):
    """Aggregate coupling metrics over a package."""

    model_config = ConfigDict(extra="forbid")

    per_module: list[ModuleCoupling] = Field(default_factory=list)
    max_fan_out: int = Field(default=0)
    max_fan_in: int = Field(default=0)

    def over_fan_out(self, threshold: int) -> list[ModuleCoupling]:
        """Return modules whose fan-out exceeds *threshold*."""
        return [m for m in self.per_module if m.fan_out > threshold]


def find_god_classes(
    pkg: PackageInfo,
    *,
    max_lines: int = DEFAULT_MAX_LINES,
    max_methods: int = DEFAULT_MAX_METHODS,
) -> list[GodClass]:
    """Return classes exceeding the line or method thresholds across *pkg*.

    Uses the shared symbol model (``ClassInfo.line_start/line_end`` and
    ``methods``), so it is identical for Python and TypeScript classes.

    Args:
        pkg: Analyzed package.
        max_lines: Line-span ceiling above which a class is a god class.
        max_methods: Method-count ceiling above which a class is a god class.

    Returns:
        One :class:`GodClass` per offending class, sorted by file then name.
    """
    god: list[GodClass] = []
    for mod in pkg.modules:
        for cls in mod.classes:
            lines = cls.line_end - cls.line_start + 1
            methods = len(cls.methods)
            if lines > max_lines or methods > max_methods:
                god.append(
                    GodClass(
                        name=cls.name,
                        file=_module_label(mod.path, pkg),
                        lines=lines,
                        methods=methods,
                    )
                )
    return sorted(god, key=lambda g: (g.file, g.name))


def compute_coupling(pkg: PackageInfo) -> CouplingMetrics:
    """Compute fan-in / fan-out per module from the package dependency graph.

    The edges in ``pkg.dependency_edges`` are ``(src, target)`` import relations
    (built by the Python import resolver or the ES6 resolver), so fan-out is the
    out-degree and fan-in the in-degree of each module — a pure graph metric,
    language-agnostic.

    Args:
        pkg: Analyzed package (with ``dependency_edges`` populated).

    Returns:
        :class:`CouplingMetrics` with per-module fan-in/out and the maxima.
    """
    # Names come straight from the edge tuples so the metric is agnostic to how
    # each backend names modules (path-relative for node, dotted for Python).
    fan_out: dict[str, int] = {}
    fan_in: dict[str, int] = {}
    for src, target in pkg.dependency_edges:
        fan_out[src] = fan_out.get(src, 0) + 1
        fan_in[target] = fan_in.get(target, 0) + 1
        fan_out.setdefault(target, 0)
        fan_in.setdefault(src, 0)

    per_module = [
        ModuleCoupling(module=name, fan_in=fan_in.get(name, 0), fan_out=fan_out[name])
        for name in sorted(fan_out)
    ]
    return CouplingMetrics(
        per_module=per_module,
        max_fan_out=max((m.fan_out for m in per_module), default=0),
        max_fan_in=max((m.fan_in for m in per_module), default=0),
    )


def _module_label(path: object, pkg: PackageInfo) -> str:
    """Return a module's name relative to the package root, else its filename."""
    from pathlib import Path

    p = Path(str(path))
    try:
        return p.resolve().relative_to(pkg.root.resolve()).as_posix()
    except ValueError:
        return p.name
