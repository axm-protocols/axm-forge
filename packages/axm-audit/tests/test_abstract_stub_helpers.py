from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule


def _parse_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Parse a single function definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node
    msg = "No function found in source"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# has_abstractmethod_decorator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "@abstractmethod\ndef foo(self): ...",
            True,
            id="bare_abstractmethod",
        ),
        pytest.param(
            "@abc.abstractmethod\ndef foo(self): ...",
            True,
            id="qualified_abc_abstractmethod",
        ),
        pytest.param(
            "def foo(self): ...",
            False,
            id="no_decorator",
        ),
        pytest.param(
            "@staticmethod\ndef foo(): ...",
            False,
            id="other_decorator",
        ),
    ],
)
def testhas_abstractmethod_decorator(source: str, expected: bool) -> None:
    """has_abstractmethod_decorator detects @abstractmethod."""
    # Also detects @abc.abstractmethod (qualified form).
    node = _parse_func(source)
    assert DocstringCoverageRule.has_abstractmethod_decorator(node) is expected


# ---------------------------------------------------------------------------
# is_stub_body
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("def foo(self): ...", True, id="ellipsis_body"),
        pytest.param("def foo(self):\n    pass", True, id="pass_body"),
        pytest.param("def foo(self):\n    return 42", False, id="real_body"),
        pytest.param(
            "def foo(self):\n    x = 1\n    return x",
            False,
            id="multi_statement_body",
        ),
    ],
)
def testis_stub_body(source: str, expected: bool) -> None:
    """is_stub_body returns True only for `...` or `pass` single-statement bodies."""
    node = _parse_func(source)
    assert DocstringCoverageRule.is_stub_body(node) is expected


# ---------------------------------------------------------------------------
# is_abstract_stub — edge cases
# ---------------------------------------------------------------------------


class TestIsAbstractStubEdgeCases:
    """Edge cases for is_abstract_stub after refactoring."""

    def test_abstract_with_real_body_not_stub(self) -> None:
        """@abstractmethod with implementation is NOT a stub."""
        node = _parse_func("""
            @abstractmethod
            def foo(self):
                return 42
        """)
        assert DocstringCoverageRule.is_abstract_stub(node) is False

    def test_non_abstract_ellipsis_not_stub(self) -> None:
        """Protocol-style method with ... but no @abstractmethod is NOT a stub."""
        node = _parse_func("""
            def foo(self): ...
        """)
        assert DocstringCoverageRule.is_abstract_stub(node) is False
