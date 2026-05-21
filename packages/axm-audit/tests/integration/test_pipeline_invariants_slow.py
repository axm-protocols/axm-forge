"""Slow invariants test on a self-copy of axm-audit (AC6).

Clones the package locally via ``git clone --depth 1`` and runs the full
invariant suite. Opt-in via ``-m slow``; not part of the default run.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.core.fix import run
from axm_audit.core.fix.models import MAX_ITERATIONS
from axm_audit.core.test_runner import run_tests

pytestmark = [pytest.mark.slow, pytest.mark.integration]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

TEST_QUALITY_RULES = frozenset(
    {"TEST_QUALITY_FILE_NAMING", "TEST_QUALITY_PYRAMID_LEVEL"}
)


def _test_quality_findings(project_path: Path) -> int:
    result = audit_project(project_path)
    total = 0
    for check in result.checks:
        rule = getattr(check, "rule", None) or getattr(check, "name", None)
        if rule in TEST_QUALITY_RULES:
            findings = getattr(check, "findings", None) or getattr(check, "issues", [])
            total += len(findings)
    return total


def _passed(report: object) -> int:
    summary = getattr(report, "summary", None)
    if summary is not None:
        return int(getattr(summary, "passed", 0))
    return int(getattr(report, "passed", 0))


def _failed(report: object) -> int:
    summary = getattr(report, "summary", None)
    if summary is not None:
        return int(getattr(summary, "failed", 0))
    return int(getattr(report, "failed", 0))


def test_invariants_on_axm_audit_self_copy(tmp_path: Path) -> None:
    """AC6: idempotence + parity + convergence + monotonicity on self-copy."""
    git_bin = shutil.which("git")
    if git_bin is None:
        pytest.skip("git not available")
    if (
        not (PACKAGE_ROOT / ".git").exists()
        and not (PACKAGE_ROOT.parent.parent / ".git").exists()
    ):
        pytest.skip("axm-audit not inside a git checkout")

    clone_dst = tmp_path / "axm-audit"
    clone_result = subprocess.run(  # noqa: S603
        [
            git_bin,
            "clone",
            "--depth",
            "1",
            "file://" + str(PACKAGE_ROOT),
            str(clone_dst),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if clone_result.returncode != 0:
        pytest.skip(f"git clone failed: {clone_result.stderr.strip()}")

    # Baseline test run for parity (AC3).
    pre_report = run_tests(clone_dst, stop_on_first=False)
    baseline_red = _failed(pre_report) > 0
    pre_pass = _passed(pre_report)

    # Baseline findings count for monotonicity (AC5).
    pre_findings = _test_quality_findings(clone_dst)

    # Apply pipeline.
    report = run(clone_dst, apply=True)

    # AC4: convergence.
    assert report.iterations <= MAX_ITERATIONS, (
        f"convergence violated: {report.iterations} > {MAX_ITERATIONS}"
    )

    # AC2: idempotence.
    second = run(clone_dst, apply=False)
    assert second.ops == [], f"idempotence violated: {second.ops}"

    # AC5: monotonicity.
    post_findings = _test_quality_findings(clone_dst)
    assert post_findings <= pre_findings, (
        f"findings increased on self-copy: {pre_findings} -> {post_findings}"
    )

    # AC3: parity (skip if baseline was red — meaningless comparison).
    if baseline_red:
        pytest.skip("baseline is red on self-copy; parity check skipped")
    post_report = run_tests(clone_dst, stop_on_first=False)
    post_pass = _passed(post_report)
    assert pre_pass == post_pass, (
        f"pass count changed on self-copy: {pre_pass} -> {post_pass}"
    )
