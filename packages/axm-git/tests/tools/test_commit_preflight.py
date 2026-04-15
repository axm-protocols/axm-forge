from __future__ import annotations

from types import SimpleNamespace

import pytest

from axm_git.tools.commit_preflight import GitPreflightTool, _render_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool() -> GitPreflightTool:
    return GitPreflightTool()


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


# ---------------------------------------------------------------------------
# Unit tests — _render_text
# ---------------------------------------------------------------------------


def test_render_text_clean():
    result = _render_text(
        files=[], diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert result == "git_preflight | clean"


def test_render_text_dirty():
    files = [
        {"path": "src/foo.py", "status": "M"},
        {"path": "src/bar.py", "status": "A"},
    ]
    diff_stat = " 2 files changed, 10 insertions(+), 3 deletions(-)"
    diff = "diff --git a/src/foo.py b/src/foo.py\n--- a/src/foo.py\n+++ b/src/foo.py"
    result = _render_text(
        files=files,
        diff_stat=diff_stat,
        diff=diff,
        diff_truncated=False,
        max_diff_lines=200,
    )
    assert "git_preflight | 2 files \u00b7 dirty" in result
    assert "M  src/foo.py" in result
    assert "A  src/bar.py" in result
    assert diff_stat in result
    assert diff in result


def test_render_text_nodiff():
    files = [{"path": "src/foo.py", "status": "M"}]
    diff_stat = " 1 file changed, 5 insertions(+)"
    result = _render_text(
        files=files,
        diff_stat=diff_stat,
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    assert "git_preflight | 1 files \u00b7 dirty" in result
    assert "M  src/foo.py" in result
    assert diff_stat in result
    assert "diff --git" not in result


def test_render_text_truncated():
    files = [{"path": "src/foo.py", "status": "M"}]
    diff = "diff --git a/src/foo.py b/src/foo.py"
    result = _render_text(
        files=files,
        diff_stat=" 1 file changed",
        diff=diff,
        diff_truncated=True,
        max_diff_lines=200,
    )
    assert result.endswith("[diff truncated at 200 lines]")


def test_render_text_file_status_format():
    files = [{"path": "src/mod.py", "status": "M"}]
    result = _render_text(
        files=files,
        diff_stat="",
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    lines = result.splitlines()
    file_line = next(ln for ln in lines if "src/mod.py" in ln)
    assert file_line.startswith("M  ")


def test_render_text_untracked_format():
    files = [{"path": "new_file.py", "status": "??"}]
    result = _render_text(
        files=files,
        diff_stat="",
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    lines = result.splitlines()
    file_line = next(ln for ln in lines if "new_file.py" in ln)
    assert file_line.startswith("?? ")


# ---------------------------------------------------------------------------
# Functional tests — execute
# ---------------------------------------------------------------------------


def _mock_run_git_dirty(cmd, cwd):
    if cmd[0] == "status":
        return _git_result(stdout=" M src/foo.py\n")
    if cmd[0] == "diff" and "-U2" in cmd:
        return _git_result(stdout="diff --git a/src/foo.py b/src/foo.py")
    # diff --stat
    return _git_result(stdout=" 1 file changed, 2 insertions(+)")


def test_execute_sets_text(tool, monkeypatch):
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr("axm_git.tools.commit_preflight.run_git", _mock_run_git_dirty)
    result = tool.execute(path="/tmp/repo")
    assert result.text is not None
    assert isinstance(result.text, str)


def test_execute_preserves_data(tool, monkeypatch):
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr("axm_git.tools.commit_preflight.run_git", _mock_run_git_dirty)
    result = tool.execute(path="/tmp/repo")
    assert "files" in result.data
    assert "clean" in result.data
    assert "diff" in result.data
    assert result.data["clean"] is False
    assert len(result.data["files"]) == 1
    assert result.data["files"][0]["path"] == "src/foo.py"
    assert result.data["files"][0]["status"] == "M"


def test_execute_clean_text(tool, monkeypatch):
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr(
        "axm_git.tools.commit_preflight.run_git",
        lambda cmd, cwd: _git_result(stdout=""),
    )
    result = tool.execute(path="/tmp/repo")
    assert result.text == "git_preflight | clean"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_render_text_empty_diff_stat():
    """Clean repo — no blank stat section in text."""
    result = _render_text(
        files=[], diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert result == "git_preflight | clean"
    assert "\n\n\n" not in result


def test_render_text_single_file():
    """Single changed file — header shows '1 files · dirty'."""
    files = [{"path": "README.md", "status": "M"}]
    result = _render_text(
        files=files, diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert "1 files \u00b7 dirty" in result


def test_render_text_long_file_paths():
    """200+ char paths shown in full, no truncation."""
    long_path = "a" * 210 + ".py"
    files = [{"path": long_path, "status": "M"}]
    result = _render_text(
        files=files, diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert long_path in result
