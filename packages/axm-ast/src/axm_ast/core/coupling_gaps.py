"""Resolve structural Protocol/ABC coupling that the reference walk misses.

``ast_impact`` walks the *reference* graph: it only sees a symbol when another
symbol names it explicitly (import, base class, call by name).  A class that
implements a :class:`typing.Protocol` **by shape** — matching the method
signatures without ever importing or inheriting the Protocol — and a consumer
that calls such a method on an untyped receiver are both invisible to that
walk.  This read-only pass enumerates those shape-conforming sites so the
blast-radius lower-bound gap becomes explicit.

The pass performs no file writes and re-parses nothing by hand: it consumes an
already-analysed :class:`~axm_ast.models.nodes.PackageInfo` and reuses the
tree-sitter caller primitive (:func:`~axm_ast.core.callers.find_callers`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.callers import find_callers

if TYPE_CHECKING:
    from axm_ast.models.nodes import ClassInfo, ModuleInfo, PackageInfo

__all__ = ["ProtocolCoupledSite", "find_protocol_coupled"]

_PROTOCOL_BASES = frozenset({"Protocol", "ABC", "ABCMeta"})


@dataclass(frozen=True)
class ProtocolCoupledSite:
    """A site structurally coupled to a Protocol/ABC without referencing it.

    Attributes:
        file: Source file containing the coupled site.
        line: 1-indexed line of the class definition or the call expression.
        why: Human-readable justification for surfacing the site.
        confidence: Syntactic match confidence in ``[0, 1]`` — a heuristic,
            since matching is by method shape only (no type inference).
    """

    file: Path
    line: int
    why: str
    confidence: float = 1.0


def _is_protocol_or_abc(cls: ClassInfo) -> bool:
    """Whether *cls* is a Protocol/ABC member (by base-class heuristic).

    Mirrors ``core.dead_code._is_protocol_class`` (``"Protocol" in bases``) and
    widens it to the ``abc`` bases, since ABC members are equally invisible to
    the reference walk when implemented by shape.
    """
    return bool(_PROTOCOL_BASES.intersection(cls.bases))


def _find_protocol_target(pkg: PackageInfo, symbol: str) -> ClassInfo | None:
    """Return the Protocol/ABC class named *symbol*, or ``None``."""
    for mod in pkg.modules:
        for cls in mod.classes:
            if cls.name == symbol and _is_protocol_or_abc(cls):
                return cls
    return None


def _protocol_method_names(target: ClassInfo) -> set[str]:
    """Names of the target's non-dunder methods — its structural shape."""
    return {m.name for m in target.methods if not m.name.startswith("__")}


def _structural_implementors(
    pkg: PackageInfo,
    target: ClassInfo,
    method_names: set[str],
) -> list[ProtocolCoupledSite]:
    """Classes matching the target's method shape without referencing it."""
    sites: list[ProtocolCoupledSite] = []
    for mod in pkg.modules:
        for cls in mod.classes:
            if cls.name == target.name or target.name in cls.bases:
                continue
            matched = {m.name for m in cls.methods} & method_names
            if not matched:
                continue
            confidence = len(matched) / len(method_names) if method_names else 1.0
            sites.append(
                ProtocolCoupledSite(
                    file=mod.path,
                    line=cls.line_start,
                    why=(
                        f"class {cls.name!r} implements method(s) "
                        f"{sorted(matched)} of protocol {target.name!r} by shape "
                        f"(no import or base reference)"
                    ),
                    confidence=confidence,
                )
            )
    return sites


def _module_path_index(pkg: PackageInfo) -> dict[str, Path]:
    """Map every dotted/stem key of a module to its source path."""
    index: dict[str, Path] = {}
    for mod in pkg.modules:
        for key in _module_keys(mod, pkg.root):
            index.setdefault(key, mod.path)
    return index


def _module_keys(mod: ModuleInfo, root: Path) -> set[str]:
    """Candidate lookup keys for a module (name, stem, dotted name)."""
    keys = {mod.path.stem, module_dotted_name(mod.path, root)}
    if mod.name:
        keys.add(mod.name)
    return keys


def _structural_consumers(
    pkg: PackageInfo,
    target: ClassInfo,
    method_names: set[str],
) -> list[ProtocolCoupledSite]:
    """Call-sites invoking a protocol method by shape on any receiver."""
    paths = _module_path_index(pkg)
    sites: list[ProtocolCoupledSite] = []
    for name in sorted(method_names):
        for call in find_callers(pkg, name):
            sites.append(
                ProtocolCoupledSite(
                    file=paths.get(call.module, Path(call.module)),
                    line=call.line,
                    why=(
                        f"call {call.call_expression!r} conforms to method "
                        f"{name!r} of protocol {target.name!r} by shape "
                        f"(no reference find_callers can walk to {target.name!r})"
                    ),
                    confidence=call.confidence,
                )
            )
    return sites


def find_protocol_coupled(pkg: PackageInfo, symbol: str) -> list[ProtocolCoupledSite]:
    """Enumerate sites structurally coupled to the Protocol/ABC named *symbol*.

    Surfaces the shape-conforming implementors and consumers that the
    reference-based ``ast_impact`` walk omits.  When *symbol* does not resolve
    to a Protocol/ABC class in *pkg*, there is no structural contract to match,
    so an empty list is returned.

    Args:
        pkg: Analysed package info (tree-sitter backed; no disk read here).
        symbol: Name of the Protocol/ABC to resolve structural coupling for.

    Returns:
        A list of :class:`ProtocolCoupledSite`, each carrying ``file``,
        ``line`` and ``why``; empty when *symbol* is not a Protocol/ABC member.
    """
    target = _find_protocol_target(pkg, symbol)
    if target is None:
        return []
    method_names = _protocol_method_names(target)
    return [
        *_structural_implementors(pkg, target, method_names),
        *_structural_consumers(pkg, target, method_names),
    ]
