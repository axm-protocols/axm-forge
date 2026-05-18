"""Split from ``test_shared_helpers_io.py``."""

import ast
import textwrap
from pathlib import Path

from axm_audit.core.rules.test_quality._shared import (
    test_is_in_lazy_import_context as is_in_lazy_import_context,
)


def _find_func(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise LookupError(name)


def test_lazy_import_context_filename(tmp_path: Path) -> None:
    test_file = tmp_path / "test_init.py"
    code = "def test_x(): pass\n"
    test_file.write_text(code)
    tree = ast.parse(code)
    func = _find_func(tree, "test_x")
    assert is_in_lazy_import_context(func, tree, test_file) is True


def test_lazy_import_context_docstring_getattr(tmp_path: Path) -> None:
    test_file = tmp_path / "test_thing.py"
    code = textwrap.dedent('''
        """This module tests __getattr__ lazy import behavior."""

        def test_x(): pass
    ''')
    test_file.write_text(code)
    tree = ast.parse(code)
    func = _find_func(tree, "test_x")
    assert is_in_lazy_import_context(func, tree, test_file) is True
