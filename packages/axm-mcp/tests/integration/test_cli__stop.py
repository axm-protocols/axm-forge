"""Integration test: stop must refuse to kill a foreign process (PID reuse)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_mcp import cli
from axm_mcp.cli import stop


@pytest.mark.integration
def test_stop_real_foreign_pid_not_killed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC1, AC2: a PID file pointing at a real foreign `sleep` process.

    stop must NOT kill it (cmdline mismatch), must clean the stale PID file,
    and must exit non-zero.
    """
    proc = subprocess.Popen(["sleep", "30"])  # noqa: S607
    try:
        pid_file = tmp_path / "axm-mcp.pid"
        pid_file.write_text(str(proc.pid))
        monkeypatch.setattr(cli, "PID_FILE", pid_file)

        with pytest.raises(SystemExit) as exc_info:
            stop()

        assert exc_info.value.code != 0
        # The foreign process must still be alive (not killed).
        assert proc.poll() is None
        # Stale PID file removed.
        assert not pid_file.exists()
        err = capsys.readouterr().err
        assert err.strip() != ""
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
