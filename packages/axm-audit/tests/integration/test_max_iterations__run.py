"""Split from ``test_extract_helpers__pipeline.py``."""

import shutil
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.fix import run
from axm_audit.core.fix.models import MAX_ITERATIONS

_MISTIERED_IO_TEST = (
    "from pathlib import Path\n\n\n"
    "def test_writes_a_file(tmp_path):\n"
    "    p = tmp_path / 'x.txt'\n"
    "    p.write_text('hello')\n"
    "    assert p.read_text() == 'hello'\n"
)


def test_run_apply_then_dry_run_converges_to_zero_ops(make_test_pkg):
    """AC5: apply=True mutates; subsequent apply=False yields no ops."""
    pkg = make_test_pkg({"tests/unit/test_io.py": _MISTIERED_IO_TEST})

    first = run(pkg, apply=True)
    assert first.applied is True
    assert first.iterations >= 1
    assert first.iterations <= MAX_ITERATIONS
    assert len(first.ops) > 0

    second = run(pkg, apply=False)
    assert second.applied is False
    assert second.ops == []


def test_run_terminates_within_max_iterations(make_test_pkg):
    """AC8: fixed-point loop terminates within MAX_ITERATIONS=6."""
    pkg = make_test_pkg(
        {
            "tests/unit/test_io_a.py": _MISTIERED_IO_TEST,
            "tests/unit/test_io_b.py": (
                "from pathlib import Path\n\n\n"
                "def test_reads(tmp_path):\n"
                "    p = tmp_path / 'b.txt'\n"
                "    p.write_text('y')\n"
                "    assert p.read_text() == 'y'\n"
            ),
        }
    )

    report = run(pkg, apply=True)

    assert report.iterations >= 1
    assert report.iterations <= MAX_ITERATIONS


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
def test_corpus_converges_within_max_iterations(case_name: str, tmp_path: Path) -> None:
    """AC4: report.iterations <= MAX_ITERATIONS."""
    pkg = _prepare_case(case_name, tmp_path)

    report = run(pkg, apply=True)

    assert report.iterations <= MAX_ITERATIONS, (
        f"convergence violated for {case_name}: {report.iterations} > {MAX_ITERATIONS}"
    )
