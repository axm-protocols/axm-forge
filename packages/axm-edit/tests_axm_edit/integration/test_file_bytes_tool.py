"""Real-filesystem behaviour of :class:`FileBytesTool` on ``tmp_path``."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.tools.file_bytes import FileBytesTool

pytestmark = pytest.mark.integration

ESCAPED_ACCENT = chr(92) + "u00e9"


def test_literal_char_where_escaped_was_expected(tmp_path: Path) -> None:
    """AC2: a literal `é` on disk with ``expect_escaped=True`` is flagged."""
    target = tmp_path / "literal.txt"
    target.write_text("café", encoding="utf-8")

    result = FileBytesTool().execute(path=str(target), expect_escaped=True)

    assert result.success is True
    assert result.data["verdict"] == "literal_where_escaped_expected"
    hint = result.data["hint"]
    assert "doubler" in hint
    assert "MCP" in hint


def test_escaped_sequence_where_literal_was_expected(tmp_path: Path) -> None:
    """AC3: a textual escape sequence with ``expect_escaped=False`` is flagged."""
    target = tmp_path / "escaped.txt"
    target.write_text(f"caf{ESCAPED_ACCENT}", encoding="utf-8")

    result = FileBytesTool().execute(path=str(target), expect_escaped=False)

    assert result.success is True
    assert result.data["verdict"] == "escaped_where_literal_expected"


def test_matching_expected_content_is_ok_with_stable_sha256(tmp_path: Path) -> None:
    """AC4: content equal to ``expected`` yields ``ok`` and a stable sha256."""
    target = tmp_path / "match.txt"
    content = "hello bytes\n"
    target.write_text(content, encoding="utf-8")

    tool = FileBytesTool()
    first = tool.execute(path=str(target), expected=content)
    second = tool.execute(path=str(target), expected=content)

    assert first.success is True
    assert first.data["verdict"] == "ok"
    assert first.data["mismatch"] is None
    assert first.data["sha256"] == second.data["sha256"]


def test_mismatch_reports_offset_and_ascii_only_reprs(tmp_path: Path) -> None:
    """AC5: a divergence exposes its offset and fully ASCII reprs."""
    target = tmp_path / "diff.txt"
    target.write_text("abcdef", encoding="utf-8")

    result = FileBytesTool().execute(path=str(target), expected="abcXef")

    mismatch = result.data["mismatch"]
    assert mismatch is not None
    assert mismatch["first_diff_offset"] == 3
    for key in ("expected_repr", "actual_repr"):
        rendered = mismatch[key]
        assert all(ord(char) < 128 for char in rendered), (
            f"{key} is not fully ASCII: {rendered!r}"
        )


def test_undecodable_bytes_are_a_diagnostic_not_a_failure(tmp_path: Path) -> None:
    """AC6: non-UTF-8 bytes stay a success with a ``decode_error`` verdict."""
    target = tmp_path / "binary.bin"
    target.write_bytes(b"\xff\xfe\x00\x9c raw")

    result = FileBytesTool().execute(path=str(target))

    assert result.success is True
    assert result.data["encoding_ok"] is False
    assert result.data["verdict"] == "decode_error"


def test_missing_path_becomes_a_failed_tool_result(tmp_path: Path) -> None:
    """AC7: a nonexistent path yields ``success is False`` and an error."""
    missing = tmp_path / "never-created.txt"

    result = FileBytesTool().execute(path=str(missing))

    assert result.success is False
    assert result.error


def test_execute_never_mutates_the_target_or_the_directory(tmp_path: Path) -> None:
    """AC8: sha256, mtime and directory listing are unchanged by a call."""
    target = tmp_path / "immutable.txt"
    target.write_text("café immutable\n", encoding="utf-8")

    sha_before = hashlib.sha256(target.read_bytes()).hexdigest()
    mtime_before = target.stat().st_mtime_ns
    listing_before = sorted(entry.name for entry in tmp_path.iterdir())

    result = FileBytesTool().execute(path=str(target), expect_escaped=True)
    assert result.success is True

    assert hashlib.sha256(target.read_bytes()).hexdigest() == sha_before
    assert target.stat().st_mtime_ns == mtime_before
    assert sorted(entry.name for entry in tmp_path.iterdir()) == listing_before
