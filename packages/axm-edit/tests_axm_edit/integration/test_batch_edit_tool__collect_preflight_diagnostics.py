"""Integration tests for the BatchEditTool preflight wiring (real I/O)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from axm_edit.tools.batch_edit import BatchEditTool
from axm_edit.tools.batch_edit_check import BatchEditCheckTool

pytestmark = pytest.mark.integration


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_snapshot(root: Path) -> dict[str, str]:
    """Path -> sha256 for every file under *root* (byte-level witness)."""
    return {
        item.relative_to(root).as_posix(): _sha256(item)
        for item in sorted(root.rglob("*"))
        if item.is_file()
    }


def _message(result: Any) -> str:
    return f"{result.error or ''}\n{result.text or ''}"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A tiny project root with two python modules."""
    (tmp_path / "mod.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("other = 2\n", encoding="utf-8")
    return tmp_path


def test_unknown_edit_key_is_rejected_and_nothing_is_written(project: Path) -> None:
    """AC1: `replace_all` blocks the batch and the target bytes are untouched."""
    target = project / "mod.py"
    before = _sha256(target)

    result = BatchEditTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "mod.py",
                "edits": [
                    {"old": "value = 1", "new": "value = 2", "replace_all": True}
                ],
            }
        ],
        lint=False,
    )

    message = _message(result)
    keys_line = [
        line
        for line in message.splitlines()
        if all(key in line for key in ("old", "new", "line"))
    ]

    assert result.success is False, message
    assert "replace_all" in message, message
    assert keys_line, f"the refusal must list the accepted edit keys: {message}"
    assert _sha256(target) == before, "the rejected edit must not be applied"


def test_blocked_batch_exposes_the_report_and_creates_no_checkpoint(
    project: Path,
) -> None:
    """AC2: a blocked batch reports blocking diagnostics before any checkpoint."""
    before = _tree_snapshot(project)

    result = BatchEditTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "mod.py",
                "edits": [{"old": "value = 1", "new": "value = 3"}],
            },
            {
                "op": "replace",
                "file": "other.py",
                "edits": [{"old": "absent anchor", "new": "whatever"}],
            },
            {"op": "create", "file": "created.py", "content": "created = 1\n"},
        ],
        lint=False,
    )

    data = result.data or {}
    preflight = data.get("preflight")

    assert result.success is False, _message(result)
    assert preflight is not None, data
    assert preflight["blocking"] is True, preflight
    assert preflight["diagnostics"], preflight
    assert not data.get("checkpoint"), "create_checkpoint must never be reached"
    assert _tree_snapshot(project) == before


def test_warning_only_batch_applies_and_keeps_its_warnings_apart(
    project: Path,
) -> None:
    """AC3: an over-long line only warns; ruff warnings stay a distinct channel."""
    target = project / "mod.py"
    long_line = "value = " + "1" * 200
    # The rule warns on the ]88, project-limit] window, so the project must
    # declare a limit above ruff's 88-char default for the line to be a
    # *warning* rather than a plain lint error.
    (project / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 220\n", encoding="utf-8"
    )

    result = BatchEditTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "mod.py",
                "edits": [{"old": "value = 1", "new": long_line}],
            }
        ],
        lint=False,
    )

    data = result.data or {}
    preflight = data.get("preflight")

    assert result.success is True, _message(result)
    assert target.read_text(encoding="utf-8") == long_line + "\n"
    assert preflight is not None, data
    assert preflight["blocking"] is False, preflight
    warnings = preflight["warnings"]
    assert warnings, preflight
    assert any("mod.py" in str(item) for item in warnings), warnings
    ruff_warnings = str(data.get("warnings", []))
    assert "mod.py" not in ruff_warnings, ruff_warnings


def test_valid_batch_applies_and_exposes_an_empty_report(project: Path) -> None:
    """AC4: a clean batch still carries an empty, non-blocking preflight entry."""
    result = BatchEditTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "mod.py",
                "edits": [{"old": "value = 1", "new": "value = 2"}],
            },
            {"op": "create", "file": "created.py", "content": "created = 1\n"},
        ],
        lint=False,
    )

    data = result.data or {}
    preflight = data.get("preflight")

    assert result.success is True, _message(result)
    assert (project / "mod.py").read_text(encoding="utf-8") == "value = 2\n"
    assert (project / "created.py").read_text(encoding="utf-8") == "created = 1\n"
    assert preflight is not None, data
    assert preflight["diagnostics"] == [], preflight
    assert preflight["blocking"] is False, preflight
    # Pre-existing payload keys keep their previous meaning.
    assert data["summary"] == {"modified": 1, "created": 1, "deleted": 0}
    assert data["applied"] >= 1


def test_check_tool_and_batch_edit_agree_on_the_ordered_diagnostics(
    project: Path,
) -> None:
    """AC5: both surfaces emit the same diagnostics, element by element."""
    operations: list[dict[str, Any]] = [
        {
            "op": "replace",
            "file": "mod.py",
            "edits": [{"old": "value = 1", "new": "value = 2", "replace_all": True}],
        },
        {
            "op": "replace",
            "file": "other.py",
            "edits": [{"old": "absent anchor", "new": "whatever"}],
        },
    ]

    checked = BatchEditCheckTool().execute(path=str(project), operations=operations)
    edited = BatchEditTool().execute(
        path=str(project), operations=operations, lint=False
    )

    check_data = checked.data or {}
    check_diagnostics = check_data.get("diagnostics")
    if check_diagnostics is None:
        check_diagnostics = (check_data.get("preflight") or {}).get("diagnostics")
    assert check_diagnostics is not None, check_data

    edit_data = edited.data or {}
    preflight = edit_data.get("preflight")
    assert preflight is not None, edit_data
    edit_diagnostics = preflight["diagnostics"]

    assert len(edit_diagnostics) == len(check_diagnostics)
    for produced, expected in zip(edit_diagnostics, check_diagnostics, strict=True):
        assert produced == expected
