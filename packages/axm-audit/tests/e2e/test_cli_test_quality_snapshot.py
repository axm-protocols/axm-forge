from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UV_BIN = shutil.which("uv") or "uv"


@pytest.mark.integration
def test_axm_audit_output_pinned() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    out = result.stdout
    lower = out.lower()
    assert "pyramid" in lower
