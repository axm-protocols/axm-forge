"""Integration: ensure ``tools/`` is free of un-annotated BLE001 findings."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_PKG_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _PKG_ROOT / "src" / "axm_ast" / "tools"


def test_audit_practices_no_unhandled_ble001_in_tools() -> None:
    """Run ruff with the practices BLE001 rule and require zero findings.

    Findings tagged ``# noqa: BLE001`` (e.g. ``# noqa: BLE001 — final boundary``)
    are suppressed by ruff itself, so they never appear in the JSON output.
    """
    proc = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "axm-ast",
            "ruff",
            "check",
            "--select",
            "BLE001",
            "--output-format",
            "json",
            str(_TOOLS_DIR),
        ],
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    findings = json.loads(proc.stdout or "[]")
    ble001 = [f for f in findings if f.get("code") == "BLE001"]
    assert not ble001, (
        f"unexpected BLE001 findings in tools/: "
        f"{[(f['filename'], f['location']['row']) for f in ble001]}"
    )
