"""CST visitors for reference collection and dotted-name extraction."""

from __future__ import annotations

import libcst as cst

__all__ = ["_ReferenceCollector", "_dotted_name"]


class _ReferenceCollector(cst.CSTVisitor):
    """Collect referenced names within a CST node.

    Visits all ``Name`` occurrences and records only the root of any
    ``Attribute`` chain (``foo.bar.baz`` -> ``"foo"``).
    """

    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        """Record a bare ``Name`` reference."""
        self.names.add(node.value)

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        """Record only the root of an ``Attribute`` chain; skip nested visit."""
        root: cst.BaseExpression = node
        while isinstance(root, cst.Attribute):
            root = root.value
        if isinstance(root, cst.Name):
            self.names.add(root.value)
        else:
            root.visit(self)
        return False


def _dotted_name(node: cst.CSTNode) -> str:
    """Convert a ``Name`` / ``Attribute`` chain to its dotted string form.

    Returns an empty string for any other node type.
    """
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        prefix = _dotted_name(node.value)
        if not prefix:
            return ""
        return f"{prefix}.{node.attr.value}"
    return ""
