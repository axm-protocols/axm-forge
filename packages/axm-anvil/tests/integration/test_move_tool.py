from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


SOURCE_CODE = '''\
from __future__ import annotations


class TestFilesystemInvalidation:
    """Dummy class used as a move fixture."""

    def run(self) -> int:
        return 1


class Untouched:
    pass
'''

TARGET_CODE = """\
from __future__ import annotations
"""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execute_full_move_on_fixture(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(SOURCE_CODE)
    tgt.write_text(TARGET_CODE)

    tool = MoveTool()
    result = tool.execute(
        path=str(tmp_path),
        symbols="TestFilesystemInvalidation",
        from_file=str(src),
        to_file=str(tgt),
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["moved"][0]["symbol"] == "TestFilesystemInvalidation"
    files_modified = [str(Path(p)) for p in result.data["files_modified"]]
    assert str(src) in files_modified
    assert str(tgt) in files_modified
    assert result.text is not None
    assert "ast_move" in result.text

    assert "TestFilesystemInvalidation" in tgt.read_text()
    assert "TestFilesystemInvalidation" not in src.read_text()


def test_execute_dry_run_no_writes(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(SOURCE_CODE)
    tgt.write_text(TARGET_CODE)
    src_digest = _digest(src)
    tgt_digest = _digest(tgt)

    tool = MoveTool()
    result = tool.execute(
        path=str(tmp_path),
        symbols="TestFilesystemInvalidation",
        from_file=str(src),
        to_file=str(tgt),
        dry_run=True,
    )

    assert result.success is True, result.error
    assert result.data is not None
    assert _digest(src) == src_digest
    assert _digest(tgt) == tgt_digest


def test_mcp_entry_point_discoverable():
    code = (
        "from importlib.metadata import entry_points;"
        "eps = entry_points(group='axm.tools');"
        "match = [(e.name, e.value) for e in eps if e.name == 'ast_move'];"
        "print(match)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ast_move" in result.stdout
    assert "axm_anvil.tools.move:MoveTool" in result.stdout
