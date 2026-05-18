"""Tests for _helpers module — get_python_files() and parse_file_safe()."""

from __future__ import annotations

from pathlib import Path


class TestParseFileSafe:
    """Tests for parse_file_safe()."""

    def test_valid_python(self, tmp_path: Path) -> None:
        """Valid Python file returns an ast.Module containing the parsed assignment."""
        import ast

        from axm_audit.core.rules._helpers import parse_file_safe

        f = tmp_path / "good.py"
        f.write_text("x = 1\n")
        result = parse_file_safe(f)
        assert isinstance(result, ast.Module)
        assert any(isinstance(n, ast.Assign) for n in result.body)

    def test_syntax_error(self, tmp_path: Path) -> None:
        """File with syntax errors returns None."""
        from axm_audit.core.rules._helpers import parse_file_safe

        f = tmp_path / "bad.py"
        f.write_text("def broken(\n")
        assert parse_file_safe(f) is None

    def test_binary_file(self, tmp_path: Path) -> None:
        """Binary (non-UTF-8) file returns None without crash."""
        from axm_audit.core.rules._helpers import parse_file_safe

        f = tmp_path / "binary.py"
        f.write_bytes(b"\x80\x81\x82\x83")
        assert parse_file_safe(f) is None
