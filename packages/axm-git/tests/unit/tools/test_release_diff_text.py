from __future__ import annotations

from axm_git.tools.release_diff_text import render_failure_text, render_text


def _data() -> dict[str, object]:
    return {
        "current_tag": "v0.7.0",
        "suggested_bump": "minor",
        "suggested_next": "0.8.0",
        "breaking": False,
        "counts": {"feat": 2, "fix": 1, "breaking": 0, "other": 1},
        "commits_since": [
            {"hash": "a1", "type": "feat", "breaking": False, "subject": "x"}
        ],
        "files_changed": 4,
        "diffstat": "+1200 / -340",
        "public_api_touched": True,
    }


def test_render_text_header_has_tag_and_bump() -> None:
    """AC6: header contains tool name, current tag, suggested bump, commit count."""
    text = render_text(_data())
    assert "git_release_diff" in text
    assert "v0.7.0" in text
    assert "minor" in text
    assert "1" in text


def test_render_text_lists_commits_under_header() -> None:
    """AC2: each commit is listed as `<hash> <type>: <subject>` after the header."""
    data = _data()
    data["commits_since"] = [
        {"hash": "a1", "type": "feat", "breaking": False, "subject": "add x"},
        {"hash": "b2", "type": "fix", "breaking": False, "subject": "fix y"},
    ]
    lines = render_text(data).splitlines()
    assert "a1 feat: add x" in lines
    assert "b2 fix: fix y" in lines
    # commit lines come after the header line
    assert lines.index("a1 feat: add x") > 0


def test_render_text_summary_line_from_counts() -> None:
    """AC1: summary line lists non-zero per-type counts, omitting zero types."""
    data = _data()
    data["counts"] = {"feat": 2, "fix": 1, "breaking": 0, "other": 0}
    text = render_text(data)
    summary = next(line for line in text.splitlines() if "feat 2" in line)
    assert "fix 1" in summary
    assert "other" not in summary
    assert "breaking" not in summary


def test_render_text_marks_breaking_commit() -> None:
    """AC2: a breaking commit carries a marker and the summary shows `breaking 1`."""
    data = _data()
    data["counts"] = {"feat": 1, "fix": 0, "breaking": 1, "other": 0}
    data["commits_since"] = [
        {"hash": "c3", "type": "feat", "breaking": True, "subject": "drop old api"}
    ]
    text = render_text(data)
    commit_line = next(line for line in text.splitlines() if line.startswith("c3"))
    assert "!" in commit_line or "breaking" in commit_line
    summary = next(line for line in text.splitlines() if "breaking 1" in line)
    assert "breaking 1" in summary


def test_render_text_empty_commits_emits_no_block() -> None:
    """AC4: empty commits -> header + diffstat only, no extra/trailing lines."""
    data = _data()
    data["commits_since"] = []
    data["counts"] = {"feat": 0, "fix": 0, "breaking": 0, "other": 0}
    text = render_text(data)
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("git_release_diff | ✓")
    assert not text.endswith("\n")


def test_render_text_header_and_diffstat_unchanged() -> None:
    """AC3: header and diffstat lines are preserved when the block is appended."""
    lines = render_text(_data()).splitlines()
    assert lines[0].startswith("git_release_diff | ✓")
    assert "v0.7.0" in lines[0]
    assert "+1200 / -340" in lines[1]


def test_render_failure_text_surfaces_error() -> None:
    """AC6: failure text is prefixed and includes the error."""
    text = render_failure_text(error="not a git repo", data=None)
    assert text.startswith("git_release_diff | ✗")
    assert "not a git repo" in text
