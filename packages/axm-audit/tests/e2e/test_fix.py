"""E2E tests for `axm-audit fix` CLI subcommand (AXM-1749).

Covers the `fix` subcommand contract from AC1-AC8.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = pytest.mark.e2e


def _tree_hash(root: Path) -> str:
    """Stable hash of every file's relative path + bytes under *root*."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def _make_canonical_pkg(root: Path) -> Path:
    """Minimal pyramid-correct package with no fix-able findings."""
    pkg = root / "pkg"
    src = pkg / "src" / "sample"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "tests" / "unit").mkdir(parents=True)
    (pkg / "tests" / "unit" / "test_sample.py").write_text(
        "def test_one_plus_one() -> None:\n    assert 1 + 1 == 2\n"
    )
    (pkg / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "sample"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        ).lstrip()
    )
    return pkg


def _make_pkg_with_mis_tiered_test(root: Path) -> Path:
    """Package with a unit test doing real file I/O (should relocate to integration)."""
    pkg = _make_canonical_pkg(root)
    (pkg / "tests" / "unit" / "test_io_heavy.py").write_text(
        dedent(
            """
            from pathlib import Path

            def test_reads_file(tmp_path: Path) -> None:
                p = tmp_path / "foo.txt"
                p.write_text("data")
                assert p.read_text() == "data"
            """
        ).lstrip()
    )
    return pkg


def _make_pkg_with_failing_test(root: Path) -> Path:
    """Package containing a test that fails when executed."""
    pkg = _make_canonical_pkg(root)
    (pkg / "tests" / "unit" / "test_red.py").write_text(
        "def test_will_fail() -> None:\n    assert False\n"
    )
    return pkg


def test_fix_dry_run_on_clean_package_reports_no_ops(tmp_path: Path) -> None:
    """AC1: `axm-audit fix <path>` runs dry-run on a clean pkg, exits 0."""
    pkg = _make_canonical_pkg(tmp_path)

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "fix", str(pkg)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "(no deterministic ops planned)" in result.stdout


def test_fix_apply_mutates_tree(tmp_path: Path) -> None:
    """AC2: `axm-audit fix <path> --apply` relocates a mis-tiered test, exits 0."""
    pkg = _make_pkg_with_mis_tiered_test(tmp_path)
    mis_tiered = pkg / "tests" / "unit" / "test_io_heavy.py"
    assert mis_tiered.exists()

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "fix", str(pkg), "--apply"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "applied" in result.stdout
    assert not mis_tiered.exists(), "mis-tiered file should have been moved"
    moved = pkg / "tests" / "integration" / "test_io_heavy.py"
    assert moved.exists(), "file should land under tests/integration/"


def test_fix_rules_filter_excludes_relocate(tmp_path: Path) -> None:
    """AC3: --rules=TEST_QUALITY_FILE_NAMING runs only file-naming, no relocates."""
    pkg = _make_pkg_with_mis_tiered_test(tmp_path)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "axm-audit",
            "fix",
            str(pkg),
            "--rules=TEST_QUALITY_FILE_NAMING",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Stage RELOCATE" not in result.stdout
    assert "[relocate" not in result.stdout


def test_fix_nonexistent_path_exits_1() -> None:
    """AC4: nonexistent path exits 1 with `Not a directory` on stderr."""
    result = subprocess.run(
        ["uv", "run", "axm-audit", "fix", "/nonexistent/path/xyz"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Not a directory" in result.stderr


def test_fix_warns_on_red_baseline(tmp_path: Path) -> None:
    """AC5: a failing test in the suite triggers a baseline warning on stderr."""
    pkg = _make_pkg_with_failing_test(tmp_path)

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "fix", str(pkg)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stderr_lower = result.stderr.lower()
    assert "baseline" in stderr_lower or "red" in stderr_lower, (
        f"expected baseline/red warning, got stderr: {result.stderr!r}"
    )


def test_fix_help_shows_flags() -> None:
    """AC6: `axm-audit fix --help` documents the `--apply` and `--rules` flags."""
    result = subprocess.run(
        ["uv", "run", "axm-audit", "fix", "--help"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "--apply" in combined
    assert "--rules" in combined


def test_fix_no_arg_defaults_to_dot(tmp_path: Path) -> None:
    """AC7: `axm-audit fix` (no arg) defaults `path` to the current directory."""
    pkg = _make_canonical_pkg(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "fix"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=pkg,
    )

    assert result.returncode == 0, result.stderr
    assert "(no deterministic ops planned)" in result.stdout


def test_fix_apply_atomic_on_failure(tmp_path: Path) -> None:
    """AC1: `axm-audit fix --apply` on a corpus whose apply yields an
    un-collectable tree exits non-zero and leaves tests/ unchanged on disk.
    """
    pkg = _make_pkg_with_mis_tiered_test(tmp_path)
    # A syntactically broken test forces the post-apply collection gate to
    # fail, which must trigger the atomic rollback (AC1/AC5).
    (pkg / "tests" / "unit" / "test_broken.py").write_text(
        "def test_add( :\n    pass\n"
    )
    tests = pkg / "tests"
    before = _tree_hash(tests)

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "fix", str(pkg), "--apply"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout
    assert _tree_hash(tests) == before
