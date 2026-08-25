"""Split from ``test_pipeline_invariants.py``."""

import shutil
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.fix import run
from axm_audit.core.test_runner import run_tests

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "fix_corpus"


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


def _corpus_cases() -> list[str]:
    if not CORPUS_ROOT.exists():
        return []
    return sorted(
        p.name
        for p in CORPUS_ROOT.iterdir()
        if p.is_dir() and (p / "input").is_dir() and (p / "expected").is_dir()
    )


CASES = _corpus_cases()

_no_corpus = pytest.mark.skipif(
    not CASES, reason="fix_corpus fixtures not yet generated (depends on T10)"
)


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
