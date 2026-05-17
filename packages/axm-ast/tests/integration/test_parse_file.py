"""Split from ``test_parser.py``."""

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class TestParseFile:
    """Tests for parse_file()."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_not_python_file(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Not a Python file"):
            parse_file(txt)

    def test_broken_file(self) -> None:
        """Broken syntax should still parse (graceful degradation)."""
        tree = parse_file(FIXTURES / "broken.py")
        assert tree.root_node.has_error is True
