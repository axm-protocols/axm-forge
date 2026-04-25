"""Integration regression: pyramid-level findings unchanged after refactor.

Runs ``axm-audit test-quality`` on the axm-audit package itself and asserts
that the per-test classification is byte-identical to the baseline captured
before the refactor.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PKG_ROOT = Path(__file__).resolve().parents[5]
BASELINE_DIR = Path(__file__).parent / "_baselines"
FINDINGS_BASELINE = BASELINE_DIR / "pyramid_findings.json"


def _normalize(payload: dict) -> dict:
    """Reduce a raw axm-audit payload to its pyramid-level classification.

    We compare only the bits that AC2 mandates (count and per-test
    classification) so that incidental fields (timestamps, paths in CI
    runners, etc.) do not produce spurious diffs.
    """
    findings = payload.get("pyramid_mismatches") or payload.get("findings") or []
    classification = sorted(
        [
            f.get("path", ""),
            f.get("function", ""),
            f.get("level", ""),
            f.get("current_level", ""),
        ]
        for f in findings
    )
    return {"count": len(classification), "classification": classification}


def _run_audit() -> dict:
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "axm_audit",
            "test-quality",
            str(PKG_ROOT),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(PKG_ROOT),
        check=False,
    )
    assert result.stdout, (
        f"axm-audit produced no JSON output\n"
        f"stderr:\n{result.stderr}\nrc={result.returncode}"
    )
    return json.loads(result.stdout)


def test_pyramid_findings_unchanged() -> None:
    """AC2 — same pyramid-level findings before and after refactor."""
    payload = _run_audit()
    current = _normalize(payload)
    if not FINDINGS_BASELINE.exists():
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        FINDINGS_BASELINE.write_text(
            json.dumps(current, indent=2) + "\n", encoding="utf-8"
        )
        pytest.skip("baseline captured; rerun to validate")
    baseline = json.loads(FINDINGS_BASELINE.read_text(encoding="utf-8"))
    assert current["count"] == baseline["count"], (
        f"pyramid findings count changed: {current['count']} "
        f"vs baseline {baseline['count']}"
    )
    assert current["classification"] == baseline["classification"], (
        "per-test pyramid classification diverged from baseline"
    )
