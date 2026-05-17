"""Split from ``test_parser.py``."""

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file


class TestParseFileIntegration:
    """Tests for parse_file() — real filesystem I/O via tmp_path."""

    def test_not_python_file(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Not a Python file"):
            parse_file(txt)
