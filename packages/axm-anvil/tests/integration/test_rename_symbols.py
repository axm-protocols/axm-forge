"""Integration tests for :func:`axm_anvil.core.rename.rename_symbols`.

Real filesystem I/O against unique ``tmp_path`` modules / mini-workspaces.
Exercises the public core function only; the private CST transformers and
caller-discovery helpers are validated through the observable rewrite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.rename import rename_symbols

pytestmark = pytest.mark.integration


def test_rename_rewrites_definition_and_local_usages(tmp_path: Path) -> None:
    """AC2: a top-level symbol's definition AND internal usages are renamed."""
    mod = tmp_path / "mod.py"
    mod.write_text(
        "def OldName() -> int:\n"
        "    return 1\n"
        "\n"
        "\n"
        "def caller() -> int:\n"
        "    return OldName()\n"
    )

    rename_symbols(
        tmp_path,
        "mod.py",
        {"OldName": "NewName"},
        workspace_root=tmp_path,
    )

    text = mod.read_text()
    assert "def NewName()" in text
    assert "return NewName()" in text
    assert "OldName" not in text


def test_rename_rewrites_cross_file_callers(tmp_path: Path) -> None:
    """AC3: cross-file callers' imports and usages are rewritten workspace-wide."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "defs.py").write_text("def Old() -> int:\n    return 1\n")
    (pkg / "caller_a.py").write_text(
        "from pkg.defs import Old\n\n\ndef a() -> int:\n    return Old()\n"
    )
    (pkg / "caller_b.py").write_text(
        "from pkg.defs import Old\n\n\ndef b() -> int:\n    return Old() + Old()\n"
    )

    rename_symbols(
        tmp_path,
        "pkg/defs.py",
        {"Old": "New"},
        workspace_root=tmp_path,
    )

    assert "def New()" in (pkg / "defs.py").read_text()
    text_a = (pkg / "caller_a.py").read_text()
    assert "from pkg.defs import New" in text_a
    assert "return New()" in text_a
    assert "Old" not in text_a
    text_b = (pkg / "caller_b.py").read_text()
    assert "from pkg.defs import New" in text_b
    assert "New() + New()" in text_b
    assert "Old" not in text_b


def test_rename_dry_run_no_write(tmp_path: Path) -> None:
    """AC4: dry_run computes the plan without mutating files on disk."""
    mod = tmp_path / "mod.py"
    original = "def OldName() -> int:\n    return OldName.__hash__ and 1\n"
    mod.write_text(original)

    plan = rename_symbols(
        tmp_path,
        "mod.py",
        {"OldName": "NewName"},
        dry_run=True,
        workspace_root=tmp_path,
    )

    assert plan is not None
    assert mod.read_text() == original
