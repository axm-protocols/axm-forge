"""Tests for axm_ast.docstring_parser."""

from __future__ import annotations

from pathlib import Path

from axm_ast.docstring_parser import ParsedDocstring, parse_docstring

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── Unit tests — parse_docstring ────────────────────────────────────────────


class TestParseDocstringGoogle:
    """Unit tests for Google-style docstrings."""

    def test_summary_only(self) -> None:
        """Simple one-liner docstring."""
        result = parse_docstring("Return the answer.")
        assert result.summary == "Return the answer."
        assert result.raises == []
        assert result.examples == []

    def test_google_style_summary(self) -> None:
        """Multi-paragraph Google docstring: summary is first paragraph."""
        doc = """Analyze a Python package directory.

        Does a lot of things.

        Args:
            path: Path to the package root directory.

        Returns:
            PackageInfo with all modules.
        """
        result = parse_docstring(doc)
        assert result.summary == "Analyze a Python package directory."
        assert result.raises == []

    def test_google_style_raises_single(self) -> None:
        """Single Raises entry parsed correctly."""
        doc = """Do something.

        Raises:
            ValueError: If path is not a directory.
        """
        result = parse_docstring(doc)
        assert len(result.raises) == 1
        assert result.raises[0][0] == "ValueError"
        assert "not a directory" in result.raises[0][1]

    def test_google_style_raises_multiple(self) -> None:
        """Multiple Raises entries parsed correctly."""
        doc = """Do something.

        Raises:
            ValueError: If path is bad.
            TypeError: If arg is wrong type.
            RuntimeError: If something fails.
        """
        result = parse_docstring(doc)
        assert len(result.raises) == 3
        types = [r[0] for r in result.raises]
        assert "ValueError" in types
        assert "TypeError" in types
        assert "RuntimeError" in types

    def test_google_style_examples(self) -> None:
        """Examples section parsed and included."""
        doc = """Do something.

        Example:
            >>> foo(1)
            2
        """
        result = parse_docstring(doc)
        assert len(result.examples) == 1
        assert "foo(1)" in result.examples[0]

    def test_args_not_in_output(self) -> None:
        """Args section is deliberately not exposed."""
        doc = """Do something.

        Args:
            path: The path.
            count: The count.
        """
        result = parse_docstring(doc)
        # Should have summary, but no args field
        assert result.summary == "Do something."
        assert not hasattr(result, "args")

    def test_returns_not_in_output(self) -> None:
        """Returns section is deliberately not exposed."""
        doc = """Do something.

        Returns:
            str: A string.
        """
        result = parse_docstring(doc)
        assert not hasattr(result, "returns")


class TestParseDocstringSphinx:
    """Unit tests for Sphinx-style docstrings."""

    def test_sphinx_raises(self) -> None:
        """Sphinx :raises ExcType: description parsed correctly."""
        doc = """Do something.

        :raises ValueError: If path is bad.
        :raises TypeError: Wrong type.
        """
        result = parse_docstring(doc)
        assert len(result.raises) == 2
        assert result.raises[0] == ("ValueError", "If path is bad.")
        assert result.raises[1] == ("TypeError", "Wrong type.")

    def test_sphinx_summary(self) -> None:
        """Sphinx docstring summary extracted."""
        doc = """Return the answer.

        :raises ValueError: bad.
        """
        result = parse_docstring(doc)
        assert result.summary == "Return the answer."


class TestParseDocstringNumpy:
    """Unit tests for NumPy-style docstrings."""

    def test_numpy_raises(self) -> None:
        """NumPy-style Raises section parsed correctly."""
        doc = """Do something.

        Raises
        ------
        ValueError
            If path is bad.
        """
        result = parse_docstring(doc)
        assert len(result.raises) >= 1
        assert result.raises[0][0] == "ValueError"

    def test_numpy_examples(self) -> None:
        """NumPy-style Examples section parsed."""
        doc = """Do something.

        Examples
        --------
        >>> foo(1)
        2
        """
        result = parse_docstring(doc)
        assert len(result.examples) == 1
        assert "foo(1)" in result.examples[0]


class TestParseDocstringEdgeCases:
    """Edge case tests for parse_docstring."""

    def test_none_input(self) -> None:
        """None input returns empty ParsedDocstring."""
        result = parse_docstring(None)
        assert isinstance(result, ParsedDocstring)
        assert result.summary is None
        assert result.raises == []
        assert result.examples == []

    def test_empty_string(self) -> None:
        """Empty string input returns empty ParsedDocstring."""
        result = parse_docstring("")
        assert result.summary is None
        assert result.raises == []

    def test_multiline_summary(self) -> None:
        """First multi-line paragraph is the summary."""
        doc = """Line one.
        Line two still in first paragraph.

        Raises:
            ValueError: bad.
        """
        result = parse_docstring(doc)
        assert "Line one" in result.summary  # type: ignore[operator]
        # Two lines joined
        assert result.summary is not None

    def test_unknown_section_ignored(self) -> None:
        """Unknown sections are silently ignored."""
        doc = """Summary.

        Note:
            Something to note.
        """
        result = parse_docstring(doc)
        assert result.summary == "Summary."
        # No crash, no unknown attrs
        assert result.raises == []
        assert result.examples == []

    def test_indented_docstring(self) -> None:
        """Indented docstrings are normalised correctly."""
        doc = """
            Summary line.

            Raises:
                ValueError: oops.
        """
        result = parse_docstring(doc)
        assert result.summary == "Summary line."
        assert result.raises[0][0] == "ValueError"


class TestFormatJsonDocstringIntegration:
    """Integration tests: docstring parsing flows through format_json."""

    def test_detailed_has_summary_field(self) -> None:
        from axm_ast.core.analyzer import analyze_package
        from axm_ast.formatters import format_json

        pkg = analyze_package(SAMPLE_PKG)
        data = format_json(pkg, detail="detailed")
        for mod in data["modules"]:
            for fn in mod.get("functions", []):
                assert "summary" in fn, f"summary missing from {fn['name']}"

    def test_detailed_no_raw_docstring_field(self) -> None:
        from axm_ast.core.analyzer import analyze_package
        from axm_ast.formatters import format_json

        pkg = analyze_package(SAMPLE_PKG)
        data = format_json(pkg, detail="detailed")
        for mod in data["modules"]:
            for fn in mod.get("functions", []):
                assert "docstring" not in fn, (
                    f"raw docstring still present in {fn['name']}"
                )

    def test_full_raises_is_list(self) -> None:
        from axm_ast.core.analyzer import analyze_package
        from axm_ast.formatters import format_json

        pkg = analyze_package(SAMPLE_PKG)
        data = format_json(pkg, detail="full")
        for mod in data["modules"]:
            for fn in mod.get("functions", []):
                assert isinstance(fn.get("raises"), list), (
                    f"raises is not a list in {fn['name']}"
                )

    def test_summary_mode_unchanged(self) -> None:
        """Summary mode should not include summary/raises/examples."""
        from axm_ast.core.analyzer import analyze_package
        from axm_ast.formatters import format_json

        pkg = analyze_package(SAMPLE_PKG)
        data = format_json(pkg, detail="summary")
        for mod in data["modules"]:
            for fn in mod.get("functions", []):
                assert "summary" not in fn
                assert "docstring" not in fn
