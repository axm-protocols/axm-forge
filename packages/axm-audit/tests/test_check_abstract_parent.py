from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.practices import DocstringCoverageRule


@pytest.fixture
def rule() -> DocstringCoverageRule:
    return DocstringCoverageRule()


def _parse_class(source: str) -> ast.ClassDef:
    """Parse a single class definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    msg = "No ClassDef found"
    raise ValueError(msg)


# --- Existing behavior tests ---


def test_abstract_override_no_parent_docstring(rule: DocstringCoverageRule) -> None:
    """Abstract parent without docstring → override still requires docstring."""
    cls = _parse_class("""
        class Base:
            @abstractmethod
            def do_work(self):
                pass
    """)
    assert rule._check_abstract_parent(cls, "do_work") is False


def test_abstract_parent_with_docstring(rule: DocstringCoverageRule) -> None:
    """Abstract parent with docstring → returns True."""
    cls = _parse_class("""
        class Base:
            @abstractmethod
            def do_work(self):
                \"\"\"Do the work.\"\"\"
                pass
    """)
    assert rule._check_abstract_parent(cls, "do_work") is True


# --- Edge cases ---


def test_empty_class_body(rule: DocstringCoverageRule) -> None:
    """Base class with no methods → returns False."""
    cls = _parse_class("""
        class Empty:
            pass
    """)
    assert rule._check_abstract_parent(cls, "anything") is False


def test_method_name_matches_but_not_abstract(rule: DocstringCoverageRule) -> None:
    """Same name but no @abstractmethod decorator → returns False."""
    cls = _parse_class("""
        class Base:
            def do_work(self):
                \"\"\"Documented but not abstract.\"\"\"
                pass
    """)
    assert rule._check_abstract_parent(cls, "do_work") is False


def test_async_abstractmethod(rule: DocstringCoverageRule) -> None:
    """async def with @abstractmethod and docstring → correctly identified."""
    cls = _parse_class("""
        class Base:
            @abstractmethod
            async def fetch(self):
                \"\"\"Fetch data.\"\"\"
                pass
    """)
    assert rule._check_abstract_parent(cls, "fetch") is True
