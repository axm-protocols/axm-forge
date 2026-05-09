from __future__ import annotations

import ast
from pathlib import Path

import pytest
from radon.complexity import cc_visit

from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality._shared import analyze_imports


@pytest.fixture
def shared_source() -> str:
    return Path(_shared.__file__).read_text()


def test_analyze_imports_cc_within_budget(shared_source: str) -> None:
    by_name = {f.name: f.complexity for f in cc_visit(shared_source)}
    assert "analyze_imports" in by_name, "analyze_imports must be defined in _shared"
    assert by_name["analyze_imports"] <= 10, (
        f"analyze_imports CC={by_name['analyze_imports']} exceeds budget of 10"
    )


def test_analyze_imports_signature_stable(tmp_path: Path) -> None:
    code = (
        "import os\n"
        "import subprocess\n"
        "from mypkg import foo\n"
        "from mypkg.sub import bar\n"
        "from mypkg._internal import hidden\n"
    )
    tree = ast.parse(code)

    result = analyze_imports(tree, {"mypkg"}, None, tmp_path)

    assert isinstance(result, tuple)
    assert len(result) == 6

    public, internal, modules, has_private, io_modules, io_signals = result
    assert isinstance(public, list)
    assert all(isinstance(s, str) for s in public)
    assert isinstance(internal, list)
    assert all(isinstance(s, str) for s in internal)
    assert isinstance(modules, list)
    assert all(isinstance(s, str) for s in modules)
    assert isinstance(has_private, bool)
    assert isinstance(io_modules, set)
    assert all(isinstance(s, str) for s in io_modules)
    assert isinstance(io_signals, list)
    assert all(isinstance(s, str) for s in io_signals)


def test_extracted_helpers_within_budget(shared_source: str) -> None:
    over_budget = [
        (f.name, f.complexity) for f in cc_visit(shared_source) if f.complexity > 10
    ]
    assert not over_budget, (
        f"Functions in _shared exceed CC budget of 10: {over_budget}"
    )
