"""CST transformers for removing top-level symbols and attribute rewriting."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import ImportAssignment, ScopeProvider

__all__ = ["AttributeRewriter", "RemoveSymbols", "RenameSymbols"]


class RenameSymbols(cst.CSTTransformer):
    """Rename ``Name`` nodes according to an ``old -> new`` mapping.

    Every identifier whose value matches a key in ``mapping`` is rewritten
    to the corresponding value. This covers definition names
    (``def OldName`` / ``class OldName``), internal references (recursion,
    self-references) and usage sites in caller modules. Attribute *names*
    (the ``attr`` of an ``Attribute`` node, e.g. ``obj.OldName``) are left
    untouched so unrelated members are not renamed.
    """

    def __init__(self, mapping: dict[str, str]) -> None:
        super().__init__()
        self._mapping = mapping

    def leave_Name(  # noqa: N802
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.Name:
        """Rewrite a bare name when it matches a rename key."""
        new = self._mapping.get(updated_node.value)
        if new is None:
            return updated_node
        return updated_node.with_changes(value=new)

    def leave_Attribute(  # noqa: N802
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Preserve the attribute member name, restoring it if renamed.

        ``leave_Name`` fires for the ``attr`` child too; undo that rewrite so
        only the head of the expression (a real binding) is renamed.
        """
        if isinstance(original_node.attr, cst.Name):
            return updated_node.with_changes(attr=original_node.attr)
        return updated_node


def _dotted_to_expr(dotted: str) -> cst.BaseExpression:
    """Build a ``Name``/``Attribute`` chain from a dotted path like ``pkg.new``."""
    parts = dotted.split(".")
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _dump_attr(node: cst.BaseExpression) -> str | None:
    """Render an ``Attribute``/``Name`` chain back to its dotted string form."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        inner = _dump_attr(node.value)
        if inner is None:
            return None
        return f"{inner}.{node.attr.value}"
    return None


def _leftmost_name(node: cst.BaseExpression) -> cst.Name | None:
    """Return the leftmost ``Name`` at the root of an attribute chain."""
    current = node
    while isinstance(current, cst.Attribute):
        current = current.value
    return current if isinstance(current, cst.Name) else None


class AttributeRewriter(cst.CSTTransformer):
    """Rewrite attribute chains rooted at ``old_module_alias`` for given symbols.

    Given ``old_module_alias`` (either the dotted module, e.g. ``pkg.old``, or a
    local alias bound via ``import pkg.old as om``) and a set of ``symbols``, this
    transformer rewrites attribute accesses of the form ``<alias>.<Symbol>`` to
    ``new_module.<Symbol>``. Chains beyond the symbol
    (``<alias>.<Symbol>.method()`` etc.) are preserved structurally. Uses
    ``ScopeProvider`` to avoid rewriting references whose leftmost name is
    shadowed by a local (non-import) binding. Exposes ``kept_usages``: the count
    of remaining ``<alias>.<other>`` references after rewriting, so callers can
    decide whether to drop ``import old_module``.
    """

    METADATA_DEPENDENCIES = (ScopeProvider,)

    def __init__(
        self,
        *,
        old_module_alias: str,
        new_module: str,
        symbols: set[str],
    ) -> None:
        super().__init__()
        self._old_alias = old_module_alias
        self._new_module = new_module
        self._symbols = set(symbols)
        self.kept_usages = 0

    def _leftmost_is_safe(self, original_value: cst.BaseExpression) -> bool:
        """Return ``True`` unless the leftmost name is shadowed by a non-import."""
        name = _leftmost_name(original_value)
        if name is None:
            return False
        try:
            scope = self.get_metadata(ScopeProvider, name)
        except KeyError:
            return True
        if scope is None:
            return True
        assignments = list(scope[name.value])
        if not assignments:
            return True
        if any(isinstance(a, ImportAssignment) for a in assignments):
            return True
        return False

    def leave_Attribute(  # noqa: N802
        self,
        original_node: cst.Attribute,
        updated_node: cst.Attribute,
    ) -> cst.BaseExpression:
        """Rewrite ``alias.Symbol`` chain roots; count untouched ``alias.*`` refs."""
        if _dump_attr(original_node.value) != self._old_alias:
            return updated_node
        if not self._leftmost_is_safe(original_node.value):
            return updated_node
        if updated_node.attr.value in self._symbols:
            return updated_node.with_changes(value=_dotted_to_expr(self._new_module))
        self.kept_usages += 1
        return updated_node


class RemoveSymbols(cst.CSTTransformer):
    """Remove targeted top-level ``ClassDef``, ``FunctionDef``, or constant
    assignments (``Assign`` / ``AnnAssign``) from a module.

    Surrounding formatting (comments, blank lines, indentation of other
    top-level symbols) is preserved thanks to libcst's lossless tree.
    Non-assignment ``SimpleStatementLine`` nodes (imports, docstrings,
    bare expressions) are left untouched.
    """

    def __init__(self, names_to_remove: set[str]) -> None:
        super().__init__()
        self._targets = names_to_remove
        self._depth = 0

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:  # noqa: N802
        """Track entry into a nested block to avoid removing nested symbols."""
        self._depth += 1

    def leave_IndentedBlock(  # noqa: N802
        self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock
    ) -> cst.IndentedBlock:
        """Track exit from a nested block; pass through the updated node."""
        self._depth -= 1
        return updated_node

    def leave_ClassDef(  # noqa: N802
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef | cst.RemovalSentinel:
        """Drop the class when its top-level name matches a removal target."""
        if self._depth == 0 and updated_node.name.value in self._targets:
            return cst.RemoveFromParent()
        return updated_node

    def leave_FunctionDef(  # noqa: N802
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef | cst.RemovalSentinel:
        """Drop the function when its top-level name matches a removal target."""
        if self._depth == 0 and updated_node.name.value in self._targets:
            return cst.RemoveFromParent()
        return updated_node

    def _should_remove_assign(self, node: cst.Assign) -> bool:
        return (
            len(node.targets) == 1
            and isinstance(node.targets[0].target, cst.Name)
            and node.targets[0].target.value in self._targets
        )

    def _should_remove_ann_assign(self, node: cst.AnnAssign) -> bool:
        return isinstance(node.target, cst.Name) and node.target.value in self._targets

    def _should_remove_stmt(self, inner: cst.BaseSmallStatement) -> bool:
        if isinstance(inner, cst.Assign):
            return self._should_remove_assign(inner)
        if isinstance(inner, cst.AnnAssign):
            return self._should_remove_ann_assign(inner)
        return False

    def leave_SimpleStatementLine(  # noqa: N802
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        """Drop top-level statement lines whose assignments target a removed name."""
        if self._depth != 0:
            return updated_node
        if any(self._should_remove_stmt(inner) for inner in updated_node.body):
            return cst.RemoveFromParent()
        return updated_node
