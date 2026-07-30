from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core import extract as extract_mod
from axm_anvil.core.extract import _mkdir_tracking, extract_symbols
from axm_anvil.core.plan import MovePlan, MoveValidationError


def _write_source(tmp_path: Path) -> Path:
    """Create a minimal source module with one extractable symbol."""
    source = tmp_path / "source.py"
    source.write_text("def foo() -> int:\n    return 1\n")
    return source


def test_write_mode_failure_removes_orphan_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: a write-mode (dry_run=False) extract whose move raises removes the
    empty scaffold target file it created rather than leaving it orphaned."""
    source = _write_source(tmp_path)
    target = tmp_path / "new_module.py"

    def _boom(*_args: object, **_kwargs: object) -> MovePlan:
        raise MoveValidationError("forced failure", ValueError("bad"))

    monkeypatch.setattr(extract_mod, "move_symbols", _boom)

    with pytest.raises(MoveValidationError):
        extract_symbols(source, target, ["foo"], dry_run=False)

    assert not target.exists()


def test_write_mode_failure_removes_created_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: the parent directories scaffolded by ``_mkdir_tracking`` for a
    failing write-mode extract are pruned back to the first pre-existing dir."""
    source = _write_source(tmp_path)
    # target lives under two not-yet-existing package dirs
    nested_root = tmp_path / "pkg"
    target = nested_root / "sub" / "new_module.py"
    assert not nested_root.exists()

    def _boom(*_args: object, **_kwargs: object) -> MovePlan:
        raise MoveValidationError("forced failure", ValueError("bad"))

    monkeypatch.setattr(extract_mod, "move_symbols", _boom)

    with pytest.raises(MoveValidationError):
        extract_symbols(source, target, ["foo"], dry_run=False)

    assert not target.exists()
    assert not (nested_root / "sub").exists()
    assert not nested_root.exists()
    # the pre-existing root is untouched
    assert tmp_path.exists()


def test_write_mode_success_keeps_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: a successful write-mode extract leaves the created target file and
    directories on disk (no regression to the happy path)."""
    source = _write_source(tmp_path)
    nested_root = tmp_path / "pkg"
    target = nested_root / "sub" / "new_module.py"

    def _ok(*_args: object, **_kwargs: object) -> MovePlan:
        return MovePlan(
            source_text_new="",
            target_text_new="def foo() -> int:\n    return 1\n",
            moved_names=["foo"],
        )

    monkeypatch.setattr(extract_mod, "move_symbols", _ok)

    plan = extract_symbols(source, target, ["foo"], dry_run=False)

    assert plan.moved_names == ["foo"]
    assert target.exists()
    assert (nested_root / "sub").exists()


def test_mkdir_tracking_returns_created_dirs(tmp_path: Path) -> None:
    """``_mkdir_tracking`` creates and reports only the dirs it actually made,
    ordered deepest-first so a caller can rmdir them in sequence."""
    leaf = tmp_path / "a" / "b" / "c"

    created = _mkdir_tracking(leaf)

    assert leaf.exists()
    assert created == [leaf, tmp_path / "a" / "b", tmp_path / "a"]
