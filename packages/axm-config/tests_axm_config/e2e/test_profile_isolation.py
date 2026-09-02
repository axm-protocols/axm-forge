from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_profile_isolation_command_reports_state_paths(
    tmp_path: Path,
) -> None:
    """AC4: the profile_isolation command prints all six state-path names."""
    env = os.environ.copy()
    env["AXM_HOME"] = str(tmp_path)

    result = subprocess.run(
        ["axm", "profile_isolation", "--profile", "scratch"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    for path_name in (
        "tickets_db",
        "warden_socket",
        "warden_log",
        "sessions_root",
        "quality_dir",
        "protocols_dir",
    ):
        assert path_name in result.stdout
