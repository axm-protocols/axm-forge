from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.e2e


def test_cli_old_name_rejected() -> None:
    result = subprocess.run(
        ["uv", "run", "axm-smelt", "compact", "--strategies", "dedup_values"],  # noqa: S607
        capture_output=True,
        text=True,
        input='{"a":"b"}',
    )
    assert result.returncode != 0
    assert "dedup_values" in (result.stderr + result.stdout).lower()
