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

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.core.parser import parse_source
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ModuleInfo, PackageInfo, WorkspaceInfo

__all__ = [
    "extract_calls",
    "extract_references",
    "find_callers",
    "find_callers_workspace",
]


_MAX_CALL_EXPRESSION_LEN = 80

# ─── Reference extraction (non-call usages) ─────────────────────────────────


def extract_references(mod: ModuleInfo) -> set[str]:
    """Extract symbol names used as references (not direct calls).

    Detects identifiers that appear as:
    - Dict values: ``{"key": my_func}``
    - List elements: ``[func_a, func_b]``
    - Tuple elements: ``(func_a, func_b)``
    - Set elements: ``{func_a, func_b}``

    This catches dynamic dispatch patterns where functions are stored
    in data structures and called indirectly.

    Args:
        mod: Parsed module info (with path to source).

    Returns:
        Set of symbol names referenced in data structures.
    """
    source = mod.path.read_text(encoding="utf-8")
    tree = parse_source(source)
    refs: set[str] = set()
    _visit_references(tree.root_node, refs)
    return refs


def _visit_references(node: object, refs: set[str]) -> None:
    """Recursively find identifiers in dict values, list/tuple/set elements."""
    node_type = getattr(node, "type", "")
    children = getattr(node, "children", [])

    if node_type == "pair":
        _collect_dict_value_ref(children, refs)
    elif node_type in ("list", "tuple", "set"):
        _collect_collection_refs(children, refs)

    # Recurse into all children.
    for child in children:
        _visit_references(child, refs)


def _collect_dict_value_ref(children: list[object], refs: set[str]) -> None:
    """Extract identifier from the value side of a dict pair."""
    past_colon = False
    for child in children:
        if getattr(child, "type", "") == ":":
            past_colon = True
            continue
        if past_colon:
            if getattr(child, "type", "") == "identifier":
                name = _node_text_safe(child)
                if name:
                    refs.add(name)
            return


def _collect_collection_refs(children: list[object], refs: set[str]) -> None:
    """Extract identifier references from list/tuple/set elements."""
    for child in children:
        if getattr(child, "type", "") == "identifier":
            name = _node_text_safe(child)
            if name:
                refs.add(name)


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
    _visit_calls(tree.root_node, mod_name, source, calls)
    return calls


def _visit_calls(
    node: object,
    module_name: str,
    source: str,
    calls: list[CallSite],
    context: str | None = None,
) -> None:
    """Recursively visit tree-sitter nodes to find calls."""
    # Update context for function/class definitions
    current_context = _update_context(node, context)

    if _is_call_node(node):
        call_site = _extract_call_site(node, module_name, source, current_context)
        if call_site is not None:
            calls.append(call_site)

    # Recurse into children
    for child in node.children:  # type: ignore[attr-defined]
        _visit_calls(child, module_name, source, calls, current_context)


def _is_call_node(node: object) -> bool:
    """Check if a node is a function call."""
    return getattr(node, "type", "") == "call"


def _update_context(node: object, current_context: str | None) -> str | None:
    """Update context when entering a function or class def."""
    node_type = getattr(node, "type", "")
    if node_type in (
        "function_definition",
        "class_definition",
    ):
        name_node = _find_child_by_type(node, "identifier")
        if name_node is not None:
            return _node_text_safe(name_node)
    return current_context


def _extract_call_site(
    node: object,
    module_name: str,
    source: str,
    context: str | None,
) -> CallSite | None:
    """Extract a CallSite from a call node."""
    # Get the function part of the call
    func_node = getattr(node, "children", [None])[0]
    if func_node is None:
        return None

    symbol = _resolve_symbol_name(func_node)
    if symbol is None:
        return None

    # Build call expression text
    call_text = _node_text_safe(node)
    # Truncate long call expressions
    if len(call_text) > _MAX_CALL_EXPRESSION_LEN:
        call_text = call_text[: _MAX_CALL_EXPRESSION_LEN - 3] + "..."

    start_point = getattr(node, "start_point", (0, 0))
    line = start_point[0] + 1  # tree-sitter uses 0-indexed
    column = start_point[1]

    return CallSite(
        module=module_name,
        symbol=symbol,
        line=line,
        column=column,
        context=context,
        call_expression=call_text,
    )


def _resolve_symbol_name(func_node: object) -> str | None:
    """Resolve the name of the called function.

    Handles:
    - Simple calls: ``foo()`` → "foo"
    - Method calls: ``self.bar()`` → "bar"
    - Chained calls: ``a.b.c()`` → "c"
    """
    node_type = getattr(func_node, "type", "")

    if node_type == "identifier":
        return _node_text_safe(func_node)

    if node_type == "attribute":
        # Get the attribute name (last part)
        attr_node = _find_child_by_type(func_node, "identifier")
        # Walk to the last identifier (rightmost)
        for child in reversed(getattr(func_node, "children", [])):
            if getattr(child, "type", "") == "identifier":
                return _node_text_safe(child)
        return _node_text_safe(attr_node) if attr_node else None

    return None


# ─── Tree-sitter helpers ────────────────────────────────────────────────────


def _find_child_by_type(node: object, child_type: str) -> object | None:
    """Find the first child of a given type."""
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == child_type:
            return child  # type: ignore[no-any-return]
    return None


def _node_text_safe(node: object) -> str:
    """Get text from a node safely."""
    text = getattr(node, "text", b"")
    if isinstance(text, bytes):
        return text.decode("utf-8")
    return str(text)


# ─── Cross-module caller search ─────────────────────────────────────────────


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
    from axm_ast.core.cache import get_calls

    # Use cached call-sites when possible
    try:
        calls_by_module = get_calls(pkg.root)
    except (ValueError, OSError):
        # Fallback for programmatic PackageInfo without a real root
        calls_by_module = None

    all_calls: list[CallSite] = []

    if calls_by_module is not None:
        for mod_calls in calls_by_module.values():
            for call in mod_calls:
                if call.symbol == symbol:
                    all_calls.append(call)
    else:
        for mod in pkg.modules:
            mod_name = module_dotted_name(mod.path, pkg.root)
            calls = extract_calls(mod, module_name=mod_name)
            for call in calls:
                if call.symbol == symbol:
                    all_calls.append(call)

    return all_calls


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
