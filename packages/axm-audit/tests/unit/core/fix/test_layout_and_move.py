"""Unit tests for axm_audit.core.fix.layout_and_move."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.fix import layout_and_move
from axm_audit.core.fix.layout_and_move import (
    flatten_tier_layout,
    relocate_non_canonical_tiers,
)

_ROOT = Path("/nonexistent-axm-audit-layout-root")

# name -> list of positional-arg tuples recorded each time the patched stub ran.
type CallLog = dict[str, list[tuple[Any, ...]]]


class _FakeDir:
    """In-memory stand-in for a tier subdirectory: knows its name and emptiness."""

    def __init__(
        self,
        name: str,
        *,
        empty: bool = True,
        nested: list[Path] | None = None,
    ) -> None:
        self.name = name
        self._empty = empty
        self._nested = nested if nested is not None else []
        self.exists_calls = 0
        self.rmdir_calls = 0

    def rglob(self, _pattern: str) -> list[Path]:
        return list(self._nested)

    def exists(self) -> bool:
        self.exists_calls += 1
        return True

    def iterdir(self) -> list[Path]:
        return [] if self._empty else [Path(self.name) / "leftover.py"]

    def rmdir(self) -> None:
        self.rmdir_calls += 1


def _recorder(log: CallLog, name: str, ret: Any) -> Any:
    """Build a stub that records its positional args and returns *ret*."""
    log.setdefault(name, [])

    def _fn(*args: Any) -> Any:
        log[name].append(args)
        return ret

    return _fn


# --------------------------------------------------------------------------- #
# relocate_non_canonical_tiers — guards
# --------------------------------------------------------------------------- #


def test_relocate_no_tests_dir_returns_empty() -> None:
    """A project without a tests/ directory yields no relocation messages."""
    assert relocate_non_canonical_tiers(_ROOT) == []


def test_relocate_no_noncanonical_dirs_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no non-canonical tier dirs exist, nothing is relocated."""
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(layout_and_move, "_iter_non_canonical_tier_dirs", lambda _r: [])
    assert relocate_non_canonical_tiers(_ROOT) == []


def test_relocate_dir_without_test_files_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-canonical dir holding no test_*.py is skipped without moving."""
    empty_dir = _FakeDir("functional", nested=[])
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(
        layout_and_move, "_iter_non_canonical_tier_dirs", lambda _r: [empty_dir]
    )
    log: CallLog = {}
    monkeypatch.setattr(
        layout_and_move, "_relocate_single_file", _recorder(log, "relocate", [])
    )
    assert relocate_non_canonical_tiers(_ROOT) == []
    assert log["relocate"] == []


def test_relocate_moves_each_nested_test_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every nested test file in a non-canonical dir is relocated once."""
    nested = [Path("functional/test_a.py"), Path("functional/test_b.py")]
    child = _FakeDir("functional", empty=True, nested=nested)
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: True)
    monkeypatch.setattr(
        layout_and_move, "_iter_non_canonical_tier_dirs", lambda _r: [child]
    )
    monkeypatch.setattr(layout_and_move, "_ensure_integration_pkg", lambda _i, _c: None)
    monkeypatch.setattr(
        layout_and_move,
        "_unique_integration_target",
        lambda src, _i: Path("tests/integration") / src.name,
    )
    monkeypatch.setattr(layout_and_move, "_prune_empty_test_subdirs", lambda _d: None)
    log: CallLog = {}
    monkeypatch.setattr(
        layout_and_move,
        "_relocate_single_file",
        _recorder(log, "relocate", ["moved one"]),
    )
    msgs = relocate_non_canonical_tiers(_ROOT)
    assert msgs == ["moved one", "moved one"]
    assert len(log["relocate"]) == 2


def test_relocate_removes_emptied_child_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child dir left empty after pruning is rmdir'd."""
    child = _FakeDir("functional", empty=True, nested=[Path("functional/test_a.py")])
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: True)
    monkeypatch.setattr(
        layout_and_move, "_iter_non_canonical_tier_dirs", lambda _r: [child]
    )
    monkeypatch.setattr(layout_and_move, "_ensure_integration_pkg", lambda _i, _c: None)
    monkeypatch.setattr(
        layout_and_move, "_unique_integration_target", lambda src, _i: src
    )
    monkeypatch.setattr(layout_and_move, "_relocate_single_file", lambda *_a: [])
    monkeypatch.setattr(layout_and_move, "_prune_empty_test_subdirs", lambda _d: None)
    relocate_non_canonical_tiers(_ROOT)
    assert child.rmdir_calls == 1


def test_relocate_keeps_nonempty_child_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child dir still holding files after pruning is not rmdir'd."""
    child = _FakeDir("functional", empty=False, nested=[Path("functional/test_a.py")])
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(Path, "is_file", lambda _self: True)
    monkeypatch.setattr(
        layout_and_move, "_iter_non_canonical_tier_dirs", lambda _r: [child]
    )
    monkeypatch.setattr(layout_and_move, "_ensure_integration_pkg", lambda _i, _c: None)
    monkeypatch.setattr(
        layout_and_move, "_unique_integration_target", lambda src, _i: src
    )
    monkeypatch.setattr(layout_and_move, "_relocate_single_file", lambda *_a: [])
    monkeypatch.setattr(layout_and_move, "_prune_empty_test_subdirs", lambda _d: None)
    relocate_non_canonical_tiers(_ROOT)
    assert child.rmdir_calls == 0


# --------------------------------------------------------------------------- #
# flatten_tier_layout — guards & orchestration
# --------------------------------------------------------------------------- #


def test_flatten_no_tests_dir_returns_empty() -> None:
    """A project without a tests/ directory yields no flatten messages."""
    assert flatten_tier_layout(_ROOT) == []


def test_flatten_skips_unit_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flatten only ever visits integration and e2e tiers, never unit."""
    seen: list[str] = []
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)

    def _record(_project: Path, tier_dir: Path) -> list[str]:
        seen.append(tier_dir.name)
        return []

    monkeypatch.setattr(layout_and_move, "_flatten_single_tier", _record)
    flatten_tier_layout(_ROOT)
    assert seen == ["integration", "e2e"]


def test_flatten_skips_missing_tier_dirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tier whose directory is absent is skipped, only present ones flatten."""

    def _is_dir(self: Path) -> bool:
        return self.name != "e2e"

    monkeypatch.setattr(Path, "is_dir", _is_dir)
    log: CallLog = {}
    monkeypatch.setattr(
        layout_and_move, "_flatten_single_tier", _recorder(log, "flatten", [])
    )
    flatten_tier_layout(_ROOT)
    flattened_names = [args[1].name for args in log["flatten"]]
    assert flattened_names == ["integration"]


def test_flatten_aggregates_messages_across_tiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Messages from each flattened tier are concatenated in tier order."""
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)

    def _flatten(_project: Path, tier_dir: Path) -> list[str]:
        return [f"flattened-{tier_dir.name}"]

    monkeypatch.setattr(layout_and_move, "_flatten_single_tier", _flatten)
    assert flatten_tier_layout(_ROOT) == [
        "flattened-integration",
        "flattened-e2e",
    ]


def test_flatten_passes_project_path_to_each_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The project root is forwarded unchanged to the per-tier flattener."""
    monkeypatch.setattr(Path, "is_dir", lambda _self: True)
    log: CallLog = {}
    monkeypatch.setattr(
        layout_and_move, "_flatten_single_tier", _recorder(log, "flatten", [])
    )
    flatten_tier_layout(_ROOT)
    assert all(args[0] == _ROOT for args in log["flatten"])
