from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule

pytestmark = pytest.mark.integration

AXM_TICKET_PATH = Path(
    "/Users/gabriel/Documents/Code/python/axm-workspaces/axm-hub/packages/axm-ticket"
)
PROTOTYPE_SCRIPT = AXM_TICKET_PATH / "detect_duplicates.py"


def _rule_tuples(result) -> set[tuple[str, str, str]]:
    tuples: set[tuple[str, str, str]] = set()
    for cluster in result.metadata["clusters"]:
        signal = cluster["signal"]
        for t in cluster["tests"]:
            tuples.add((t["file"], t["name"], signal))
    return tuples


def _prototype_tuples(raw: object) -> set[tuple[str, str, str]]:
    tuples: set[tuple[str, str, str]] = set()
    if isinstance(raw, dict):
        clusters = raw.get("clusters", [])
    else:
        clusters = raw
    for cluster in clusters:
        signal = cluster["signal"]
        for t in cluster["tests"]:
            tuples.add((t["file"], t["name"], signal))
    return tuples


@pytest.mark.skipif(
    not AXM_TICKET_PATH.exists(), reason="axm-ticket fixture not available"
)
@pytest.mark.skipif(
    not PROTOTYPE_SCRIPT.exists(), reason="detect_duplicates.py prototype missing"
)
def test_axm_ticket_threshold_0_8_matches_prototype() -> None:
    rule = DuplicateTestsRule(ast_similarity_threshold=0.8)
    result = rule.check(AXM_TICKET_PATH)

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(PROTOTYPE_SCRIPT), "--threshold=0.8", "--json"],
        cwd=AXM_TICKET_PATH,
        capture_output=True,
        text=True,
        check=True,
    )
    prototype = json.loads(proc.stdout)

    assert _rule_tuples(result) == _prototype_tuples(prototype)
