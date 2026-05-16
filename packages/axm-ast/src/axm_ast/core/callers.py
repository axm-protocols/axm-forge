"""Caller/usage analysis via tree-sitter call-site detection.

Parses call-sites from tree-sitter AST to answer "who calls this
function?" — traversing ``call`` nodes to find every function/method
invocation across a package.

Example:
    >>> from axm_ast.core.callers import find_callers
    >>> results = find_callers(pkg, "greet")
    >>> for r in results:
    ...     print(f"{r.module}:{r.line} — {r.call_expression}")
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

from tree_sitter import Node

from axm_ast.core._call_helpers import (
    extract_call_site,
    is_call_node,
    node_text_safe,
    update_context,
)
from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.parser import parse_source
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ModuleInfo, PackageInfo, WorkspaceInfo

logger = logging.getLogger(__name__)

__all__ = [
    "extract_calls",
    "extract_references",
    "find_callers",
    "find_callers_workspace",
]

# ─── Reference extraction (non-call usages) ─────────────────────────────────


def extract_references(mod: ModuleInfo) -> set[str]:
    """Extract symbol names used as references (not direct calls).

    Detects identifiers that appear as:
    - Dict values: ``{"key": my_func}``
    - List elements: ``[func_a, func_b]``
    - Tuple elements: ``(func_a, func_b)``
    - Set elements: ``{func_a, func_b}``
    - Keyword arguments: ``DataLoader(collate_fn=my_func)``
    - Default parameters: ``def foo(callback=my_func)``
    - Positional arguments: ``register(MyClass)`` (bare identifiers only)

    This catches dynamic dispatch patterns where functions are stored
    in data structures, passed as positional arguments, used as keyword
    arguments, or used as default parameter values.

    Args:
        mod: Parsed module info (with path to source).

    Returns:
        Set of symbol names referenced in non-call positions.
    """
    source = mod.path.read_text(encoding="utf-8")
    tree = parse_source(source)
    refs: set[str] = set()
    _visit_references(tree.root_node, refs)
    return refs


def _visit_references(node: Node, refs: set[str]) -> None:
    """Recursively find identifiers in non-call reference positions."""
    node_type = node.type
    children = node.children

    if node_type == "pair":
        _collect_dict_value_ref(children, refs)
    elif node_type in ("list", "tuple", "set"):
        _collect_collection_refs(children, refs)
    elif node_type in ("keyword_argument", "default_parameter"):
        _collect_kwarg_ref(children, refs)
    elif node_type == "assignment":
        # Handle `callback = self.method` — extract attribute ref from RHS.
        _collect_kwarg_ref(children, refs)
    elif node_type == "argument_list":
        _collect_argument_refs(children, refs)
    elif node_type == "string" and _is_forward_ref_string(node):
        _extract_forward_refs(node, refs)

    # Recurse into all children.
    for child in children:
        _visit_references(child, refs)


def _collect_dict_value_ref(children: list[Node], refs: set[str]) -> None:
    """Extract identifier from the value side of a dict pair."""
    past_colon = False
    for child in children:
        if child.type == ":":
            past_colon = True
            continue
        if past_colon:
            name = _extract_ref_name(child)
            if name:
                refs.add(name)
            return


def _collect_collection_refs(children: list[Node], refs: set[str]) -> None:
    """Extract identifier and attribute references from list/tuple/set elements."""
    for child in children:
        name = _extract_ref_name(child)
        if name:
            refs.add(name)


def _collect_argument_refs(children: list[Node], refs: set[str]) -> None:
    """Extract bare identifier/attribute refs from positional args.

    Skips call nodes (tracked by ``find_callers``) and literals.
    """
    for child in children:
        if child.type == "call":
            continue
        name = _extract_ref_name(child)
        if name:
            refs.add(name)


def _extract_ref_name(node: Node) -> str | None:
    """Return the reference name for an identifier or attribute node.

    - ``identifier`` nodes → return the identifier text.
    - ``attribute`` nodes (e.g. ``self._method``) → return the last
      identifier segment (the attribute name).
    - Everything else → ``None``.
    """
    node_type = node.type
    if node_type == "identifier":
        return node_text_safe(node) or None
    if node_type == "attribute":
        # Last child with type "identifier" is the attribute name.
        for child in reversed(node.children):
            if child.type == "identifier":
                return node_text_safe(child) or None
    return None


def _collect_kwarg_ref(children: list[Node], refs: set[str]) -> None:
    """Extract identifier from the value side of a kwarg or default param.

    Handles ``keyword_argument`` (``f(callback=my_func)``) and
    ``default_parameter`` (``def foo(fn=my_func)``) nodes.
    The structure is ``name = value``; we extract the value if
    it is a bare identifier or attribute (not a call or literal).
    """
    past_eq = False
    for child in children:
        if child.type == "=":
            past_eq = True
            continue
        if past_eq:
            name = _extract_ref_name(child)
            if name:
                refs.add(name)
            return


# ─── Forward-reference (string-typed) detection ─────────────────────────────

_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

# Tree-sitter parent node types that wrap a string used as a type annotation.
# A bare `type` node covers variable / return / parameter annotations.
_ANNOTATION_PARENT_TYPES = frozenset({"type"})


def _is_forward_ref_string(node: Node) -> bool:
    """Return True when ``node`` is a string in a typing position.

    Typing positions covered (Python tree-sitter grammar):

    * Direct child of a ``type`` node (variable / return / parameter
      annotation, including generic args via ``generic_type`` →
      ``type_parameter`` → ``type``).
    * 1st argument of a ``call`` whose function identifier is ``cast``.

    Excluded:

    * ``Annotated[T, *meta]`` — only the first ``type`` is a real type
      position; the rest are metadata.
    * ``Literal[...]`` — args are values, not types.
    """
    parent = node.parent
    if parent is None:
        return False
    parent_type = parent.type
    if parent_type == "argument_list":
        return _is_cast_first_string_arg(node, parent)
    if parent_type in _ANNOTATION_PARENT_TYPES:
        return _is_real_type_position(parent)
    return False


def _is_real_type_position(type_node: Node) -> bool:
    """True when a ``type`` node sits in a real type-position slot.

    Filters out ``Annotated[T, *metadata]`` non-first args and
    ``Literal[...]`` args, which the grammar still wraps in ``type``
    nodes despite being values/metadata semantically.
    """
    parent = type_node.parent
    if parent is None or parent.type != "type_parameter":
        return True
    container = _generic_container_name(parent.parent)
    if container == "Literal":
        return False
    if container == "Annotated":
        return _is_first_type_in_parameter(type_node, parent)
    return True


def _generic_container_name(generic_type: Node | None) -> str | None:
    """Return the container name of a ``generic_type`` node."""
    if generic_type is None or generic_type.type != "generic_type":
        return None
    for child in generic_type.children:
        name = _trailing_identifier(child)
        if name is not None:
            return name
    return None


def _is_first_type_in_parameter(type_node: Node, type_parameter: Node) -> bool:
    """True when ``type_node`` is the first ``type`` child of ``type_parameter``."""
    for child in type_parameter.children:
        if child.type == "type":
            return child.id == type_node.id
    return False


def _is_cast_first_string_arg(node: Node, argument_list: Node) -> bool:
    """True when ``node`` is the 1st arg of ``cast(...)``."""
    call_node = argument_list.parent
    if call_node is None or call_node.type != "call":
        return False
    func = call_node.child_by_field_name("function")
    if func is None:
        return False
    if _trailing_identifier(func) != "cast":
        return False
    # First non-punctuation child of argument_list is the 1st positional arg.
    for child in argument_list.children:
        if child.type in ("(", ")", ","):
            continue
        return child.id == node.id
    return False


def _trailing_identifier(node: Node) -> str | None:
    """Return the last identifier segment of an identifier/attribute node."""
    if node.type == "identifier":
        return node_text_safe(node) or None
    if node.type == "attribute":
        for child in reversed(node.children):
            if child.type == "identifier":
                return node_text_safe(child) or None
    return None


def _extract_forward_refs(node: Node, refs: set[str]) -> None:
    """Pull every Python identifier out of a string-literal node."""
    text = node_text_safe(node)
    if not text:
        return
    # Strip the surrounding quote characters so the regex sees only the content.
    body = text.strip()
    for quote in ('"""', "'''", '"', "'"):
        if (
            body.startswith(quote)
            and body.endswith(quote)
            and len(body) >= 2 * len(quote)
        ):
            body = body[len(quote) : -len(quote)]
            break
    refs.update(_IDENT_RE.findall(body))


# ─── Call extraction ─────────────────────────────────────────────────────────


def extract_calls(
    mod: ModuleInfo,
    module_name: str | None = None,
) -> list[CallSite]:
    """Extract all function/method call-sites from a module.

    Traverses the tree-sitter AST to find every ``call`` node
    and extracts the called symbol name, location, and context.

    Args:
        mod: Parsed module info (with path to source).
        module_name: Dotted module name for CallSite.module.

    Returns:
        List of CallSite objects for each call in the module.
    """
    source = mod.path.read_text(encoding="utf-8")
    tree = parse_source(source)
    mod_name = module_name or mod.path.stem

    calls: list[CallSite] = []
    source_bytes = source.encode("utf-8")
    _visit_calls(tree.root_node, mod_name, source_bytes, calls)
    return calls


def _visit_calls(
    node: Node,
    module_name: str,
    source_bytes: bytes,
    calls: list[CallSite],
    context: str | None = None,
) -> None:
    """Recursively visit tree-sitter nodes to find calls."""
    current_context = update_context(node, source_bytes, current=context)

    if is_call_node(node):
        call_site = extract_call_site(
            node,
            module=module_name,
            source_bytes=source_bytes,
            context=current_context,
        )
        if call_site is not None:
            calls.append(call_site)

    for child in node.children:
        _visit_calls(child, module_name, source_bytes, calls, current_context)


# ─── Cross-module caller search ─────────────────────────────────────────────


def _iter_cached_calls(pkg_root: Path) -> Iterator[CallSite] | None:
    from axm_ast.core.cache import get_calls

    try:
        calls_by_module = get_calls(pkg_root)
    except (ValueError, OSError):
        return None
    return (call for mod_calls in calls_by_module.values() for call in mod_calls)


def _iter_fresh_calls(pkg: PackageInfo) -> Iterator[CallSite]:
    for mod in pkg.modules:
        mod_name = module_dotted_name(mod.path, pkg.root)
        yield from extract_calls(mod, module_name=mod_name)


def find_callers(
    pkg: PackageInfo,
    symbol: str,
) -> list[CallSite]:
    """Find all call-sites of a given symbol across a package.

    Searches every module in the package for calls matching
    the given symbol name.  Uses cached call-sites when available
    to avoid re-parsing files on repeated queries.

    Args:
        pkg: Analyzed package info.
        symbol: Name of the function/method to search for.

    Returns:
        List of CallSite objects where the symbol is called.

    Example:
        >>> results = find_callers(pkg, "greet")
        >>> results[0].module
        'cli'
    """
    calls = _iter_cached_calls(pkg.root)
    if calls is None:
        calls = _iter_fresh_calls(pkg)
    return [c for c in calls if c.symbol == symbol]


def find_callers_workspace(
    ws: WorkspaceInfo,
    symbol: str,
) -> list[CallSite]:
    """Find all call-sites of a symbol across a workspace.

    Searches every package in the workspace for calls matching
    the given symbol name. Module names are prefixed with
    ``pkg_name::`` for disambiguation.

    Args:
        ws: Analyzed workspace info.
        symbol: Name of the function/method to search for.

    Returns:
        List of CallSite objects where the symbol is called.

    Example:
        >>> results = find_callers_workspace(ws, "ToolResult")
        >>> results[0].module
        'axm_mcp::server'
    """
    all_calls: list[CallSite] = []

    for pkg in ws.packages:
        callers = find_callers(pkg, symbol)
        for call in callers:
            # Prefix with package name for cross-package disambiguation
            call.module = f"{pkg.name}::{call.module}"
            all_calls.append(call)

    return all_calls
