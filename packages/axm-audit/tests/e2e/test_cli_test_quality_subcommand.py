from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UV_BIN = shutil.which("uv") or "uv"


@pytest.mark.e2e
def test_cli_test_quality_happy_path() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    assert result.stdout.strip()


@pytest.mark.e2e
def test_cli_test_quality_json_valid() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT), "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    for key in (
        "clusters",
        "verdicts",
        "pyramid_mismatches",
        "private_import_violations",
    ):
        assert key in data, f"missing key: {key}"


@pytest.mark.e2e
def test_cli_test_quality_mismatches_only() -> None:
    result = subprocess.run(  # noqa: S603
        [
            _UV_BIN,
            "run",
            "axm-audit",
            "test-quality",
            str(PROJECT_ROOT),
            "--mismatches-only",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    out = result.stdout.lower()
    # Section headers from the other rule groups must be absent.
    assert "tautologies:" not in out
    assert "duplicates:" not in out
    assert "private imports:" not in out
