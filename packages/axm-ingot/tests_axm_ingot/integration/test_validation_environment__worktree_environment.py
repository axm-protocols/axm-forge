"""Filesystem discovery of worktree validation environments."""

from __future__ import annotations

import os
import sys

import pytest

from axm_ingot.validation import worktree_environment

pytestmark = pytest.mark.integration


def test_worktree_metadata_selects_source_environment_and_candidate_overlay(tmp_path):
    source = tmp_path / "source"
    admin = source / ".git" / "worktrees" / "lane"
    admin.mkdir(parents=True)
    (admin / "commondir").write_text("../..")
    (source / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    lane = tmp_path / "lane"
    package = lane / "packages" / "sample"
    (package / "src").mkdir(parents=True)
    (lane / ".git").write_text(f"gitdir: {admin}")
    env = worktree_environment(package)
    assert env is not None
    assert env.source == source
    assert env.command(["pytest"])[0] == str(source / ".venv" / "bin" / "python")
    assert env.variables()["PYTHONPATH"].split(os.pathsep)[0] == str(package / "src")
    assert env.variables()["VIRTUAL_ENV"] == str(source / ".venv")


def test_missing_source_environment_fails_closed(tmp_path):
    admin = tmp_path / "source" / ".git" / "worktrees" / "lane"
    admin.mkdir(parents=True)
    (admin / "commondir").write_text("../..")
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / ".git").write_text(f"gitdir: {admin}")
    with pytest.raises(ValueError, match="source environment missing"):
        worktree_environment(lane)


def test_ordinary_checkout_keeps_existing_runner(tmp_path):
    (tmp_path / ".git").mkdir()
    assert worktree_environment(tmp_path) is None
