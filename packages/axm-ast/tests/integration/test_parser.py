from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.parser import parse_file

pytestmark = pytest.mark.integration


def test_parse_file_non_utf8_does_not_leak_unicodedecodeerror(tmp_path: Path) -> None:
    """AC1: a non-UTF-8 file is parsed best-effort, never leaking UnicodeDecodeError.

    Contract chosen: graceful decode with ``errors="replace"``. The undecodable
    bytes are replaced and the file still parses to a tree-sitter Tree.
    """
    py_file = tmp_path / "latin1.py"
    # 0xFF is not a valid standalone UTF-8 byte; raw read_text(encoding="utf-8")
    # would raise UnicodeDecodeError.
    py_file.write_bytes(b"x = 'caf\xe9'  # \xff invalid utf-8\n")

    tree = parse_file(py_file)

    assert tree.root_node.type == "module"


def test_parse_file_valid_utf8_unchanged(tmp_path: Path) -> None:
    """AC3: a valid UTF-8 source file parses to the expected Tree, as before."""
    py_file = tmp_path / "valid.py"
    py_file.write_text("def greet() -> str:\n    return 'café'\n", encoding="utf-8")

    tree = parse_file(py_file)

    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error
