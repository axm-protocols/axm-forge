"""Property tests for the audit.fix pipeline on the synthetic corpus.

Covers idempotence (AC2), parity (AC3), convergence (AC4), monotonicity
(AC5) and tree-diff (AC1) over the fixtures in ``tests/fixtures/fix_corpus``.
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

pytestmark = pytest.mark.integration

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "fix_corpus"

TEST_QUALITY_RULES = frozenset(
    {"TEST_QUALITY_FILE_NAMING", "TEST_QUALITY_PYRAMID_LEVEL"}
)

_SKIP_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
)


def _corpus_cases() -> list[str]:
    if not CORPUS_ROOT.exists():
        return []
    return sorted(
        p.name
        for p in CORPUS_ROOT.iterdir()
        if p.is_dir() and (p / "input").is_dir() and (p / "expected").is_dir()
    )


CASES = _corpus_cases()


def _prepare_case(case_name: str, tmp_path: Path) -> Path:
    src = CORPUS_ROOT / case_name / "input"
    dst = tmp_path / case_name
    shutil.copytree(src, dst)
    git_bin = shutil.which("git")
    if git_bin is not None:
        subprocess.run(  # noqa: S603
            [git_bin, "init", "--quiet"],
            cwd=dst,
            check=True,
            capture_output=True,
            timeout=30,
        )
    return dst


def _normalize(content: str) -> str:
    lines = [line.rstrip() for line in content.splitlines()]
    normalized = "\n".join(lines).rstrip() + "\n"
    ruff_bin = shutil.which("ruff")
    if ruff_bin is None:
        return normalized
    try:
        result = subprocess.run(  # noqa: S603
            [ruff_bin, "format", "-"],
            input=normalized,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return normalized
    if result.returncode == 0:
        return result.stdout
    return normalized


def _walk_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        rel = "/".join(rel_parts)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out[rel] = "<binary:" + path.read_bytes().hex() + ">"
            continue
        if path.suffix == ".py":
            out[rel] = _normalize(text)
        else:
            out[rel] = text.rstrip() + "\n" if text else text
    return out


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


def _coverage(report: object) -> float | None:
    for attr in ("coverage_total", "coverage_percent", "coverage"):
        value = getattr(report, attr, None)
        if value is None:
            continue
        if isinstance(value, int | float):
            return float(value)
        pct = getattr(value, "percent", None) or getattr(value, "total", None)
        if pct is not None:
            return float(pct)
    return None


_no_corpus = pytest.mark.skipif(
    not CASES, reason="fix_corpus fixtures not yet generated (depends on T10)"
)


@_no_corpus
@pytest.mark.parametrize("case_name", CASES)
def test_corpus_matches_expected_tree(case_name: str, tmp_path: Path) -> None:
    """AC1: post-apply tree exactly matches the expected/ directory."""
    pkg = _prepare_case(case_name, tmp_path)
    run(pkg, apply=True)

    actual = _walk_tree(pkg)
    expected = _walk_tree(CORPUS_ROOT / case_name / "expected")

    assert sorted(actual.keys()) == sorted(expected.keys()), (
        f"file list mismatch for {case_name}: "
        f"only-actual={sorted(set(actual) - set(expected))}, "
        f"only-expected={sorted(set(expected) - set(actual))}"
    )
    for rel in sorted(expected):
        assert actual[rel] == expected[rel], f"content mismatch in {case_name}::{rel}"


@_no_corpus
@pytest.mark.parametrize("case_name", CASES)
def test_corpus_idempotent(case_name: str, tmp_path: Path) -> None:
    """AC2: a second dry-run after apply yields report.ops == []."""
    pkg = _prepare_case(case_name, tmp_path)
    run(pkg, apply=True)

    second = run(pkg, apply=False)

    assert second.ops == [], f"idempotence violated for {case_name}: {second.ops}"


@_no_corpus
@pytest.mark.parametrize("case_name", CASES)
def test_corpus_test_parity(case_name: str, tmp_path: Path) -> None:
    """AC3: pre/post pass count equal and coverage delta <= 0.1%."""
    pkg = _prepare_case(case_name, tmp_path)
    pre = run_tests(pkg, stop_on_first=False)
    if _failed(pre) > 0:
        pytest.skip("baseline is red")
    pre_pass = _passed(pre)
    pre_cov = _coverage(pre)

    run(pkg, apply=True)

    post = run_tests(pkg, stop_on_first=False)
    post_pass = _passed(post)
    post_cov = _coverage(post)

    assert pre_pass == post_pass, (
        f"pass count changed for {case_name}: {pre_pass} -> {post_pass}"
    )
    if pre_cov is not None and post_cov is not None:
        assert abs(pre_cov - post_cov) <= 0.1, (
            f"coverage delta too large for {case_name}: {pre_cov:.3f} -> {post_cov:.3f}"
        )


@_no_corpus
@pytest.mark.parametrize("case_name", CASES)
def test_corpus_converges_within_max_iterations(case_name: str, tmp_path: Path) -> None:
    """AC4: report.iterations <= MAX_ITERATIONS."""
    pkg = _prepare_case(case_name, tmp_path)

    report = run(pkg, apply=True)

    assert report.iterations <= MAX_ITERATIONS, (
        f"convergence violated for {case_name}: {report.iterations} > {MAX_ITERATIONS}"
    )


@_no_corpus
@pytest.mark.parametrize("case_name", CASES)
def test_corpus_findings_monotonic(case_name: str, tmp_path: Path) -> None:
    """AC5: TEST_QUALITY_* finding count post-apply <= pre-apply."""
    pkg = _prepare_case(case_name, tmp_path)
    pre = _test_quality_findings(pkg)

    run(pkg, apply=True)

    post = _test_quality_findings(pkg)
    assert post <= pre, f"findings increased for {case_name}: {pre} -> {post}"
