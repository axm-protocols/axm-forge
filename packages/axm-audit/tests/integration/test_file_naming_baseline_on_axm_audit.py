"""Baseline regression guard for FileNamingRule on axm-audit itself.

Running the rule on the package's own source/tests must produce a stable
set of findings. The snapshot lives at
``tests/unit/core/rules/test_quality/_baselines/axm_audit_file_naming.json``
and is updated only by an explicit chantier — never silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.file_naming import FileNamingRule

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = (
    _REPO_ROOT
    / "tests"
    / "unit"
    / "core"
    / "rules"
    / "test_quality"
    / "_baselines"
    / "axm_audit_file_naming.json"
)


def _normalize(finding: dict[str, object]) -> dict[str, object]:
    """Strip any non-deterministic fields prior to comparison."""
    keep = {
        "verdict",
        "severity",
        "tier",
        "current_name",
        "proposed_name",
        "canonical_name",
        "files",
        "path",
        "tuple",
        "tuples",
        "suggested_splits",
    }
    out: dict[str, object] = {k: finding[k] for k in keep if k in finding}
    for k in ("files", "tuple", "tuples", "suggested_splits"):
        if k in out and isinstance(out[k], list):
            out[k] = sorted(out[k], key=lambda x: json.dumps(x, sort_keys=True))
    return out


def test_findings_match_committed_baseline() -> None:
    """AC10 — findings on axm-audit itself match the committed snapshot."""
    assert _BASELINE.exists(), f"baseline missing: {_BASELINE}"
    snapshot = json.loads(_BASELINE.read_text())
    expected = sorted(
        (_normalize(f) for f in snapshot.get("findings", [])),
        key=lambda f: json.dumps(f, sort_keys=True),
    )

    result = FileNamingRule().check(_REPO_ROOT)
    raw = list(result.details.get("findings", [])) if result.details else []
    actual = sorted(
        (_normalize(f) for f in raw),
        key=lambda f: json.dumps(f, sort_keys=True),
    )

    assert actual == expected, (
        "FileNamingRule findings drifted from baseline. "
        "If this drift is intentional, regenerate "
        f"{_BASELINE.relative_to(_REPO_ROOT)} via the documented chantier."
    )
