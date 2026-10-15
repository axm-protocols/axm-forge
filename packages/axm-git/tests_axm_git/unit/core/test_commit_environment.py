"""Isolation and explicit subprocess snapshots of the commit runtime."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from axm_git.core.commit_environment import commit_environment, environment_options
from axm_git.core.runner import find_git_root, run_git


def test_nested_scope_restores_after_exception() -> None:
    """An inner failed invocation cannot replace the outer or ambient runtime."""
    assert environment_options() == {}
    with commit_environment({"PYTHONPATH": "outer"}):
        with pytest.raises(RuntimeError), commit_environment({"PYTHONPATH": "inner"}):
            assert environment_options()["env"]["PYTHONPATH"] == "inner"
            raise RuntimeError("scripted")
        assert environment_options()["env"]["PYTHONPATH"] == "outer"
    assert environment_options() == {}


def test_subprocess_snapshots_are_independent_and_keep_git_options() -> None:
    """Local Git metadata overlays the snapshot without replacing candidate paths."""
    original = {"PATH": "/declared/bin", "PYTHONPATH": "/candidate/src"}
    with commit_environment(original):
        original["PYTHONPATH"] = "mutated caller"
        first = environment_options(
            {"GIT_INDEX_FILE": "/tmp/isolated-index", "PYTHONPATH": "/service"}
        )["env"]
        second = environment_options()["env"]
        assert first is not second
        assert first["GIT_INDEX_FILE"] == "/tmp/isolated-index"
        assert first["PYTHONPATH"] == second["PYTHONPATH"] == "/candidate/src"
    assert environment_options({"PATH": "/explicit"}) == {"env": {"PATH": "/explicit"}}


def _observe(marker: str, barrier: Barrier) -> str:
    """Read a thread's runtime while another invocation is concurrently live."""
    with commit_environment({"PYTHONPATH": marker}):
        barrier.wait(timeout=5)
        return environment_options()["env"]["PYTHONPATH"]


def test_concurrent_invocations_do_not_share_runtime() -> None:
    """Two overlapping invocations retain their own immutable values."""
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_observe, "first", barrier)
        second = executor.submit(_observe, "second", barrier)
        assert (first.result(), second.result()) == ("first", "second")
    assert environment_options() == {}


def test_every_git_subprocess_gets_a_fresh_scoped_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root discovery and ordinary Git reads share the explicit scoped contract."""
    calls: list[dict[str, object]] = []

    def invoke(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, "/candidate\n", "")

    monkeypatch.setattr(subprocess, "run", invoke)
    with commit_environment({"PYTHONPATH": "/candidate/src"}):
        assert find_git_root(Path("/candidate")) == Path("/candidate")
        run_git(["status"], Path("/candidate"), env={"GIT_INDEX_FILE": "/tmp/index"})
    run_git(["status"], Path("/candidate"))
    first, second, outside = calls
    assert isinstance(first["env"], Mapping)
    assert isinstance(second["env"], Mapping)
    assert first["env"] is not second["env"]
    assert first["env"]["PYTHONPATH"] == second["env"]["PYTHONPATH"]
    assert second["env"]["GIT_INDEX_FILE"] == "/tmp/index"
    assert "env" not in outside
