"""Unit tests for the ``doc_policy`` documentation-required predicate."""

from __future__ import annotations

from axm_ast.doc_policy import is_documentation_required
from axm_ast.models.nodes import ClassInfo, FunctionInfo


class TestIsDocumentationRequired:
    """Cover the public-surface + docstring-presence policy branches."""

    def test_public_docstringed_symbol_is_not_a_gap(self) -> None:
        """AC1: a public symbol with a non-empty docstring is documented."""
        fn = FunctionInfo(
            name="parse",
            docstring="Parse the thing.",
            line_start=1,
            line_end=3,
        )
        assert is_documentation_required(fn) is False

    def test_private_symbol_never_required_regardless_of_docstring(self) -> None:
        """AC2: a ``_``-prefixed symbol is never required, docstring or not."""
        with_doc = FunctionInfo(
            name="_helper",
            docstring="Helps.",
            line_start=1,
            line_end=2,
        )
        without_doc = FunctionInfo(
            name="_helper",
            docstring=None,
            line_start=1,
            line_end=2,
        )
        assert is_documentation_required(with_doc) is False
        assert is_documentation_required(without_doc) is False

    def test_public_symbol_without_docstring_is_a_gap(self) -> None:
        """AC3: a public symbol with no docstring is documentation-required."""
        cls = ClassInfo(name="Parser", docstring=None, line_start=1, line_end=5)
        assert is_documentation_required(cls) is True

    def test_dunder_handling_matches_practices_policy(self) -> None:
        """AC4: dunders (e.g. ``__init__``) are excluded like the practices rule."""
        dunder = FunctionInfo(
            name="__init__",
            docstring=None,
            line_start=1,
            line_end=2,
        )
        # Practices skips every name starting with "_" -> __init__ not required.
        assert is_documentation_required(dunder) is False
