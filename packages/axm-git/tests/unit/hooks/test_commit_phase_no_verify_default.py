"""AXM-1645: pre-commit hooks must run by default in commit_phase.

Unit tests for the contract change: ``skip_hooks`` defaults to ``False``
so ``--no-verify`` is no longer appended unless callers opt in.
"""

from __future__ import annotations

import inspect

from axm_git.hooks.commit_phase import CommitPhaseHook, _build_commit_cmd


def test_build_commit_cmd_no_verify_omitted_when_skip_hooks_false() -> None:
    cmd = _build_commit_cmd("msg", None, skip_hooks=False)
    assert "--no-verify" not in cmd


def test_build_commit_cmd_no_verify_present_when_skip_hooks_true() -> None:
    cmd = _build_commit_cmd("msg", None, skip_hooks=True)
    assert "--no-verify" in cmd


def test_commit_phase_default_skip_hooks_is_false() -> None:
    sig = inspect.signature(CommitPhaseHook._commit_from_outputs)
    assert sig.parameters["skip_hooks"].default is False
