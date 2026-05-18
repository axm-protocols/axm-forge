from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.structure import TestsPyramidRule

pytestmark = pytest.mark.e2e


def _make_pkg(root: Path, name: str, files: dict[str, str]) -> None:
    pkg_src = root / "packages" / name / "src" / name.replace("-", "_")
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    for fname, content in files.items():
        (pkg_src / fname).write_text(textwrap.dedent(content))
    (root / "packages" / name / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )


def test_cli_audit_multi_package_workspace(tmp_path: Path) -> None:
    _make_pkg(tmp_path, "pkg-broken", {"bad.py": "def f():\n    x = 1\n    return 0\n"})
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary not found on PATH")

    proc = subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "axm-audit",
            "audit",
            str(tmp_path),
            "--category",
            "lint",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0 or proc.stdout, "expected output"
    out = proc.stdout
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        pytest.fail(f"expected JSON output, got: {out!r}")
    blob = json.dumps(payload)
    assert "pkg-broken" in blob
    assert "pkg-clean" in blob or proc.returncode != 0


PYPROJECT = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"

    [tool.pytest.ini_options]
    markers = [
        "integration: integration tests",
        "e2e: end-to-end tests",
    ]
    """
).strip()


def test_cli_audit_structure_shows_pyramid(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    for d in ("tests/unit", "tests/integration", "tests/e2e"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")

    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "axm-audit",
            "audit",
            str(tmp_path),
            "--category",
            "structure",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    payload = json.loads(proc.stdout)
    checks = payload.get("checks", [])
    pyramid_rule_id = TestsPyramidRule().rule_id
    assert any(c.get("rule_id") == pyramid_rule_id for c in checks)


def test_cli_help_lists_test_quality() -> None:
    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", "--help"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "test_quality" in combined
    assert "testing" in combined


def test_cli_invalid_category_lists_valid(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "audit", str(pkg), "--category", "bogus"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "test_quality" in combined


def _make_clean_project(root: Path) -> None:
    """Build a minimal package with no test_quality findings.

    A real package layout is required so the rules can run, but the test
    suite is intentionally trivial and pyramid-correct.
    """
    (root / "src" / "sample").mkdir(parents=True)
    (root / "src" / "sample" / "__init__.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_sample.py").write_text(
        dedent(
            """
            from sample import add

            def test_add() -> None:
                assert add(2, 3) == 5
            """
        ).lstrip()
    )
    (root / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "sample"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        ).lstrip()
    )


@pytest.mark.e2e
def test_cli_runs_test_quality_category(tmp_path: Path) -> None:
    """`audit . --category test_quality` runs to completion and emits output.

    The exit code reflects whether the project passes the score threshold;
    we only require that the CLI ran without crashing (returncode in {0, 1})
    and produced visible output mentioning the audited category.
    """
    _make_clean_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", ".", "--category", "test_quality"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode in (0, 1), (
        f"CLI crashed (rc={result.returncode}): {result.stderr}"
    )
    assert result.stdout != ""


@pytest.mark.e2e
def test_cli_test_quality_category_passes_on_clean_project(tmp_path: Path) -> None:
    """On a project with no test_quality issues, exit code is 0."""
    _make_clean_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", ".", "--category", "test_quality"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode == 0, (
        f"clean project should pass test_quality\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
