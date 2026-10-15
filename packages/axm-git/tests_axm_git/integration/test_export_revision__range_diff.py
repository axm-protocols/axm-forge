"""Commit measurements ignore checkout dirt and exports never follow symlinks."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.core.range_diff import export_revision, range_diff
from axm_git.tools.range_diff import RangeDiffTool

pytestmark = pytest.mark.integration


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_export_revision_and_range_diff(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.test")
    file = repo / "odd\tname.py"
    file.write_text("def calc():\n    return 1\n")
    (repo / "escape").symlink_to(tmp_path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD")
    file.write_text("def calc():\n    return 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "head")
    head = _git(repo, "rev-parse", "HEAD")
    file.write_text("checkout dirt")
    [changed] = range_diff(repo, base, head)
    assert changed.path == "odd\tname.py"
    [hunk] = changed.hunks
    assert (hunk.old_start, hunk.old_count, hunk.new_start, hunk.new_count) == (
        2,
        1,
        2,
        1,
    )
    assert RangeDiffTool().execute(path=str(repo), base=base, head=head).success
    with export_revision(repo, head) as tree:
        assert (tree / changed.path).read_text() == "def calc():\n    return 2\n"
        assert not (tree / "escape").exists()
    assert not tree.exists()
    assert file.read_text() == "checkout dirt"
    assert not RangeDiffTool().execute(path=str(repo), base="-bad", head=head).success
