"""Integration tests for strip_def_only."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import strip_def_only

pytestmark = pytest.mark.integration


def test_strip_def_only_removes_function_in_place(tmp_path: Path) -> None:
    """strip_def_only deletes the named def and rewrites the file."""
    target = tmp_path / "mod.py"
    target.write_text("def keep():\n    return 1\n\n\ndef drop():\n    return 2\n")

    strip_def_only(target, "drop")

    body = target.read_text()
    assert "def keep" in body
    assert "def drop" not in body


def test_strip_def_only_no_match_leaves_file_untouched(tmp_path: Path) -> None:
    """strip_def_only is a no-op when the name is absent."""
    target = tmp_path / "mod.py"
    original = "def keep():\n    return 1\n"
    target.write_text(original)

    strip_def_only(target, "absent")

    assert target.read_text() == original
