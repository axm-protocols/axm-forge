from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule
from axm_audit.models.results import AuditResult, CheckResult, Severity


@pytest.fixture
def rule() -> DocstringCoverageRule:
    return DocstringCoverageRule()


class TestDocstringCoverageRuleUnit:
    """Tests for DocstringCoverageRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_DOCSTRING."""
        rule = DocstringCoverageRule()
        assert rule.rule_id == "PRACTICE_DOCSTRING"


def test_docstring_coverage_rule_registered(registry: dict[str, list[type]]) -> None:
    """DocstringCoverageRule must be registered in the practices bucket."""
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert "DocstringCoverageRule" in names


class TestFormatAgentActionable:
    """Tests for format_agent surfacing details on PRACTICE_DOCSTRING checks."""

    def test_passed_with_missing_includes_details(self) -> None:
        """Passed check with missing docstrings includes full details."""
        from axm_audit.formatters import format_agent

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 88% (7/8)",
            severity=Severity.INFO,
            details={
                "coverage": 0.88,
                "total": 8,
                "documented": 7,
                "missing": ["mod.py:foo"],
            },
            fix_hint="Add docstrings to public functions",
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        # Passed entry should be a dict with details, not a plain string
        assert len(output["passed"]) == 1
        entry = output["passed"][0]
        assert isinstance(entry, dict)
        assert entry["details"]["missing"] == ["mod.py:foo"]

    def test_passed_clean_is_string(self) -> None:
        """Passed check with no actionable items stays as summary string."""
        from axm_audit.formatters import format_agent

        check = CheckResult(
            rule_id="QUALITY_TYPE",
            passed=True,
            message="Type score: 100/100",
            severity=Severity.INFO,
            score=100,
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)

    def test_passed_empty_missing_is_string(self) -> None:
        """Passed check with empty missing list stays as summary string."""
        from axm_audit.formatters import format_agent

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 100% (8/8)",
            severity=Severity.INFO,
            details={"coverage": 1.0, "total": 8, "documented": 8, "missing": []},
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)


class TestDocstringTextRendering:
    """Tests for _build_result text= output (AXM-1395)."""

    def test_docstring_text_with_missing(self, rule: DocstringCoverageRule) -> None:
        """Passed with 6 missing across 3 modules -> 3 grouped bullet lines."""
        missing = [
            "core.py:process_data",
            "core.py:validate_input",
            "utils.py:format_output",
            "utils.py:parse_config",
            "helpers.py:build_key",
            "helpers.py:load_data",
        ]
        result = rule._build_result(documented=44, missing=missing)

        assert result.passed is True
        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 3
        for line in lines:
            assert line.startswith("     • ")
        assert "core.py: process_data, validate_input" in result.text
        assert "utils.py: format_output, parse_config" in result.text
        assert "helpers.py: build_key, load_data" in result.text
        # AC3: details dict unchanged
        assert result.details is not None
        assert result.details["missing"] == missing
        assert result.details["coverage"] == 0.88
        assert result.details["total"] == 50
        assert result.details["documented"] == 44
        assert result.score == 88

    def test_docstring_text_perfect(self, rule: DocstringCoverageRule) -> None:
        """100% coverage -> text is None."""
        result = rule._build_result(documented=10, missing=[])

        assert result.passed is True
        assert result.text is None
        # AC3: details dict unchanged
        assert result.details is not None
        assert result.details["missing"] == []
        assert result.score == 100

    def test_docstring_text_failed(self, rule: DocstringCoverageRule) -> None:
        """Below threshold, 12 missing across 4 files.

        Grouped bullets, passed False.
        """
        missing = [
            "mod_a.py:f1",
            "mod_a.py:f2",
            "mod_a.py:f3",
            "mod_b.py:f4",
            "mod_b.py:f5",
            "mod_b.py:f6",
            "mod_c.py:f7",
            "mod_c.py:f8",
            "mod_c.py:f9",
            "mod_d.py:f10",
            "mod_d.py:f11",
            "mod_d.py:f12",
        ]
        result = rule._build_result(documented=3, missing=missing)

        assert result.passed is False
        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 4
        for line in lines:
            assert line.startswith("     • ")
        assert "mod_a.py: f1, f2, f3" in result.text
        assert "mod_b.py: f4, f5, f6" in result.text
        assert "mod_c.py: f7, f8, f9" in result.text
        assert "mod_d.py: f10, f11, f12" in result.text

    # --- Edge cases ---

    def test_docstring_text_single_file_single_missing(
        self, rule: DocstringCoverageRule
    ) -> None:
        """Single missing func in one file -> one bullet line."""
        result = rule._build_result(documented=9, missing=["file.py:func_name"])

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 1
        assert lines[0] == "     • file.py: func_name"

    def test_docstring_text_nested_path(self, rule: DocstringCoverageRule) -> None:
        """Nested path uses full relative path as grouping key."""
        missing = [
            "pkg/sub/module.py:func_a",
            "pkg/sub/module.py:func_b",
        ]
        result = rule._build_result(documented=8, missing=missing)

        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 1
        assert "pkg/sub/module.py: func_a, func_b" in lines[0]


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


@pytest.mark.parametrize(
    ("source", "method", "expected"),
    [
        pytest.param(
            """
            class Base:
                @abstractmethod
                def do_work(self):
                    pass
            """,
            "do_work",
            False,
            id="abstract_no_parent_docstring",
        ),
        pytest.param(
            """
            class Base:
                @abstractmethod
                def do_work(self):
                    \"\"\"Do the work.\"\"\"
                    pass
            """,
            "do_work",
            True,
            id="abstract_parent_with_docstring",
        ),
        pytest.param(
            """
            class Empty:
                pass
            """,
            "anything",
            False,
            id="empty_class_body",
        ),
        pytest.param(
            """
            class Base:
                def do_work(self):
                    \"\"\"Documented but not abstract.\"\"\"
                    pass
            """,
            "do_work",
            False,
            id="method_name_matches_but_not_abstract",
        ),
        pytest.param(
            """
            class Base:
                @abstractmethod
                async def fetch(self):
                    \"\"\"Fetch data.\"\"\"
                    pass
            """,
            "fetch",
            True,
            id="async_abstractmethod",
        ),
    ],
)
def test_check_abstract_parent(
    rule: DocstringCoverageRule, source: str, method: str, expected: bool
) -> None:
    """_check_abstract_parent: True iff parent has @abstractmethod and docstring."""
    cls = _parse_class(source)
    assert rule._check_abstract_parent(cls, method) is expected


def _parse_class(source: str) -> ast.ClassDef:
    """Parse a single class definition from source text."""
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    msg = "No ClassDef found"
    raise ValueError(msg)
