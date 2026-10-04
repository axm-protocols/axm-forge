"""Unit tests for axm_edit.core.syntax_gate (pure, no I/O)."""

from __future__ import annotations

import json

import pytest
from pytest_mock import MockerFixture

from axm_edit.core import syntax_gate
from axm_edit.core.syntax_gate import syntax_regression

VALID = "def f():\n    return 1\n"
BROKEN = "def f():\n    return (1\n"


class TestSyntaxRegression:
    """A batch may not turn parseable Python into unparseable Python."""

    def test_valid_after_content_passes(self) -> None:
        """A file that still parses after the batch is accepted."""
        assert syntax_regression("mod.py", VALID, VALID.replace("1", "2")) is None

    def test_regression_names_the_file_and_line(self) -> None:
        """Parseable before, unparseable after: refused with a location."""
        error = syntax_regression("pkg/mod.py", VALID, BROKEN)

        assert error is not None
        assert error.file == "pkg/mod.py"
        assert error.line is not None
        assert error.error is not None
        assert "break Python syntax" in error.error

    def test_unbalanced_docstring_is_refused(self) -> None:
        """The docstring-pairing risk the old triple-quote rule targeted."""
        after = 'def f():\n    """Doc.\n    return 1\n'

        error = syntax_regression("mod.py", VALID, after)

        assert error is not None
        assert error.line == 2

    def test_new_python_file_must_parse(self) -> None:
        """A created file has no prior state and must parse."""
        error = syntax_regression("new.py", None, BROKEN)

        assert error is not None
        assert error.file == "new.py"

    def test_already_broken_file_is_not_blocked(self) -> None:
        """An edit on a file that did not parse before stays possible."""
        assert syntax_regression("mod.py", BROKEN, BROKEN + "x = 1\n") is None

    def test_stub_files_are_checked(self) -> None:
        """``.pyi`` stubs are Python too."""
        error = syntax_regression("mod.pyi", VALID, BROKEN)

        assert error is not None
        assert error.file == "mod.pyi"

    def test_non_python_files_are_ignored(self) -> None:
        """Only Python suffixes are parsed."""
        assert syntax_regression("notes.md", VALID, BROKEN) is None

    def test_null_byte_is_reported_without_a_line(self) -> None:
        """A null byte fails the parse with a ValueError, still refused."""
        error = syntax_regression("mod.py", VALID, "x = 1\x00\n")

        assert error is not None
        assert error.error is not None


class TestDataSyntaxRegression:
    """Data formats guard regressions while respecting JSON dialects."""

    def test_module_docstring(self) -> None:
        """The syntax gate exposes its informative module documentation."""
        from axm_edit.core import syntax_gate

        assert syntax_gate.__doc__
        assert "both in memory" in syntax_gate.__doc__
        assert "at least as recent" in syntax_gate.__doc__

    def test_python_message_unchanged(self) -> None:
        """The Python regression diagnostic remains byte-identical."""
        error = syntax_regression("m.py", "x = 1\n", "x = (1\n")
        assert error is not None
        assert error.error == (
            "Batch would break Python syntax at line 1: '(' was never closed. "
            "Nothing was written; check the quote and bracket pairing of `new`."
        )

    def test_python_null_byte_message_unchanged(self) -> None:
        """The Python null-byte diagnostic remains byte-identical."""
        error = syntax_regression("m.py", "x = 1\n", "x = 1\x00\n")
        assert error is not None
        assert error.error == (
            "Batch would break Python syntax: source code string cannot contain "
            "null bytes. Nothing was written; check the quote and bracket "
            "pairing of `new`."
        )

    def test_toml_regression(self) -> None:
        """Broken TOML is refused with its source line."""
        error = syntax_regression("pyproject.toml", 'name = "ok"\n', 'name = "bad\n')
        assert error is not None
        assert error.file == "pyproject.toml"
        assert error.line == 1
        assert "break TOML syntax at line 1" in (error.error or "")

    def test_json_regression(self) -> None:
        """Broken JSON is refused with its source line."""
        error = syntax_regression("settings.json", '{"x": 1}', '{\n"x": }')
        assert error is not None
        assert error.file == "settings.json"
        assert error.line == 2
        assert "break JSON syntax at line 2" in (error.error or "")

    @pytest.mark.parametrize(
        ("filename", "before", "after"),
        [("a.toml", "x = 1", "x = 2"), ("a.json", '{"x": 1}', '{"x": 2}')],
    )
    def test_valid_edit(self, filename: str, before: str, after: str) -> None:
        """Valid edits remain allowed for each data format."""
        assert syntax_regression(filename, before, after) is None

    @pytest.mark.parametrize(
        ("filename", "before", "after"),
        [("a.toml", "x =", "y ="), ("a.json", '{"x": }', '{"y": }')],
    )
    def test_broken_file_remains_editable(
        self, filename: str, before: str, after: str
    ) -> None:
        """Already-broken files remain editable."""
        assert syntax_regression(filename, before, after) is None

    def test_new_valid_toml(self) -> None:
        """New valid TOML is accepted."""
        assert syntax_regression("a.toml", None, "x = 1") is None

    def test_new_broken_toml(self) -> None:
        """New broken TOML is refused."""
        error = syntax_regression("a.toml", None, "x =")

        assert error is not None
        assert error.file == "a.toml"
        assert "break TOML syntax" in (error.error or "")

    def test_new_json_unchecked(self) -> None:
        """New JSON remains unchecked even when broken."""
        assert syntax_regression("a.json", None, '{"x": }') is None

    @pytest.mark.parametrize(
        ("filename", "valid", "prefix"),
        [("a.json", "[]", ""), ("a.toml", "x = []", "x = ")],
    )
    @pytest.mark.parametrize("side", ["before", "after"])
    def test_recursion_limit(
        self, filename: str, valid: str, prefix: str, side: str
    ) -> None:
        """Parser recursion limits on either side never crash or refuse."""
        deep = prefix + "[" * 200000 + "]" * 200000
        before, after = (deep, valid) if side == "before" else (valid, deep)
        assert syntax_regression(filename, before, after) is None

    def test_json_to_jsonc(self) -> None:
        """Adding the first comment to strict JSON is allowed."""
        assert syntax_regression("tsconfig.json", "{}", "// c\n{}") is None

    def test_json_comments_remain_editable(self) -> None:
        """Valid JSONC can become different valid JSONC."""
        assert syntax_regression("tsconfig.json", "// old\n{}", "// new\n{}") is None

    @pytest.mark.parametrize("after", ['// c\n{\n"x": }', '// c\n{\n"x": 1'])
    def test_jsonc_to_broken(self, after: str) -> None:
        """Missing values and unclosed braces in JSONC are refused."""
        error = syntax_regression("tsconfig.json", "// c\n{}", after)
        assert error is not None
        assert error.line == 3
        assert "break JSON syntax at line 3" in (error.error or "")

    def test_markers_inside_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Comment markers and comma delimiters inside strings stay intact."""
        observed: list[str] = []
        loads = json.loads

        def capture(source: str) -> object:
            """Record exactly what the scanner passes to the JSON parser."""
            observed.append(source)
            return loads(source)

        monkeypatch.setattr(json, "loads", capture)
        after = r'{"text": "// /* */ ,} ,] \" //"}'
        assert syntax_regression("a.json", "{}", after) is None
        assert observed == ["{}", after]

    def test_escaped_backslash_before_closing_quote(self) -> None:
        """An escaped backslash does not hide the closing quote."""
        after = r'{"text": "\\", // comment' + '\n"value": 1,}'
        assert syntax_regression("a.json", "{}", after) is None

    @pytest.mark.parametrize("after", ['{"x": 1,}', "[1,]", '{"x": [1,], /* c */}'])
    def test_trailing_comma(self, after: str) -> None:
        """Trailing commas in objects and arrays are tolerated."""
        assert syntax_regression("a.json", "{}", after) is None

    def test_multiline_block_comment_line(self) -> None:
        """Blanking a multiline comment preserves a later error location."""
        after = '{\n/* comment\nstill comment */\n"x":\n}'
        error = syntax_regression("a.json", "{}", after)
        assert error is not None
        assert error.line == 5
        assert "break JSON syntax at line 5" in (error.error or "")

    def test_unclosed_block_comment(self) -> None:
        """An unclosed block comment is refused rather than silently removed."""
        error = syntax_regression("a.json", "{}", "{} /* unfinished")

        assert error is not None
        assert error.line == 1
        assert "break JSON syntax at line 1" in (error.error or "")

    def test_comment_cannot_join_tokens(self) -> None:
        """Blanking comments cannot turn separate number tokens into one."""
        error = syntax_regression("a.json", "{}", '{"x": 1/* c */2}')

        assert error is not None
        assert error.line == 1
        assert "break JSON syntax at line 1" in (error.error or "")

    @pytest.mark.parametrize(
        "filename", ["a.md", "a.yaml", "a.ts", "a", "a.JSON", "a.TOML"]
    )
    def test_unsupported_suffix(self, filename: str) -> None:
        """Unsupported suffixes remain unchecked."""
        assert syntax_regression(filename, "x = 1", "x =") is None

    def test_toml_end_of_input(self) -> None:
        """TOML errors without a reported line still produce a refusal."""
        error = syntax_regression("a.toml", "x = 1", "x =")
        assert error is not None
        assert "break TOML syntax" in (error.error or "")

    def test_strict_json_skips_the_tolerant_scan(self, mocker: MockerFixture) -> None:
        """Strict JSON never pays for the pure-Python comment scanner."""
        scan = mocker.spy(syntax_gate, "_blank_comments")

        assert syntax_regression("a.json", '{"x": 1}', '{"x": 2}') is None
        assert scan.call_count == 0

    def test_commented_json_uses_the_tolerant_scan(self, mocker: MockerFixture) -> None:
        """A strict failure falls back to the comment-tolerant view."""
        scan = mocker.spy(syntax_gate, "_blank_comments")

        assert syntax_regression("a.json", "{}", "// c\n{}") is None
        assert scan.call_count == 1
