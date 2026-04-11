from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.practices import DocstringCoverageRule


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
