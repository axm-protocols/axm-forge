from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.structure import TestsPyramidRule

pytestmark = pytest.mark.e2e

_UNPAIRED_COGNITIVE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "unpaired_cognitive"
    / "sample.py"
)
_HAS_COMPLEXIPY = importlib.util.find_spec("complexipy") is not None


def _make_unpaired_cognitive_project(root: Path) -> None:
    """Materialise a src-layout project that fires the complexity diagnostic.

    The fixture's class blocks have no paired complexipy entry, so auditing the
    ``complexity`` category emits the ``no cognitive score paired`` warning while
    still producing a numeric score (no offenders).
    """
    src = root / "src" / "uc"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "sample.py").write_text(_UNPAIRED_COGNITIVE_FIXTURE.read_text())
    (root / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "uc"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        ).lstrip()
    )


def _run_complexity_json(root: Path) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary not found on PATH")
    return subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "axm-audit",
            "audit",
            str(root),
            "--category",
            "complexity",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_audit_json_score_numeric_under_complexity_diagnostics(
    tmp_path: Path,
) -> None:
    """AC1: `audit <fixture> --json | jq .score` yields a number with the
    complexity `no cognitive score paired` diagnostic firing."""
    _make_unpaired_cognitive_project(tmp_path)
    proc = _run_complexity_json(tmp_path)

    # stdout is a single valid JSON document (would raise otherwise).
    payload = json.loads(proc.stdout)
    assert isinstance(payload["score"], int | float)
    # No diagnostic text leaks into the JSON stdout payload.
    assert "no cognitive score paired" not in proc.stdout


@pytest.mark.skipif(
    not _HAS_COMPLEXIPY,
    reason="complexipy required for the cognitive-pairing diagnostic to fire",
)
def test_cli_audit_json_diagnostics_on_stderr_not_stdout(tmp_path: Path) -> None:
    """AC2: in `--json` mode the complexity diagnostic appears on stderr and is
    absent from stdout, which stays a single valid JSON document."""
    _make_unpaired_cognitive_project(tmp_path)
    proc = _run_complexity_json(tmp_path)

    assert "no cognitive score paired" in proc.stderr
    assert "no cognitive score paired" not in proc.stdout
    # stdout parses as one JSON document — no diagnostic interleaving.
    json.loads(proc.stdout)


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


def test_audit_type_cli_fails_on_missing_stub(tmp_path: Path) -> None:
    """AC1: `axm-audit audit --category type` on a package importing an
    unstubbed/missing lib must NOT score 100 — it fails loud with a report
    naming the missing import."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary not found on PATH")

    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"
            version = "0.1.0"
            requires-python = ">=3.12"
            """
        ).strip()
    )
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    # Imports a module that does not exist in the env (import-not-found),
    # plus a real type error — reproduces the AXM-1878 masking scenario.
    (src / "client.py").write_text(
        dedent(
            """
            import totallymissingmod_axm1900

            def call() -> int:
                return totallymissingmod_axm1900.run()
            """
        ).strip()
        + "\n"
    )

    proc = subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "axm-audit",
            "audit",
            str(tmp_path),
            "--category",
            "type",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(proc.stdout)
    blob = json.dumps(payload)
    # Must surface the missing import — not a silent 100.
    assert "totallymissingmod_axm1900" in blob or '"score": 100' not in blob
    assert '"passed": true' not in blob.lower() or "100" not in blob


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


@pytest.mark.e2e
def test_workspace_audit_cli_unchanged_output(tmp_path: Path) -> None:
    """AC2: workspace audit JSON output is stable under parallelism.

    Runs the CLI twice over the same temp 2-package workspace; the parallel
    execution must yield a deterministic report (same exit code, same set of
    rule_ids and per-rule passed flags) across runs and across packages.
    """
    _make_pkg(tmp_path, "pkg-broken", {"bad.py": "def f():\n    x = 1\n    return 0\n"})
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary not found on PATH")

    def _run() -> tuple[int, str]:
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
        return proc.returncode, proc.stdout

    rc1, out1 = _run()
    rc2, out2 = _run()

    assert rc1 == rc2
    payload1 = json.loads(out1)
    payload2 = json.loads(out2)

    def _sig(payload: dict[str, object]) -> list[tuple[str, bool]]:
        checks = payload.get("checks", [])
        assert isinstance(checks, list)
        return sorted((c.get("rule_id", ""), c.get("passed", False)) for c in checks)

    assert _sig(payload1) == _sig(payload2)
    blob = json.dumps(payload1)
    assert "pkg-broken" in blob
    assert "pkg-clean" in blob or rc1 != 0
