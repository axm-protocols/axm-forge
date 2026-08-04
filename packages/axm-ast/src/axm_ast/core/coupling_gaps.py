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

from axm_ast.core._call_helpers import node_text_safe
from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.callers import find_callers
from axm_ast.core.parser import parse_file

if TYPE_CHECKING:
    from axm_ast.models.nodes import ClassInfo, ModuleInfo, PackageInfo

__all__ = [
    "ProtocolCoupledSite",
    "ValueCoupledSite",
    "find_protocol_coupled",
    "find_value_coupled",
]

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


_EQUALITY_OPS = frozenset({"==", "!="})
_MEMBERSHIP_OPS = frozenset({"in", "not in"})


@dataclass(frozen=True)
class ValueCoupledSite:
    """A site coupled to a target through one of its contract literal values.

    Reference-graph analysis is blind to coupling that flows through a literal
    value: a branch on ``verdict == "pass"``, a membership test against a
    literal set, or a ``match`` arm.  This surfaces those literal-keyed
    operational sites tied to the target's declared contract literals.

    Attributes:
        file: Source file containing the literal-keyed site.
        line: 1-indexed line of the operational site.
        why: Human-readable justification for surfacing the site.
        confidence: Label distinguishing a high-confidence exact match
            (equality / match arm) from a low-confidence heuristic one
            (membership in a literal collection).
    """

    file: Path
    line: int
    why: str
    confidence: str = "high"


def _string_value(node: object) -> str | None:
    """Return the value of a tree-sitter ``string`` *node*, quotes stripped."""
    if getattr(node, "type", "") != "string":
        return None
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == "string_content":
            return node_text_safe(child)
    raw = node_text_safe(node)
    return raw.strip("\"'") if raw else None


def _collect_string_values(node: object, out: set[str]) -> None:
    """Accumulate every string-literal value reachable from *node*."""
    if getattr(node, "type", "") == "string":
        value = _string_value(node)
        if value is not None:
            out.add(value)
        return
    for child in getattr(node, "children", []):
        _collect_string_values(child, out)


def _find_definition_node(node: object, symbol: str) -> object | None:
    """Return the ``def``/``class`` node named *symbol*, or ``None``."""
    node_type = getattr(node, "type", "")
    if node_type in ("function_definition", "class_definition"):
        for child in getattr(node, "children", []):
            is_name = getattr(child, "type", "") == "identifier"
            if is_name and node_text_safe(child) == symbol:
                return node
    for child in getattr(node, "children", []):
        found = _find_definition_node(child, symbol)
        if found is not None:
            return found
    return None


def _return_literals(def_node: object, out: set[str]) -> None:
    """Accumulate string literals returned within the target definition."""
    if getattr(def_node, "type", "") == "return_statement":
        _collect_string_values(def_node, out)
    for child in getattr(def_node, "children", []):
        _return_literals(child, out)


def _derive_contract_literals(pkg: PackageInfo, symbol: str) -> set[str]:
    """Derive the literal values that make up *symbol*'s declared contract."""
    literals: set[str] = set()
    for mod in pkg.modules:
        def_node = _find_definition_node(parse_file(mod.path).root_node, symbol)
        if def_node is not None:
            _return_literals(def_node, literals)
            break
    return literals


def _comparison_kind(node: object) -> str | None:
    """Classify a ``comparison_operator`` node as equality or membership."""
    children = getattr(node, "children", [])
    child_types = {getattr(child, "type", "") for child in children}
    if child_types & _EQUALITY_OPS:
        return "equality"
    if child_types & _MEMBERSHIP_OPS:
        return "membership"
    return None


def _node_line(node: object) -> int:
    """1-indexed start line of *node*."""
    start_point = getattr(node, "start_point", (0, 0))
    return int(start_point[0]) + 1


def _emit_comparison_site(
    node: object,
    path: Path,
    symbol: str,
    literals: set[str],
    sites: list[ValueCoupledSite],
) -> None:
    """Record a site when a comparison keys on a target contract literal."""
    kind = _comparison_kind(node)
    if kind is None:
        return
    values: set[str] = set()
    _collect_string_values(node, values)
    matched = values & literals
    if not matched:
        return
    sites.append(
        ValueCoupledSite(
            file=path,
            line=_node_line(node),
            why=(
                f"site {node_text_safe(node)!r} keys on contract literal(s) "
                f"{sorted(matched)} of {symbol!r} via {kind} match"
            ),
            confidence="high" if kind == "equality" else "low",
        )
    )


def _emit_case_site(
    node: object,
    path: Path,
    symbol: str,
    literals: set[str],
    sites: list[ValueCoupledSite],
) -> None:
    """Record a site when a ``match`` arm keys on a target contract literal."""
    values: set[str] = set()
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == "case_pattern":
            _collect_string_values(child, values)
    matched = values & literals
    if not matched:
        return
    sites.append(
        ValueCoupledSite(
            file=path,
            line=_node_line(node),
            why=(
                f"match arm keys on contract literal(s) {sorted(matched)} of {symbol!r}"
            ),
            confidence="high",
        )
    )


def _collect_value_sites(
    node: object,
    path: Path,
    symbol: str,
    literals: set[str],
    sites: list[ValueCoupledSite],
) -> None:
    """Walk *node*, recording every literal-keyed operational site."""
    node_type = getattr(node, "type", "")
    if node_type == "comparison_operator":
        _emit_comparison_site(node, path, symbol, literals, sites)
    elif node_type == "case_clause":
        _emit_case_site(node, path, symbol, literals, sites)
    for child in getattr(node, "children", []):
        _collect_value_sites(child, path, symbol, literals, sites)


def find_value_coupled(pkg: PackageInfo, symbol: str) -> list[ValueCoupledSite]:
    """Enumerate sites coupled to *symbol* through its contract literal values.

    Derives *symbol*'s declared contract literals (its return literals) and
    locates the operational sites keyed on them — equality comparisons,
    membership tests and ``match`` arms.  Matches are scoped to the derived
    contract literals, so an identical literal that is not part of the
    contract is not reported.  When *symbol* declares no contract literals,
    there is nothing to key on and an empty list is returned.

    Args:
        pkg: Analysed package info (tree-sitter backed; no disk write here).
        symbol: Name of the target whose literal contract to resolve.

    Returns:
        A list of :class:`ValueCoupledSite`, each carrying ``file``, ``line``,
        ``why`` and a ``confidence`` label; empty when no contract literal is
        derivable for *symbol*.
    """
    literals = _derive_contract_literals(pkg, symbol)
    if not literals:
        return []
    sites: list[ValueCoupledSite] = []
    for mod in pkg.modules:
        _collect_value_sites(
            parse_file(mod.path).root_node, mod.path, symbol, literals, sites
        )
    return sites
