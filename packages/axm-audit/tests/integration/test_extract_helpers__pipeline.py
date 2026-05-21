"""Integration tests for extract_helpers + pipeline run().

Real filesystem + git + libcst. Covers the ``_extract_shared_helpers``
post-pipeline polish, ``_ruff_format_tests`` polish, and end-to-end
``run()`` behaviour (dry-run, apply, convergence, mixed-tier residue,
partial rule selection, iteration cap).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix import run
from axm_audit.core.fix.extract_helpers import _extract_shared_helpers
from axm_audit.core.fix.models import MAX_ITERATIONS, PipelineReport
from axm_audit.core.fix.pipeline import _ruff_format_tests

pytestmark = pytest.mark.integration


@pytest.fixture
def make_test_pkg(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Build a minimal git-initialised package with the given source files."""

    def _make(sources: dict[str, str]) -> Path:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
        )
        (pkg / "src").mkdir()
        (pkg / "src" / "pkg").mkdir()
        (pkg / "src" / "pkg" / "__init__.py").write_text("")
        (pkg / "tests").mkdir()
        for rel, content in sources.items():
            f = pkg / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],  # noqa: S607
            cwd=pkg,
            check=True,
            capture_output=True,
        )
        return pkg

    return _make


_MISTIERED_IO_TEST = (
    "from pathlib import Path\n\n\n"
    "def test_writes_a_file(tmp_path):\n"
    "    p = tmp_path / 'x.txt'\n"
    "    p.write_text('hello')\n"
    "    assert p.read_text() == 'hello'\n"
)


def test_extract_shared_helpers_consolidates_identical_helpers(make_test_pkg):
    """AC1: identical _helper across two files collapses into _helpers.py."""
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

    msgs = _extract_shared_helpers(pkg)

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
    assert any("extracted helper" in m and "_helper" in m for m in msgs)


def test_extract_shared_helpers_keeps_divergent_per_file(make_test_pkg):
    """AC2: divergent _helper bodies stay per-file; warning names both."""
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

    msgs = _extract_shared_helpers(pkg)

    helpers_file = pkg / "tests" / "integration" / "_helpers.py"
    assert not helpers_file.exists()
    assert "x * 2" in (pkg / "tests" / "integration" / "test_a.py").read_text()
    assert "x + 100" in (pkg / "tests" / "integration" / "test_b.py").read_text()

    blob = "\n".join(msgs)
    assert "ambiguous" in blob
    assert "test_a.py" in blob and "test_b.py" in blob


def test_ruff_format_tests_formats_and_swallows_warnings(make_test_pkg):
    """AC3: _ruff_format_tests formats tests/ and surfaces only soft warnings."""
    misformatted = "def test_x( ):\n    x =1\n    y= 2\n    assert  x+y==3\n"
    pkg = make_test_pkg({"tests/unit/test_x.py": misformatted})

    msgs = _ruff_format_tests(pkg)

    body = (pkg / "tests" / "unit" / "test_x.py").read_text()
    if "skipped: ruff not on PATH" not in "\n".join(msgs):
        assert "x = 1" in body
        assert "y = 2" in body
        assert "x + y == 3" in body
    for m in msgs:
        assert "Traceback" not in m
        assert "raise " not in m


def test_run_dry_run_does_not_mutate(make_test_pkg):
    """AC4: apply=False -> applied=False, iterations=1, source unchanged."""
    pkg = make_test_pkg({"tests/unit/test_io.py": _MISTIERED_IO_TEST})
    before = (pkg / "tests" / "unit" / "test_io.py").read_text()

    report = run(pkg, apply=False)

    assert isinstance(report, PipelineReport)
    assert report.applied is False
    assert report.iterations == 1
    assert (pkg / "tests" / "unit" / "test_io.py").read_text() == before
    assert not (pkg / "tests" / "integration" / "test_io.py").exists()


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
