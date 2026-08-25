"""Whole-file rewrites applied through ``BatchEditTool`` (real filesystem I/O).

Each test writes a module under ``tmp_path``, hands the tool a ``rewrite``
operation carrying that file's real sha256 digest, and reads the bytes back
from disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.tools.batch_edit import BatchEditTool

pytestmark = pytest.mark.integration

TRIPLE_DOUBLE = '"""'
TRIPLE_SINGLE = "'''"


@pytest.fixture
def tool() -> BatchEditTool:
    return BatchEditTool()


def _digest(path: Path) -> str:
    """sha256 hex digest of the on-disk bytes of *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_op(file: str, content: str, checksum: str) -> dict[str, object]:
    return {
        "op": "rewrite",
        "file": file,
        "content": content,
        "expected_checksum": checksum,
    }


def test_tool_applies_a_valid_rewrite_and_renders_its_line(
    tool: BatchEditTool, tmp_path: Path
) -> None:
    """AC3: a digest-matching rewrite applies and is named in the rendered text."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")
    new_body = "value = 2\nother = 3\n"

    result = tool.execute(
        path=str(tmp_path),
        operations=[_rewrite_op("pkg/mod.py", new_body, _digest(target))],
        lint=False,
    )

    assert result.success, result.error
    assert target.read_text(encoding="utf-8") == new_body
    assert result.text is not None
    named = [line for line in result.text.splitlines() if "pkg/mod.py" in line]
    assert any("rewrite" in line.lower() for line in named), result.text


def test_triple_quote_heavy_module_is_rewritten_whole(
    tool: BatchEditTool, tmp_path: Path
) -> None:
    """AC4: a module holding both triple-quote flavours is replaced byte for byte."""
    target = tmp_path / "quotes.py"
    original = (
        f"{TRIPLE_DOUBLE}Module doc.{TRIPLE_DOUBLE}\n"
        f"SQL = {TRIPLE_SINGLE}select 1{TRIPLE_SINGLE}\n"
    )
    target.write_text(original, encoding="utf-8")
    new_body = (
        f"{TRIPLE_DOUBLE}Rewritten doc.{TRIPLE_DOUBLE}\n"
        f"SQL = {TRIPLE_SINGLE}select 2{TRIPLE_SINGLE}\n"
        f"NOTE = {TRIPLE_DOUBLE}keeps {TRIPLE_SINGLE} inside{TRIPLE_DOUBLE}\n"
    )

    result = tool.execute(
        path=str(tmp_path),
        operations=[_rewrite_op("quotes.py", new_body, _digest(target))],
        lint=False,
    )

    assert result.success, result.error
    assert target.read_bytes() == new_body.encode("utf-8")
