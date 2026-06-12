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


def test_render_failure_text_surfaces_error() -> None:
    """AC6: failure text is prefixed and includes the error."""
    text = render_failure_text(error="not a git repo", data=None)
    assert text.startswith("git_release_diff | ✗")
    assert "not a git repo" in text
