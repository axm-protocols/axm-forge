"""Unit tests for parse_source/parse_file (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


class TestParseFileUnit:
    """Tests for parse_file() — pure, no real I/O."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_broken_file(self) -> None:
        """Broken syntax should still parse (graceful degradation)."""
        tree = parse_file(FIXTURES / "broken.py")
        assert tree.root_node.has_error is True
