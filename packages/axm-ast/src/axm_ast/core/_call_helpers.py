"""Internal-API helpers for tree-sitter call-site analysis.

This module's name has a leading underscore (``_call_helpers``) to mark it as
package-internal-but-importable across ``axm_ast.core`` — distinct from the
symbol-level ``_prefix`` convention which is module-local. Symbols defined
here are public (no underscore prefix) so other ``axm_ast.core`` modules can
import them without violating the no-private-cross-module-import rule.

Internal API: importable across ``axm_ast.core`` only. Not exported from the
package root.
"""

from __future__ import annotations

from axm_ast.models.calls import CallSite

__all__ = [
    "extract_call_site",
    "is_call_node",
    "node_text_safe",
    "update_context",
]


_MAX_CALL_EXPRESSION_LEN = 80


def is_call_node(node: object) -> bool:
    """Return True when *node* is a tree-sitter ``call`` node."""
    return getattr(node, "type", "") == "call"


def node_text_safe(node: object | None, source_bytes: bytes = b"") -> str:
    """Return the text covered by *node*, or ``""`` when *node* is ``None``.

    The ``source_bytes`` argument is reserved for callers that wish to slice
    the source explicitly; the default reads ``node.text`` (populated by
    tree-sitter).
    """
    if node is None:
        return ""
    text = getattr(node, "text", b"")
    if isinstance(text, bytes):
        return text.decode("utf-8")
    return str(text)


def update_context(
    node: object,
    source_bytes: bytes = b"",
    *,
    current: str | None = None,
) -> str | None:
    """Return the enclosing function/class name when *node* is a definition.

    Otherwise return *current* unchanged. Used by call-site walkers to track
    the surrounding scope when recording each call.
    """
    del source_bytes  # reserved for symmetry; not needed when node.text is set.
    node_type = getattr(node, "type", "")
    if node_type in ("function_definition", "class_definition"):
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                return node_text_safe(child)
    return current


def extract_call_site(
    node: object,
    module: str,
    source_bytes: bytes,
    context: str | None,
) -> CallSite | None:
    """Build a :class:`CallSite` from a tree-sitter ``call`` *node*.

    Returns ``None`` when the called symbol cannot be resolved (e.g. dynamic
    constructions like ``getattr(obj, name)()``).
    """
    del source_bytes  # node.text already carries the bytes we need.
    func_node = getattr(node, "children", [None])[0]
    if func_node is None:
        return None

    symbol = _resolve_symbol_name(func_node)
    if symbol is None:
        return None

    call_text = node_text_safe(node)
    if len(call_text) > _MAX_CALL_EXPRESSION_LEN:
        call_text = call_text[: _MAX_CALL_EXPRESSION_LEN - 3] + "..."

    start_point = getattr(node, "start_point", (0, 0))
    line = start_point[0] + 1
    column = start_point[1]

    return CallSite(
        module=module,
        symbol=symbol,
        line=line,
        column=column,
        context=context,
        call_expression=call_text,
    )


def _resolve_symbol_name(func_node: object) -> str | None:
    """Resolve the called symbol name from the function-position node."""
    node_type = getattr(func_node, "type", "")

    if node_type == "identifier":
        return node_text_safe(func_node)

    if node_type == "attribute":
        for child in reversed(getattr(func_node, "children", [])):
            if getattr(child, "type", "") == "identifier":
                return node_text_safe(child)
        return None

    return None
