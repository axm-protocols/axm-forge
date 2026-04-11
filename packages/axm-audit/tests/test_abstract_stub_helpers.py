from __future__ import annotations

import ast
import textwrap

from axm_audit.core.rules.practices import DocstringCoverageRule


def _parse_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Parse a single function definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node
    msg = "No function found in source"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# _has_abstractmethod_decorator
# ---------------------------------------------------------------------------


class TestHasAbstractmethodDecorator:
    """Tests for the extracted _has_abstractmethod_decorator helper."""

    def test_bare_abstractmethod(self) -> None:
        node = _parse_func("""
            @abstractmethod
            def foo(self): ...
        """)
        assert DocstringCoverageRule._has_abstractmethod_decorator(node) is True

    def test_qualified_abc_abstractmethod(self) -> None:
        node = _parse_func("""
            @abc.abstractmethod
            def foo(self): ...
        """)
        assert DocstringCoverageRule._has_abstractmethod_decorator(node) is True

    def test_no_decorator(self) -> None:
        node = _parse_func("""
            def foo(self): ...
        """)
        assert DocstringCoverageRule._has_abstractmethod_decorator(node) is False

    def test_other_decorator(self) -> None:
        node = _parse_func("""
            @staticmethod
            def foo(): ...
        """)
        assert DocstringCoverageRule._has_abstractmethod_decorator(node) is False


# ---------------------------------------------------------------------------
# _is_stub_body
# ---------------------------------------------------------------------------


class TestIsStubBody:
    """Tests for the extracted _is_stub_body helper."""

    def test_ellipsis_body(self) -> None:
        node = _parse_func("""
            def foo(self): ...
        """)
        assert DocstringCoverageRule._is_stub_body(node) is True

    def test_pass_body(self) -> None:
        node = _parse_func("""
            def foo(self):
                pass
        """)
        assert DocstringCoverageRule._is_stub_body(node) is True

    def test_real_body(self) -> None:
        node = _parse_func("""
            def foo(self):
                return 42
        """)
        assert DocstringCoverageRule._is_stub_body(node) is False

    def test_multi_statement_body(self) -> None:
        node = _parse_func("""
            def foo(self):
                x = 1
                return x
        """)
        assert DocstringCoverageRule._is_stub_body(node) is False


# ---------------------------------------------------------------------------
# _is_abstract_stub — edge cases
# ---------------------------------------------------------------------------


class TestIsAbstractStubEdgeCases:
    """Edge cases for _is_abstract_stub after refactoring."""

    def test_abstract_with_real_body_not_stub(self) -> None:
        """@abstractmethod with implementation is NOT a stub."""
        node = _parse_func("""
            @abstractmethod
            def foo(self):
                return 42
        """)
        assert DocstringCoverageRule._is_abstract_stub(node) is False

    def test_non_abstract_ellipsis_not_stub(self) -> None:
        """Protocol-style method with ... but no @abstractmethod is NOT a stub."""
        node = _parse_func("""
            def foo(self): ...
        """)
        assert DocstringCoverageRule._is_abstract_stub(node) is False
