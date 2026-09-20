from __future__ import annotations

import threading
from pathlib import Path

from axm_init.core.root_lock import target_root_lock


def test_lock_is_released_on_exit_and_reentrant_within_one_thread() -> None:
    """AC1: the guard is re-entrant, so nested acquisitions never deadlock."""
    root = Path(__file__).parent

    with target_root_lock(root), target_root_lock(root):
        pass

    # A fresh acquisition still succeeds: nothing stayed held.
    with target_root_lock(root):
        pass


def test_distinct_roots_do_not_exclude_each_other(tmp_path: Path) -> None:
    """AC2: the registry is keyed by root, so unrelated roots run in parallel."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    entered_second = threading.Event()

    def hold_second() -> None:
        with target_root_lock(second):
            entered_second.set()

    with target_root_lock(first):
        worker = threading.Thread(target=hold_second)
        worker.start()
        # The other root must be reachable while `first` is held.
        assert entered_second.wait(timeout=5.0)
        worker.join(timeout=5.0)


def test_the_same_root_spelled_differently_shares_one_lock(tmp_path: Path) -> None:
    """AC3: roots are canonicalised, so `x` and `x/sub/..` exclude each other."""
    root = tmp_path / "target"
    (root / "sub").mkdir(parents=True)
    alias = root / "sub" / ".."
    blocked = threading.Event()

    def hold_alias() -> None:
        with target_root_lock(alias):
            blocked.set()

    with target_root_lock(root):
        worker = threading.Thread(target=hold_alias)
        worker.start()
        # The alias resolves to the same canonical root: it must NOT get in.
        assert not blocked.wait(timeout=0.3)

    worker.join(timeout=5.0)
    assert blocked.is_set()
