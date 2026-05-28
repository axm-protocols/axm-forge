"""Integration tests for extract_helpers + pipeline run().

Real filesystem + git + libcst. Covers the ``_extract_shared_helpers``
post-pipeline polish, ``_ruff_format_tests`` polish, and end-to-end
``run()`` behaviour (dry-run, apply, convergence, mixed-tier residue,
partial rule selection, iteration cap).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.core.fix import run

pytestmark = pytest.mark.integration


_MISTIERED_IO_TEST = (
    "from pathlib import Path\n\n\n"
    "def test_writes_a_file(tmp_path):\n"
    "    p = tmp_path / 'x.txt'\n"
    "    p.write_text('hello')\n"
    "    assert p.read_text() == 'hello'\n"
)


def test_extract_shared_helpers_consolidates_identical_helpers(make_test_pkg):
    """AC1: identical _helper across two files collapses into _helpers.py.

    Drives the post-pipeline extract-helpers polish through the public
    ``run()`` seam with an empty rule set (skips relocate/naming stages
    so only the post-polish path executes).
    """
    helper_def = "def _helper(x):\n    return x * 2\n\n\n"
    pkg = make_test_pkg(
        {
            "tests/integration/test_a.py": (
                helper_def + "def test_a():\n    assert _helper(1) == 2\n"
            ),
            "tests/integration/test_b.py": (
                helper_def + "def test_b():\n    assert _helper(2) == 4\n"
            ),
        }
    )

    report = run(pkg, apply=True, rules=set())

    helpers_file = pkg / "tests" / "integration" / "_helpers.py"
    assert helpers_file.exists()
    helpers_body = helpers_file.read_text()
    assert "def _helper" in helpers_body

    src_a = (pkg / "tests" / "integration" / "test_a.py").read_text()
    src_b = (pkg / "tests" / "integration" / "test_b.py").read_text()
    assert "def _helper" not in src_a
    assert "def _helper" not in src_b
    assert "_helper" in src_a and "import" in src_a
    assert "_helper" in src_b and "import" in src_b
    assert any("extracted helper" in m and "_helper" in m for m in report.warnings)


def test_extract_shared_helpers_keeps_divergent_per_file(make_test_pkg):
    """AC2: divergent _helper bodies stay per-file; warning names both.

    Same public ``run()`` seam as AC1 — divergent bodies produce an
    ``ambiguous helper`` warning instead of an extraction.
    """
    pkg = make_test_pkg(
        {
            "tests/integration/test_a.py": (
                "def _helper(x):\n    return x * 2\n\n\n"
                "def test_a():\n    assert _helper(1) == 2\n"
            ),
            "tests/integration/test_b.py": (
                "def _helper(x):\n    return x + 100\n\n\n"
                "def test_b():\n    assert _helper(1) == 101\n"
            ),
        }
    )

    report = run(pkg, apply=True, rules=set())

    helpers_file = pkg / "tests" / "integration" / "_helpers.py"
    assert not helpers_file.exists()
    assert "x * 2" in (pkg / "tests" / "integration" / "test_a.py").read_text()
    assert "x + 100" in (pkg / "tests" / "integration" / "test_b.py").read_text()

    blob = "\n".join(report.warnings)
    assert "ambiguous" in blob
    assert "test_a.py" in blob and "test_b.py" in blob


def test_ruff_format_tests_formats_and_swallows_warnings(make_test_pkg):
    """AC3: post-polish formats tests/ and surfaces only soft warnings.

    Drives the ruff-format polish stage through ``run(apply=True)`` with
    an empty rule set so relocate/naming don't touch the file before
    polish has a chance to reformat it.
    """
    misformatted = "def test_x( ):\n    x =1\n    y= 2\n    assert  x+y==3\n"
    pkg = make_test_pkg({"tests/unit/test_x.py": misformatted})

    report = run(pkg, apply=True, rules=set())

    body = (pkg / "tests" / "unit" / "test_x.py").read_text()
    if "skipped: ruff not on PATH" not in "\n".join(report.warnings):
        assert "x = 1" in body
        assert "y = 2" in body
        assert "x + y == 3" in body
    for m in report.warnings:
        assert "Traceback" not in m
        assert "raise " not in m


def test_run_mixed_tier_emits_unfixable_residue(make_test_pkg):
    """AC6: disagreeing classification -> no relocate; unfixable carries residue."""
    body = (
        "from pathlib import Path\n\n\n"
        "def test_with_io(tmp_path):\n"
        "    (tmp_path / 'a').write_text('x')\n"
        "    assert (tmp_path / 'a').read_text() == 'x'\n\n\n"
        "def test_no_io():\n"
        "    assert 1 + 1 == 2\n"
    )
    pkg = make_test_pkg({"tests/integration/test_mixed.py": body})

    report = run(pkg, apply=True)

    mixed_path = pkg / "tests" / "integration" / "test_mixed.py"
    assert mixed_path.exists()
    for op in report.ops:
        if op.kind != "relocate":
            continue
        assert Path(str(op.source)).name != "test_mixed.py"
    assert len(report.unfixable) > 0


def test_run_partial_rule_selection_excludes_relocate(make_test_pkg):
    """AC7: rules={FILE_NAMING} -> no relocate op even with mis-tiered input."""
    pkg = make_test_pkg({"tests/unit/test_io.py": _MISTIERED_IO_TEST})

    report = run(pkg, apply=True, rules={"TEST_QUALITY_FILE_NAMING"})

    assert all(op.kind != "relocate" for op in report.ops)
    assert (pkg / "tests" / "unit" / "test_io.py").exists()
    assert not (pkg / "tests" / "integration" / "test_io.py").exists()


CORPUS_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "fix_corpus"

_SKIP_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
)

TEST_QUALITY_RULES = frozenset(
    {"TEST_QUALITY_FILE_NAMING", "TEST_QUALITY_PYRAMID_LEVEL"}
)


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
def test_corpus_findings_monotonic(case_name: str, tmp_path: Path) -> None:
    """AC5: TEST_QUALITY_* finding count post-apply <= pre-apply."""
    pkg = _prepare_case(case_name, tmp_path)
    pre = _test_quality_findings(pkg)

    run(pkg, apply=True)

    post = _test_quality_findings(pkg)
    assert post <= pre, f"findings increased for {case_name}: {pre} -> {post}"


def test_run_on_empty_package_returns_empty_plan(tmp_path: Path) -> None:
    """AC2: pipeline on a package with only an empty tests/ dir yields no ops."""
    from axm_audit.core.fix import run

    (tmp_path / "tests").mkdir()

    report = run(tmp_path)

    assert report.ops == []
    assert report.applied is False
