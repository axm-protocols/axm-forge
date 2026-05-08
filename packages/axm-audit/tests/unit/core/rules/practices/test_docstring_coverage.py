from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule


@pytest.fixture
def rule() -> DocstringCoverageRule:
    return DocstringCoverageRule()


class TestIsAbstractOverrideEdgeCases:
    """Edge-case tests for _is_abstract_override."""

    def test_no_enclosing_class_returns_false(
        self, rule: DocstringCoverageRule
    ) -> None:
        """Free function not inside any class returns False."""
        source = textwrap.dedent("""\
            def free_function():
                pass
        """)
        tree = ast.parse(source)
        func_node = tree.body[0]
        assert isinstance(func_node, ast.FunctionDef)
        class_map: dict[str, ast.ClassDef] = {}

        result = rule._is_abstract_override(func_node, class_map)

        assert result is False

    def test_ambiguous_cross_file_name_skipped(
        self, rule: DocstringCoverageRule
    ) -> None:
        """global_classes[name] has >1 definition, conservative skip."""
        source = textwrap.dedent("""\
            class Child(Base):
                def method(self):
                    pass
        """)
        tree = ast.parse(source)
        child_cls = tree.body[0]
        assert isinstance(child_cls, ast.ClassDef)
        method_node = child_cls.body[0]
        assert isinstance(method_node, ast.FunctionDef)
        class_map: dict[str, ast.ClassDef] = {"Child": child_cls}

        # Two ambiguous definitions for Base — both valid abstract parents
        base1_src = textwrap.dedent("""\
            from abc import abstractmethod

            class Base:
                @abstractmethod
                def method(self):
                    \"\"\"Documented.\"\"\"\n
        """)
        base2_src = textwrap.dedent("""\
            from abc import abstractmethod

            class Base:
                @abstractmethod
                def method(self):
                    \"\"\"Documented.\"\"\"\n
        """)
        base1_cls = ast.parse(base1_src).body[1]
        assert isinstance(base1_cls, ast.ClassDef)
        base2_cls = ast.parse(base2_src).body[1]
        assert isinstance(base2_cls, ast.ClassDef)

        global_classes: dict[str, list[ast.ClassDef]] = {"Base": [base1_cls, base2_cls]}

        result = rule._is_abstract_override(method_node, class_map, global_classes)

        assert result is False

    def test_base_with_dotted_attribute_skipped(
        self, rule: DocstringCoverageRule
    ) -> None:
        """class Foo(mod.Base) — base_name is None via ast.Attribute, skipped."""
        source = textwrap.dedent("""\
            class Foo(mod.Base):
                def method(self):
                    pass
        """)
        tree = ast.parse(source)
        foo_cls = tree.body[0]
        assert isinstance(foo_cls, ast.ClassDef)
        method_node = foo_cls.body[0]
        assert isinstance(method_node, ast.FunctionDef)
        class_map: dict[str, ast.ClassDef] = {"Foo": foo_cls}

        result = rule._is_abstract_override(method_node, class_map)

        assert result is False


def _parse_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Parse a single function definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node
    msg = "No function found in source"
    raise ValueError(msg)


class TestHasAbstractmethodDecorator:
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
    def testhas_abstractmethod_decorator(self, source: str, expected: bool) -> None:
        """has_abstractmethod_decorator detects @abstractmethod."""
        # Also detects @abc.abstractmethod (qualified form).
        node = _parse_func(source)
        assert DocstringCoverageRule.has_abstractmethod_decorator(node) is expected


class TestIsStubBody:
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
    def testis_stub_body(self, source: str, expected: bool) -> None:
        """is_stub_body True only for `...` or `pass` single-statement bodies."""
        node = _parse_func(source)
        assert DocstringCoverageRule.is_stub_body(node) is expected


class TestIsAbstractStubEdgeCases:
    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(
                """
                @abstractmethod
                def foo(self):
                    return 42
                """,
                id="abstract_with_real_body",
            ),
            pytest.param(
                """
                def foo(self): ...
                """,
                id="non_abstract_ellipsis",
            ),
        ],
    )
    def test_is_abstract_stub_edge_cases_not_stub(self, source: str) -> None:
        """False unless BOTH @abstractmethod AND a stub body are present."""
        node = _parse_func(source)
        assert DocstringCoverageRule.is_abstract_stub(node) is False


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


def _parse_class(source: str) -> ast.ClassDef:
    """Parse a single class definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    msg = "No ClassDef found"
    raise ValueError(msg)
