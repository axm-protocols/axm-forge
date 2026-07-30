"""Integration: write_file + edit_file confine against a shared root (real I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.tools.edit_file import EditFileTool
from axm_edit.tools.write_file import WriteFileTool


@pytest.mark.integration
class TestConfinementAgainstSharedRoot:
    """Both fs-mutating tools share the same root+relative confinement contract."""

    def test_both_tools_confine_against_a_shared_root(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        writer = WriteFileTool()
        editor = EditFileTool()

        # In-root write then edit both succeed on the happy path.
        write_res = writer.execute(path=str(root), file="pkg/app.py", content="x = 1\n")
        assert write_res.success is True
        assert (root / "pkg" / "app.py").read_text() == "x = 1\n"

        edit_res = editor.execute(
            path=str(root), file="pkg/app.py", old="x = 1", new="x = 2"
        )
        assert edit_res.success is True
        assert (root / "pkg" / "app.py").read_text() == "x = 2\n"

        # Out-of-root attempts fail on BOTH tools, touching nothing outside root.
        escapee = tmp_path / "escapee.py"
        write_escape = writer.execute(path=str(root), file=str(escapee), content="leak")
        assert write_escape.success is False
        assert not escapee.exists()

        edit_escape = editor.execute(
            path=str(root), file="../escapee.py", old="a", new="b"
        )
        assert edit_escape.success is False
