"""Integration: predicate over symbols from real axm-ast extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import analyze_package
from axm_ast.doc_policy import is_documentation_required


@pytest.mark.integration
def test_predicate_reads_docstrings_via_real_extraction(tmp_path: Path) -> None:
    """AC1: docstringed publics are documented, docstring-less publics are gaps."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n', encoding="utf-8")
    (pkg / "mod.py").write_text(
        '"""Module."""\n'
        "def documented() -> int:\n"
        '    """Has a docstring."""\n'
        "    return 1\n\n"
        "def undocumented() -> int:\n"
        "    return 2\n\n"
        "def _private() -> int:\n"
        "    return 3\n",
        encoding="utf-8",
    )

    package = analyze_package(pkg)
    funcs = {f.name: f for m in package.modules for f in m.functions}

    assert is_documentation_required(funcs["documented"]) is False
    assert is_documentation_required(funcs["undocumented"]) is True
    assert is_documentation_required(funcs["_private"]) is False
