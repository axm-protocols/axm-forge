"""CST visitors for reference collection and dotted-name extraction."""

from __future__ import annotations

import libcst as cst

__all__ = ["ReferenceCollector", "StringForwardRefScanner", "dotted_name"]


class ReferenceCollector(cst.CSTVisitor):
    """Collect *external* referenced names within a CST node.

    Visits all ``Name`` occurrences and records only the root of any
    ``Attribute`` chain (``foo.bar.baz`` -> ``"foo"``). Two classes of
    names are deliberately excluded from :attr:`names`:

    * **Keyword-argument names** (``f(x=1)`` -> ``x``): a kwarg label is a
      parameter name of the callee, never a reference to a surrounding
      symbol.
    * **Locally-bound names** (function/lambda parameters and simple
      assignment targets inside the visited block): these resolve to the
      block's own scope, not to an external top-level helper.

    Excluding both prevents a homonymous top-level helper from being pulled
    in as a spurious dependency of a moved block.
    """

    def __init__(self) -> None:
        super().__init__()
        self._names: set[str] = set()
        self._bound: set[str] = set()

    @property
    def names(self) -> set[str]:
        """External references: collected names minus locally-bound names."""
        return self._names - self._bound

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        """Record a bare ``Name`` reference."""
        self._names.add(node.value)

    def visit_Attribute(self, node: cst.Attribute) -> bool:  # noqa: N802
        """Record only the root of an ``Attribute`` chain; skip nested visit."""
        root: cst.BaseExpression = node
        while isinstance(root, cst.Attribute):
            root = root.value
        if isinstance(root, cst.Name):
            self._names.add(root.value)
        else:
            root.visit(self)
        return False

    def visit_Arg(self, node: cst.Arg) -> bool:  # noqa: N802
        """Skip a keyword label (``f(x=1)`` -> ``x``); visit only the value."""
        node.value.visit(self)
        return False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: N802
        """Record function parameters as locally-bound names."""
        self._record_params(node.params)

    def visit_Lambda(self, node: cst.Lambda) -> None:  # noqa: N802
        """Record lambda parameters as locally-bound names."""
        self._record_params(node.params)

    def visit_Assign(self, node: cst.Assign) -> None:  # noqa: N802
        """Record simple assignment targets as locally-bound names."""
        for target in node.targets:
            self._record_binding(target.target)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:  # noqa: N802
        """Record an annotated-assignment target as a locally-bound name."""
        self._record_binding(node.target)

    def _record_params(self, params: cst.Parameters) -> None:
        for param in (
            *params.posonly_params,
            *params.params,
            *params.kwonly_params,
        ):
            self._bound.add(param.name.value)
        if isinstance(params.star_arg, cst.Param):
            self._bound.add(params.star_arg.name.value)
        if params.star_kwarg is not None:
            self._bound.add(params.star_kwarg.name.value)

    def _record_binding(self, target: cst.BaseExpression) -> None:
        if isinstance(target, cst.Name):
            self._bound.add(target.value)
        elif isinstance(target, cst.Tuple | cst.List):
            for element in target.elements:
                self._record_binding(element.value)


class StringForwardRefScanner(cst.CSTVisitor):
    """Detect string annotations that forward-reference a moved symbol.

    Scans ``Annotation`` nodes whose value is a ``SimpleString`` or
    ``ConcatenatedString``. The string content is parsed with
    ``cst.parse_expression`` and its ``Name`` nodes are intersected with
    ``moved_names`` (whole-identifier match, never a substring). Each hit
    appends a structured, actionable message to :attr:`warnings`. This is
    detection-only: the visitor never mutates the tree.
    """

    def __init__(self, moved_names: set[str]) -> None:
        super().__init__()
        self.moved_names = moved_names
        self.warnings: list[str] = []
        self._func_stack: list[str] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: N802
        """Track the enclosing function and scan its return annotation."""
        self._func_stack.append(node.name.value)
        if node.returns is not None:
            self._scan(node.returns, f"{node.name.value}() return")

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:  # noqa: N802
        """Pop the enclosing-function stack."""
        self._func_stack.pop()

    def visit_Param(self, node: cst.Param) -> None:  # noqa: N802
        """Scan a parameter's string annotation."""
        if node.annotation is not None:
            func = self._func_stack[-1] if self._func_stack else "<module>"
            self._scan(node.annotation, f"{func}({node.name.value})")

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:  # noqa: N802
        """Scan an annotated assignment's string annotation."""
        ctx = dotted_name(node.target) or "<assignment>"
        self._scan(node.annotation, ctx)

    def _scan(self, annotation: cst.Annotation, ctx: str) -> None:
        value = annotation.annotation
        if not isinstance(value, cst.SimpleString | cst.ConcatenatedString):
            return
        raw = value.evaluated_value
        if not isinstance(raw, str):
            return
        try:
            expr = cst.parse_expression(raw)
        except cst.ParserSyntaxError:
            return
        collector = ReferenceCollector()
        expr.visit(collector)
        for name in sorted(collector.names & self.moved_names):
            self.warnings.append(
                f"forward-reference '{name}' in string annotation at {ctx} "
                "not rewritten; update manually"
            )


def dotted_name(node: cst.CSTNode) -> str:
    """Convert a ``Name`` / ``Attribute`` chain to its dotted string form.

    Returns an empty string for any other node type.
    """
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        prefix = dotted_name(node.value)
        if not prefix:
            return ""
        return f"{prefix}.{node.attr.value}"
    return ""
