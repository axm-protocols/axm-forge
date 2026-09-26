"""Unit tests for axm_edit.core.syntax_gate (pure, no I/O)."""

from __future__ import annotations

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
