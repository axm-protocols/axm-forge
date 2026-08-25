from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from axm_git.tools.release_diff import GitReleaseDiffTool


def _completed(
    stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=""
    )


class _FakeGit:
    """Routes git subcommands to canned outputs and records calls."""

    def __init__(self, responses: dict[str, str], *, tags: str = "") -> None:
        self._responses = responses
        self._tags = tags
        self.calls: list[list[str]] = []

    def __call__(
        self, args: list[str], cwd: Path, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return _completed(self._stdout_for(args))

    def _stdout_for(self, args: list[str]) -> str:
        sub = args[0]
        simple = {"tag": self._tags, "rev-parse": "HEAD"}
        if sub in simple:
            return simple[sub]
        if sub == "log":
            return self._responses.get("log", "")
        if sub == "diff":
            if "--name-only" in args:
                return self._responses.get("name-only", "")
            if "--stat" in args:
                return self._responses.get("stat", "")
            return self._responses.get("diff", "")
        return ""


def _patch(monkeypatch: Any, fake: _FakeGit) -> None:
    monkeypatch.setattr("axm_git.tools.release_diff.run_git", fake)
    monkeypatch.setattr(
        "axm_git.tools.release_diff.find_git_root",
        lambda path: Path("/repo"),
    )
    monkeypatch.setattr("axm_git.tools.release_diff.get_tag_prefix", lambda path: "")


def test_execute_returns_suggested_bump_fields(monkeypatch: Any) -> None:
    """AC1: execute returns current_tag, suggested_bump, suggested_next, breaking."""
    fake = _FakeGit(
        {
            "log": "abc123\tfeat: add thing",
            "stat": " 1 file changed, 3 insertions(+)",
            "name-only": "core/foo.py",
        },
        tags="v0.7.0",
    )
    _patch(monkeypatch, fake)
    result = GitReleaseDiffTool().execute(path=".")
    assert result.success
    data = result.data
    assert data["current_tag"] == "v0.7.0"
    assert data["suggested_bump"] == "minor"
    assert data["suggested_next"]
    assert data["breaking"] is False


def test_commits_since_scoped_to_subdir_and_counted(monkeypatch: Any) -> None:
    """AC2: commits_since parsed with hash/type/subject; counts aggregated."""
    log = "a1\tfeat: x\nb2\tfix: y\nc3\tchore: z"
    fake = _FakeGit({"log": log, "stat": "", "name-only": ""}, tags="v0.7.0")
    _patch(monkeypatch, fake)
    data = GitReleaseDiffTool().execute(path=".").data
    counts = data["counts"]
    assert counts["feat"] == 1
    assert counts["fix"] == 1
    assert counts["chore"] == 1
    assert "breaking" not in counts
    commits = data["commits_since"]
    assert len(commits) == 3
    for c in commits:
        assert "hash" in c
        assert "type" in c
        assert "subject" in c


def test_aggregate_counts_dynamic_per_type(monkeypatch: Any) -> None:
    """AC3: counts has one key per encountered type, no zero-valued keys."""
    log = (
        "a1\tfeat: one\nb2\tfeat: two\nc3\tfix: y\n"
        "d4\tdocs: a\ne5\tdocs: b\nf6\tdocs: c\ng7\tchore: z"
    )
    fake = _FakeGit({"log": log, "stat": "", "name-only": ""}, tags="v0.7.0")
    _patch(monkeypatch, fake)
    counts = GitReleaseDiffTool().execute(path=".").data["counts"]
    assert counts["feat"] == 2
    assert counts["fix"] == 1
    assert counts["docs"] == 3
    assert counts["chore"] == 1
    assert all(v > 0 for v in counts.values())


def test_aggregate_counts_breaking_tallied(monkeypatch: Any) -> None:
    """AC3: a feat!: commit tallies both feat and breaking."""
    fake = _FakeGit(
        {"log": "a1\tfeat!: drop api", "stat": "", "name-only": ""},
        tags="v0.7.0",
    )
    _patch(monkeypatch, fake)
    counts = GitReleaseDiffTool().execute(path=".").data["counts"]
    assert counts["feat"] == 1
    assert counts["breaking"] == 1


def test_diffstat_and_public_api_flag(monkeypatch: Any) -> None:
    """AC3: files_changed, diffstat, and public_api_touched when __init__.py present."""
    fake = _FakeGit(
        {
            "log": "a1\tfeat: x",
            "stat": " 2 files changed, 1200 insertions(+), 340 deletions(-)",
            "name-only": "src/axm_x/__init__.py\nsrc/axm_x/core.py",
        },
        tags="v0.7.0",
    )
    _patch(monkeypatch, fake)
    import re

    data = GitReleaseDiffTool().execute(path=".").data
    assert data["files_changed"] > 0
    assert re.match(r"\+\d+ / -\d+", data["diffstat"])
    assert data["public_api_touched"] is True


def test_public_api_not_touched_when_no_init(monkeypatch: Any) -> None:
    """AC3: public_api_touched is False when no __init__.py in diff."""
    fake = _FakeGit(
        {
            "log": "a1\tfix: x",
            "stat": " 1 file changed, 2 insertions(+)",
            "name-only": "core/foo.py",
        },
        tags="v0.7.0",
    )
    _patch(monkeypatch, fake)
    data = GitReleaseDiffTool().execute(path=".").data
    assert data["public_api_touched"] is False


def test_first_release_when_no_tag(monkeypatch: Any) -> None:
    """AC4: no tag -> current_tag is None, suggested_next == 0.1.0."""
    fake = _FakeGit(
        {
            "log": "a1\tfeat: initial",
            "stat": " 1 file changed, 5 insertions(+)",
            "name-only": "core/foo.py",
        },
        tags="",
    )
    _patch(monkeypatch, fake)
    data = GitReleaseDiffTool().execute(path=".").data
    assert data["current_tag"] is None
    assert data["suggested_next"] == "0.1.0"


def test_read_only_invokes_no_mutating_git(monkeypatch: Any) -> None:
    """AC5: only read-only git subcommands are invoked."""
    fake = _FakeGit(
        {
            "log": "a1\tfeat: x",
            "stat": " 1 file changed, 1 insertion(+)",
            "name-only": "core/foo.py",
        },
        tags="v0.7.0",
    )
    _patch(monkeypatch, fake)
    GitReleaseDiffTool().execute(path=".")
    allowed = {"log", "diff", "tag", "rev-parse"}
    for call in fake.calls:
        assert call[0] in allowed, f"unexpected git subcommand: {call[0]}"


def test_breaking_commit_sets_major_post_1_0(monkeypatch: Any) -> None:
    """AC1: feat! on a post-1.0 base bumps major and sets breaking."""
    fake = _FakeGit(
        {
            "log": "a1\tfeat!: drop legacy api",
            "stat": " 1 file changed, 1 insertion(+)",
            "name-only": "core/foo.py",
        },
        tags="v1.2.0",
    )
    _patch(monkeypatch, fake)
    data = GitReleaseDiffTool().execute(path=".").data
    assert data["suggested_bump"] == "major"
    assert data["breaking"] is True
