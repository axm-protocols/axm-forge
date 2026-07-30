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
    """AC5: each prefixed subject is listed verbatim as `<hash> <subject>`."""
    data = _data()
    data["commits_since"] = [
        {"hash": "a1", "type": "feat", "breaking": False, "subject": "feat: add x"},
        {"hash": "b2", "type": "fix", "breaking": False, "subject": "fix: fix y"},
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
        {
            "hash": "c3",
            "type": "feat",
            "breaking": True,
            "subject": "feat!: drop old api",
        }
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


def test_summary_line_orders_and_omits_zero() -> None:
    """AC4: summary is feat, fix, then alpha, breaking last; zeros omitted."""
    data = _data()
    data["counts"] = {"feat": 2, "docs": 3, "breaking": 1}
    data["commits_since"] = [
        {"hash": "a1", "type": "feat", "breaking": False, "subject": "feat: x"}
    ]
    summary = next(line for line in render_text(data).splitlines() if "feat 2" in line)
    assert summary == "feat 2 · docs 3 · breaking 1"
    assert "fix" not in summary
    assert "other" not in summary


def test_commit_line_no_duplicate_prefix() -> None:
    """AC5: an already-prefixed subject is not re-prefixed with its type."""
    data = _data()
    data["counts"] = {"docs": 1}
    data["commits_since"] = [
        {"hash": "abc", "type": "docs", "breaking": False, "subject": "docs(x): tidy"}
    ]
    line = next(
        line for line in render_text(data).splitlines() if line.startswith("abc")
    )
    assert line == "abc docs(x): tidy"


def test_commit_line_breaking_keeps_marker() -> None:
    """AC5: a breaking, already-prefixed subject keeps the `!` marker."""
    data = _data()
    data["counts"] = {"feat": 1, "breaking": 1}
    data["commits_since"] = [
        {"hash": "xyz", "type": "feat", "breaking": True, "subject": "feat!: drop"}
    ]
    line = next(
        line for line in render_text(data).splitlines() if line.startswith("xyz")
    )
    assert "!" in line
    assert line == "xyz feat!: drop"


def test_commit_line_unprefixed_subject_gets_other() -> None:
    """AC5: a subject with no conventional prefix renders as `other: <subject>`."""
    data = _data()
    data["counts"] = {"other": 1}
    data["commits_since"] = [
        {"hash": "def", "type": "other", "breaking": False, "subject": "wip"}
    ]
    line = next(
        line for line in render_text(data).splitlines() if line.startswith("def")
    )
    assert line == "def other: wip"
