"""Unit tests for axm_ast.core.parser — parse_source, parse_file.

All tests are pure / no real I/O (parse_source operates on in-memory
strings; parse_file only touches small static fixtures).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file, parse_source

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ────────────────────────────────────────────────────────────────────────────
# parse_source
# ────────────────────────────────────────────────────────────────────────────


class TestParseSource:
    """Tests for parse_source()."""

    def test_syntax_error_graceful(self) -> None:
        """Tree-sitter should parse even with syntax errors."""
        tree = parse_source("def broken(")
        assert tree.root_node.has_error is True


# ────────────────────────────────────────────────────────────────────────────
# parse_file
# ────────────────────────────────────────────────────────────────────────────


class TestParseFileUnit:
    """Tests for parse_file() — pure, no real I/O."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_broken_file(self) -> None:
        """Broken syntax should still parse (graceful degradation)."""
        tree = parse_file(FIXTURES / "broken.py")
        assert tree.root_node.has_error is True
