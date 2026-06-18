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


def test_rename_module_level_assignment(tmp_path: Path) -> None:
    """A top-level assignment (plain and annotated) is renamable in place."""
    mod = tmp_path / "mod.py"
    mod.write_text(
        "OLD_CONST = 1\n"
        "OLD_TYPED: int = 2\n"
        "\n"
        "\n"
        "def use() -> int:\n"
        "    return OLD_CONST + OLD_TYPED\n"
    )

    plan = rename_symbols(
        tmp_path,
        "mod.py",
        {"OLD_CONST": "NEW_CONST", "OLD_TYPED": "NEW_TYPED"},
        workspace_root=tmp_path,
    )

    assert plan.renamed == {"OLD_CONST": "NEW_CONST", "OLD_TYPED": "NEW_TYPED"}
    text = mod.read_text()
    assert "NEW_CONST = 1" in text
    assert "NEW_TYPED: int = 2" in text
    assert "return NEW_CONST + NEW_TYPED" in text
    assert "OLD_CONST" not in text
    assert "OLD_TYPED" not in text


def test_rename_absent_symbol_warns_and_skips(tmp_path: Path) -> None:
    """A non-strict rename of an absent symbol records a warning and writes
    nothing (the all-absent mapping yields an empty active set)."""
    mod = tmp_path / "mod.py"
    original = "def kept() -> int:\n    return 1\n"
    mod.write_text(original)

    plan = rename_symbols(
        tmp_path,
        "mod.py",
        {"Ghost": "Spectre"},
        workspace_root=tmp_path,
    )

    assert plan.renamed == {}
    assert plan.files_modified == []
    assert any("Ghost" in w for w in plan.warnings)
    assert mod.read_text() == original


def test_rename_source_outside_root_skips_callers(tmp_path: Path) -> None:
    """When the source file is not under the workspace root, caller discovery
    is skipped (the _module_path_from_file ValueError path) so no callers are
    rewritten; computed in dry_run to avoid the out-of-root write guard."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    mod = outside / "mod.py"
    mod.write_text("def Old() -> int:\n    return Old.__name__ and 1\n")

    plan = rename_symbols(
        root,
        mod,
        {"Old": "New"},
        dry_run=True,
        workspace_root=root,
    )

    assert plan.renamed == {"Old": "New"}
    assert plan.callers_updated == []
    assert "def New()" in plan.source_text_new
