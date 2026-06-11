"""Integration tests for the axm_mcp.cli PID-file helpers.

Round-trips ``write_pid`` / ``read_pid`` (and ``remove_pid_file``) against a
real PID file in a temp directory. The serve/stop CLI commands that consume
these helpers are tested in ``test_app.py``.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_mcp.cli import read_pid, remove_pid_file, write_pid

pytestmark = pytest.mark.integration


@pytest.fixture
def tmp_pid_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Redirect PID file to a temp directory."""
    pid_file = tmp_path / "mcp-server.pid"
    with (
        patch("axm_mcp.cli.PID_DIR", tmp_path),
        patch("axm_mcp.cli.PID_FILE", pid_file),
    ):
        yield pid_file


class TestPidHelpers:
    """Round-trip ``write_pid`` / ``read_pid`` and removal semantics."""

    def test_write_then_read_pid(self, tmp_pid_file: Path) -> None:
        """write_pid persists a PID that read_pid then returns."""
        write_pid(42)
        assert read_pid() == 42
        write_pid(43)
        assert read_pid() == 43

    @pytest.mark.parametrize(
        "content",
        [None, "not-a-pid"],
        ids=["missing", "corrupt"],
    )
    def test_write_pid_overwrites_then_read_none(
        self, tmp_pid_file: Path, content: str | None
    ) -> None:
        """read_pid returns None when the file is absent or non-integer.

        Seeds a valid PID with write_pid first, then clobbers/removes the
        file so read_pid must fall back to None.
        """
        write_pid(11)
        assert read_pid() == 11
        if content is None:
            tmp_pid_file.unlink()
        else:
            tmp_pid_file.write_text(content)
        assert read_pid() is None

    def test_remove_then_read_pid_none(self, tmp_pid_file: Path) -> None:
        """remove_pid_file clears the PID; read_pid then returns None; idempotent."""
        write_pid(7)
        assert read_pid() == 7
        remove_pid_file()
        assert read_pid() is None
        # Re-seed and confirm remove is idempotent (second call must not raise).
        write_pid(8)
        remove_pid_file()
        assert read_pid() is None
