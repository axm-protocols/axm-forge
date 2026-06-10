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

    @pytest.mark.integration
    def test_parse_file_non_utf8_does_not_leak_unicodedecodeerror(
        self, tmp_path: Path
    ) -> None:
        """AC1: non-UTF-8 parses best-effort without UnicodeDecodeError.

        Contract chosen: graceful decode with ``errors="replace"``. The undecodable
        bytes are replaced and the file still parses to a tree-sitter Tree.
        """
        py_file = tmp_path / "latin1.py"
        # 0xFF is not a valid standalone UTF-8 byte; raw read_text(encoding="utf-8")
        # would raise UnicodeDecodeError.
        py_file.write_bytes(b"x = 'caf\xe9'  # \xff invalid utf-8\n")

        tree = parse_file(py_file)

        assert tree.root_node.type == "module"

    @pytest.mark.integration
    def test_parse_file_valid_utf8_unchanged(self, tmp_path: Path) -> None:
        """AC3: a valid UTF-8 source file parses to the expected Tree, as before."""
        py_file = tmp_path / "valid.py"
        py_file.write_text("def greet() -> str:\n    return 'café'\n", encoding="utf-8")

        tree = parse_file(py_file)

        assert tree.root_node.type == "module"
        assert not tree.root_node.has_error
