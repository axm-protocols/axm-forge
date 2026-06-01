"""CST transformers for removing top-level symbols and attribute rewriting."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import libcst as cst
from libcst.metadata import ImportAssignment, ScopeProvider

__all__ = [
    "AttributeRewriter",
    "ProtectConditionalImports",
    "RemoveSymbols",
    "RenameSymbols",
    "SyncDunderAll",
]


def _is_import_line(line: cst.SimpleStatementLine) -> bool:
    """Return True when the statement line is a (possibly aliased) import."""
    return any(isinstance(inner, cst.Import | cst.ImportFrom) for inner in line.body)


def _line_has_f401_noqa(line: cst.SimpleStatementLine) -> bool:
    """Return True when the line already carries an ``F401`` noqa comment."""
    comment = line.trailing_whitespace.comment
    if comment is None:
        return False
    return "noqa" in comment.value and "F401" in comment.value


def _with_f401_noqa(line: cst.SimpleStatementLine) -> cst.SimpleStatementLine:
    """Append a ``# noqa: F401`` comment to an import statement line."""
    return line.with_changes(
        trailing_whitespace=cst.TrailingWhitespace(
            whitespace=cst.SimpleWhitespace("  "),
            comment=cst.Comment("# noqa: F401"),
            newline=cst.Newline(),
        )
    )


def _protect_block_imports(block: cst.IndentedBlock) -> cst.IndentedBlock:
    """Tag every import line in a guard suite with ``# noqa: F401``."""
    new_body: list[cst.BaseStatement] = []
    for stmt in block.body:
        if (
            isinstance(stmt, cst.SimpleStatementLine)
            and _is_import_line(stmt)
            and not _line_has_f401_noqa(stmt)
        ):
            new_body.append(_with_f401_noqa(stmt))
        else:
            new_body.append(stmt)
    return block.with_changes(body=tuple(new_body))


class _DepthTracker(cst.CSTTransformer):
    """Mixin tracking nesting depth via ``visit``/``leave`` of ``IndentedBlock``."""

    _depth: int = 0

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> None:  # noqa: N802
        """Track entry into a nested block."""
        self._depth += 1

    def leave_IndentedBlock(  # noqa: N802
        self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock
    ) -> cst.IndentedBlock:
        """Track exit from a nested block; pass through the updated node."""
        self._depth -= 1
        return updated_node


class ProtectConditionalImports(_DepthTracker):
    """Append ``# noqa: F401`` to imports nested in top-level guard blocks.

    Conditional imports (``try``/``except`` or ``if`` guards at module
    scope) must survive the post-move ``ruff --fix`` F401 pass even when no
    remaining symbol references them — removing the fallback branch of a
    ``try: import a / except: import b as a`` block silently changes runtime
    behavior (AXM-1775 AC3). Marking the import lines with a per-line noqa
    keeps the guard intact without disabling F401 for the whole file.

    Only module-level guards are tagged; guards nested inside functions or
    classes are left untouched.
    """

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0

    @staticmethod
    def _protected_else(orelse: cst.Else | cst.If | None) -> cst.Else | None:
        if isinstance(orelse, cst.Else) and isinstance(orelse.body, cst.IndentedBlock):
            return orelse.with_changes(body=_protect_block_imports(orelse.body))
        return None

    def leave_Try(  # noqa: N802
        self, original_node: cst.Try, updated_node: cst.Try
    ) -> cst.Try:
        """Protect imports in a top-level ``try``/``except``/``else`` guard."""
        if self._depth != 0:
            return updated_node
        changes: dict[str, object] = {}
        if isinstance(updated_node.body, cst.IndentedBlock):
            changes["body"] = _protect_block_imports(updated_node.body)
        if updated_node.handlers:
            changes["handlers"] = tuple(
                handler.with_changes(body=_protect_block_imports(handler.body))
                if isinstance(handler.body, cst.IndentedBlock)
                else handler
                for handler in updated_node.handlers
            )
        protected_else = self._protected_else(updated_node.orelse)
        if protected_else is not None:
            changes["orelse"] = protected_else
        return updated_node.with_changes(**changes) if changes else updated_node

    def leave_If(  # noqa: N802
        self, original_node: cst.If, updated_node: cst.If
    ) -> cst.If:
        """Protect imports in a top-level ``if``/``else`` guard."""
        if self._depth != 0:
            return updated_node
        if isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node.with_changes(
                body=_protect_block_imports(updated_node.body)
            )
        return updated_node


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

    def leave_Annotation(  # noqa: N802
        self, original_node: cst.Annotation, updated_node: cst.Annotation
    ) -> cst.Annotation:
        """Rewrite renamed identifiers inside a string forward-reference.

        A string annotation (``"OldName"``) is opaque to ``leave_Name`` — its
        content is a literal, not a ``Name`` node. Parse the string body,
        apply the same ``old -> new`` rename (whole-identifier match), and
        re-emit the string when its parsed content actually referenced a
        renamed symbol. Non-string annotations and strings that do not parse
        are left untouched.
        """
        value = original_node.annotation
        if not isinstance(value, cst.SimpleString):
            return updated_node
        raw = value.evaluated_value
        if not isinstance(raw, str):
            return updated_node
        try:
            expr = cst.parse_expression(raw)
        except cst.ParserSyntaxError:
            return updated_node
        rewritten = cast("cst.BaseExpression", expr.visit(RenameSymbols(self._mapping)))
        new_raw = cst.Module(body=[]).code_for_node(rewritten)
        if new_raw == raw:
            return updated_node
        prefix = value.prefix
        quote = value.quote
        return updated_node.with_changes(
            annotation=value.with_changes(value=f"{prefix}{quote}{new_raw}{quote}")
        )


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


class RemoveSymbols(_DepthTracker):
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


def _string_element_value(element: cst.BaseElement) -> str | None:
    """Return the literal text of a string ``Element`` (without quotes), else None."""
    if not isinstance(element, cst.Element):
        return None
    value = element.value
    if isinstance(value, cst.SimpleString):
        return value.raw_value
    if isinstance(value, cst.ConcatenatedString):
        evaluated = value.evaluated_value
        return evaluated if isinstance(evaluated, str) else None
    return None


class SyncDunderAll(_DepthTracker):
    """Synchronize a module's existing ``__all__`` literal on a symbol move.

    Removes the names in ``remove`` from the ``__all__`` ``List``/``Tuple``
    and appends the names in ``add`` that are not already present
    (idempotent). Existing ``Element`` nodes are reused untouched via
    ``.with_changes()`` so quotes, trailing commas and comments of the
    surviving entries are preserved. A module without a top-level
    ``__all__`` literal is left untouched — this transformer **never**
    synthesizes a new assignment.
    """

    def __init__(self, remove: set[str], add: list[str]) -> None:
        super().__init__()
        self._remove = remove
        self._add = add
        self._depth = 0

    def _is_dunder_all(self, node: cst.Assign) -> bool:
        return (
            len(node.targets) == 1
            and isinstance(node.targets[0].target, cst.Name)
            and node.targets[0].target.value == "__all__"
        )

    def _sync_elements(
        self, elements: Sequence[cst.BaseElement]
    ) -> list[cst.BaseElement]:
        kept: list[cst.BaseElement] = []
        present: set[str] = set()
        for element in elements:
            name = _string_element_value(element)
            if name is not None and name in self._remove:
                continue
            if name is not None:
                present.add(name)
            kept.append(element)
        for name in self._add:
            if name not in present:
                kept.append(cst.Element(value=cst.SimpleString(f'"{name}"')))
                present.add(name)
        return kept

    def leave_Assign(  # noqa: N802
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign:
        """Rewrite the ``__all__`` list/tuple elements in place when at module level."""
        if self._depth != 0 or not self._is_dunder_all(updated_node):
            return updated_node
        value = updated_node.value
        if not isinstance(value, cst.List | cst.Tuple):
            return updated_node
        new_elements = self._sync_elements(value.elements)
        return updated_node.with_changes(
            value=value.with_changes(elements=new_elements)
        )
