"""Integration tests for test_quality._shared (real I/O on tmp_path)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from radon.complexity import cc_visit

from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality._shared import (
    analyze_imports,
)


def test_analyze_imports_io_module_names(tmp_path: Path) -> None:
    tree = ast.parse("import httpx as hx\n")
    _public, _internal, _modules, _has_private, io_module_names, io_signals = (
        analyze_imports(tree, set(), None, tmp_path)
    )
    assert "hx" in io_module_names
    assert any("httpx" in s for s in io_signals)


def test_analyze_imports_public_vs_internal(tmp_path: Path) -> None:
    tree = ast.parse("from pkg import Foo, _Bar\n")
    public, internal, _modules, has_private, _io_names, _io_signals = analyze_imports(
        tree, {"pkg"}, {"Foo"}, tmp_path
    )
    assert "Foo" in public
    assert "_Bar" in internal
    assert has_private is True


def test_io_match_shortcircuits_pkg(tmp_path: Path) -> None:
    (tmp_path / "src" / "subprocess").mkdir(parents=True)
    (tmp_path / "src" / "subprocess" / "__init__.py").write_text('__all__ = ["run"]\n')
    tree = ast.parse("from subprocess import run\n")
    public, internal, _modules, _has_private, _io_names, io_signals = analyze_imports(
        tree, {"subprocess"}, {"run"}, tmp_path
    )
    assert io_signals == ["imports subprocess"]
    assert public == []
    assert internal == []


def test_private_name_always_internal(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text('__all__ = ["_helper"]\n')
    (tmp_path / "src" / "pkg" / "mod.py").write_text('__all__ = ["_helper"]\n')
    tree = ast.parse("from pkg.mod import _helper\n")
    public, internal, _modules, has_private, _io_names, _io_signals = analyze_imports(
        tree, {"pkg"}, {"_helper"}, tmp_path
    )
    assert "_helper" in internal
    assert "_helper" not in public
    assert has_private is True


FIXTURE_CODE = (
    "import os\n"
    "import sys\n"
    "import subprocess\n"
    "from pathlib import Path\n"
    "from unittest.mock import patch\n"
    "from mypkg import public_a, public_b, _private\n"
    "from mypkg.sub import nested\n"
    "from mypkg._internal import private_helper\n"
    "from mypkg.utils._priv import hidden\n"
)


def test_analyze_imports_is_deterministic(tmp_path: Path) -> None:
    tree = ast.parse(FIXTURE_CODE)
    runs = [analyze_imports(tree, {"mypkg"}, None, tmp_path) for _ in range(3)]
    for i in range(1, len(runs)):
        assert runs[i] == runs[0], f"Run {i} produced different output than run 0"


def test_analyze_imports_findings_match_baseline(tmp_path: Path) -> None:
    tree = ast.parse(FIXTURE_CODE)
    _public, _internal, modules, has_private, io_modules, io_signals = analyze_imports(
        tree, {"mypkg"}, None, tmp_path
    )

    # Behavioral baseline: structural facts that any correct refactor must preserve.
    assert has_private is True, "Private mypkg alias (`_private`) must be flagged"
    assert any(m.startswith("mypkg") for m in modules), (
        "mypkg modules must appear in the per-module list"
    )
    # IO stdlib modules are tracked separately, not in the per-module list.
    assert "subprocess" in io_modules
    assert any("subprocess" in s for s in io_signals)
    # Outputs remain the documented types.
    assert isinstance(io_modules, set)
    assert isinstance(io_signals, list)


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
