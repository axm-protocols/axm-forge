"""E2E tests for hash-based cluster acknowledgement via the CLI (axm-1727)."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.e2e


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def _make_project_with_duplicates(root: Path) -> None:
    """Build a minimal package containing one duplicate-test cluster."""
    (root / "src" / "sample").mkdir(parents=True)
    (root / "src" / "sample" / "__init__.py").write_text(
        "def parse(x: int) -> int:\n    return 1\n"
    )
    _write(
        root / "tests" / "unit" / "test_sample.py",
        """
        from sample import parse

        def test_parse_one():
            result = parse(1)
            assert result == 1
            assert result > 0

        def test_parse_two():
            result = parse(2)
            assert result == 1
            assert result > 0
        """,
    )


def _run_audit(project: Path) -> subprocess.CompletedProcess[str]:
    cmd = [
        "uv",
        "run",
        "axm-audit",
        "audit",
        ".",
        "--category",
        "test_quality",
        "--json",
    ]
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=project,
    )


def _find_rule(payload: object, rule_name: str) -> dict[str, Any] | None:
    """Locate the rule entry by name in any reasonable JSON shape."""
    stack: list[object] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if (
                node.get("rule_id") == rule_name
                or node.get("rule") == rule_name
                or node.get("name") == rule_name
            ):
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


def _extract_cluster_hash(project: Path) -> str:
    """Run the rule via Python API to read out the cluster hash for ack setup."""
    from axm_audit.core.rules.test_quality.duplicate_tests import (
        DuplicateTestsRule,
    )

    result = DuplicateTestsRule().check(project)
    clusters: list[dict[str, Any]] = list(result.metadata["clusters"])
    assert clusters, "setup error: expected at least one duplicate cluster"
    return str(clusters[0]["cluster_hash"])


def _write_pyproject(project: Path, entries: list[tuple[str, str]]) -> None:
    body = [
        "[project]",
        'name = "sample"',
        'version = "0.0.0"',
        'requires-python = ">=3.12"',
    ]
    for h, reason in entries:
        body += [
            "",
            "[[tool.axm-audit.duplicate_tests.acknowledged]]",
            f'hash = "{h}"',
            f'reason = "{reason}"',
        ]
    (project / "pyproject.toml").write_text("\n".join(body) + "\n")


def test_acknowledged_cluster_yields_passing_audit(tmp_path: Path) -> None:
    """AC3, AC5: matching ack hash → rule passes via CLI JSON output."""
    _make_project_with_duplicates(tmp_path)
    h = _extract_cluster_hash(tmp_path)
    _write_pyproject(tmp_path, [(h, "validated via e2e")])

    proc = _run_audit(tmp_path)
    assert proc.returncode == 0, (
        f"audit failed: rc={proc.returncode} stdout={proc.stdout[-500:]!r} "
        f"stderr={proc.stderr[-500:]!r}"
    )
    payload = json.loads(proc.stdout)
    rule = _find_rule(payload, "TEST_QUALITY_DUPLICATE_TESTS")
    assert rule is not None, f"rule entry not found in {payload!r}"
    assert rule.get("passed") is True
    clusters = rule.get("metadata", {}).get("clusters", [])
    acked = [c for c in clusters if c.get("cluster_hash") == h]
    assert acked and acked[0].get("acknowledged") is True


def test_stale_acknowledgement_warned_but_no_failure(tmp_path: Path) -> None:
    """AC4, AC5: stale hash → stale_acknowledged populated.

    Audit didn't error.
    """
    _make_project_with_duplicates(tmp_path)
    fake_hash = "deadbeef0000"
    _write_pyproject(tmp_path, [(fake_hash, "stale entry")])

    proc = _run_audit(tmp_path)
    # The live cluster is still flagged → exit reflects failure, but the CLI
    # did not crash (returncode is 0 or 1, never an exception-style code).
    assert proc.returncode in (0, 1), (
        f"audit crashed: rc={proc.returncode} stderr={proc.stderr[-500:]!r}"
    )
    payload = json.loads(proc.stdout)
    rule = _find_rule(payload, "TEST_QUALITY_DUPLICATE_TESTS")
    assert rule is not None
    stale = rule.get("metadata", {}).get("stale_acknowledged", [])
    stale_hashes = [entry["hash"] for entry in stale]
    assert fake_hash in stale_hashes
    assert rule.get("passed") is False
