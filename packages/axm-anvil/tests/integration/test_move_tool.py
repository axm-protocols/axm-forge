from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from axm_anvil.tools.move import MoveTool
from tests.integration._helpers import (
    _write_empty_new,
    _write_old_foo,
)

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


def test_move_tool_exposes_callers_updated(workspace: Path) -> None:
    """AC7: MoveTool.execute surfaces `data['callers_updated']` entries."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "caller.py").write_text("from pkg.old import Foo\n\nFoo()\n")

    tool = MoveTool()
    result = tool.execute(
        path=str(workspace),
        symbols="Foo",
        from_file=str(old),
        to_file=str(new),
    )

    assert result.success is True, getattr(result, "error", None)
    callers = result.data["callers_updated"]
    assert isinstance(callers, list)
    assert len(callers) == 1
    entry = callers[0]
    assert set(entry.keys()) == {"file", "line", "old", "new"}


def _write_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )


def _setup_clean_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return tmp_path, a, b


def _setup_cycle_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text(
        "from mypkg.b import helper\n"
        "\n"
        "def Bar():\n"
        "    return 1\n"
        "\n"
        "def uses_helper():\n"
        "    return helper()\n"
        "\n"
        "def Foo():\n"
        "    return Bar()\n"
    )
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return tmp_path, a, b


def test_check_mode_reports_cycle_failure(tmp_path: Path) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
        check=True,
    )

    assert result.success is False
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_check_mode_reports_success_when_clean(tmp_path: Path) -> None:
    root, a, b = _setup_clean_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
        check=True,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.get("check") is True
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_move_tool_maps_cycle_error(tmp_path: Path) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
    )
    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Import cycle:")
    assert "mypkg.a" in result.error
    assert "mypkg.b" in result.error


@pytest.mark.integration
def test_tool_execute_exposes_shared_helpers_data(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n    return 1\n\n"
        "def moved_A():\n    return _shared()\n\n"
        "def remaining_B():\n    return _shared()\n"
    )
    target.write_text("")

    tool = MoveTool()
    result = tool.execute(
        path=str(tmp_path),
        symbols="moved_A",
        from_file="src.py",
        to_file="tgt.py",
    )
    assert result.success
    shared_data = result.data["shared_helpers_detected"]
    assert len(shared_data) == 1
    entry = shared_data[0]
    assert entry["name"] == "_shared"
    assert "moved_A" in entry["used_by_moved"]
    assert "remaining_B" in entry["used_by_remaining"]
