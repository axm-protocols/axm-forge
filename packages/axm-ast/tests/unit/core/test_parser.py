"""Unit tests for parse_file defensive validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file


class TestParseFileValidation:
    """Defensive guards on parse_file inputs."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_not_python_file(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Not a Python file"):
            parse_file(txt)
