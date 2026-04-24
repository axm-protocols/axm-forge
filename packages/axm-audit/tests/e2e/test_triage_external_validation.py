"""E2E: triage() produces 0 DELETE across three external Python corpora.

AC11 — LibCST, dagster, and traffic should never false-positive. Total
UNKNOWN findings across the three corpora must remain <= 3.

This test is opt-in: it skips automatically if any of the expected external
checkouts is missing from the developer machine.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_EXTERNAL_ROOT = Path.home() / "Documents" / "Code" / "external"
_EXTERNAL_CORPORA = [
    _EXTERNAL_ROOT / "LibCST",
    _EXTERNAL_ROOT / "dagster",
    _EXTERNAL_ROOT / "traffic",
]
_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not all(p.exists() for p in _EXTERNAL_CORPORA),
    reason="external corpora (LibCST, dagster, traffic) not present",
)
def test_external_corpus_zero_deletes() -> None:
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "axm_audit.cli",
        "audit",
        *(str(p) for p in _EXTERNAL_CORPORA),
        "--category",
        "test_quality",
        "--json",
    ]
    proc = subprocess.run(  # noqa: S603
        cmd,
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), (
        f"audit CLI failed unexpectedly (rc={proc.returncode}):\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )

    payload = json.loads(proc.stdout)
    findings = payload.get("findings", payload if isinstance(payload, list) else [])

    deletes = 0
    unknowns = 0
    for f in findings:
        rule_id = str(f.get("rule_id", ""))
        if "tautology" not in rule_id.lower():
            continue
        decision = str(f.get("verdict") or f.get("decision") or "")
        if decision == "DELETE":
            deletes += 1
        elif decision == "UNKNOWN":
            unknowns += 1

    assert deletes == 0, f"expected zero DELETE verdicts, got {deletes}"
    assert unknowns <= 3, f"expected UNKNOWN <= 3, got {unknowns}"
