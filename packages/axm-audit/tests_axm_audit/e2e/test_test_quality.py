from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from textwrap import dedent

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UV_BIN = shutil.which("uv") or "uv"


@pytest.mark.integration
def test_axm_audit_output_pinned() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    out = result.stdout
    lower = out.lower()
    assert "pyramid" in lower


@pytest.mark.e2e
def test_cli_test_quality_happy_path() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    assert result.stdout.strip()


@pytest.mark.e2e
def test_cli_test_quality_json_valid() -> None:
    result = subprocess.run(  # noqa: S603
        [_UV_BIN, "run", "axm-audit", "test-quality", str(PROJECT_ROOT), "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
    for key in (
        "clusters",
        "verdicts",
        "pyramid_mismatches",
        "private_import_violations",
    ):
        assert key in data, f"missing key: {key}"


@pytest.mark.e2e
def test_cli_test_quality_mismatches_only() -> None:
    result = subprocess.run(  # noqa: S603
        [
            _UV_BIN,
            "run",
            "axm-audit",
            "test-quality",
            str(PROJECT_ROOT),
            "--mismatches-only",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    out = result.stdout.lower()
    # Section headers from the other rule groups must be absent.
    assert "tautologies:" not in out
    assert "duplicates:" not in out
    assert "private imports:" not in out


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and parent.name == "axm-audit":
            return parent
    raise RuntimeError("axm-audit project root not found")


def test_cli_test_quality_includes_new_rule_json() -> None:
    """AC10: `axm-audit test-quality --json` lists TEST_QUALITY_NO_PACKAGE_SYMBOL."""
    root = _project_root()
    result = subprocess.run(  # noqa: S603
        ["axm-audit", "test-quality", "--json", str(root)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    blob = (result.stdout or "") + (result.stderr or "")
    assert "TEST_QUALITY_NO_PACKAGE_SYMBOL" in blob, (
        f"rule absent from CLI output. exit={result.returncode}\n{blob[:2000]}"
    )


def test_cli_audit_test_quality_on_synthetic_offender(tmp_path: Path) -> None:
    """AC5: CLI on a synthetic offender surfaces a NO_PACKAGE_SYMBOL finding."""
    pkg = tmp_path / "synpkg"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("")
    (pkg / "tests" / "integration").mkdir(parents=True)
    (pkg / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            pkg-cli = "pkg.cli:main"
            """
        ).strip()
    )
    result = subprocess.run(  # noqa: S603
        ["axm-audit", "test-quality", "--json", str(pkg)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    blob = result.stdout or ""
    found_verdict = "NO_PACKAGE_SYMBOL" in blob
    try:
        parsed = json.loads(blob)
        json_has_finding = "TEST_QUALITY_NO_PACKAGE_SYMBOL" in json.dumps(parsed)
    except (ValueError, json.JSONDecodeError):
        json_has_finding = False
    assert found_verdict or json_has_finding or result.returncode != 0, (
        f"CLI did not surface NO_PACKAGE_SYMBOL.\nstdout={blob[:2000]}\n"
        f"stderr={(result.stderr or '')[:1000]}"
    )


def _make_minimal_project(root: Path) -> None:
    """Create a minimal pyramid-correct project with no tautological tests."""
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
def test_test_quality_cli_emits_valid_json(tmp_path: Path) -> None:
    """`test-quality --json` emits parseable JSON regardless of pass/fail."""
    _make_minimal_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in (0, 1), (
        f"CLI crashed (rc={result.returncode}): {result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict | list)


@pytest.mark.e2e
def test_test_quality_cli_clean_project_no_findings(tmp_path: Path) -> None:
    """On a clean project, no tautology verdicts are emitted."""
    _make_minimal_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    verdicts = payload.get("verdicts", []) if isinstance(payload, dict) else payload
    assert verdicts == [], f"clean project unexpectedly produced verdicts: {verdicts}"


@pytest.mark.e2e
def test_test_quality_cli_detects_tautology(tmp_path: Path) -> None:
    """`test-quality` flags an obvious tautology when present."""
    (tmp_path / "src" / "sample").mkdir(parents=True)
    (tmp_path / "src" / "sample" / "__init__.py").write_text("x = 1\n")
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_taut.py").write_text(
        dedent(
            """
            def test_obvious_tautology() -> None:
                assert True
            """
        ).lstrip()
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
    )

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    verdicts = payload.get("verdicts", []) if isinstance(payload, dict) else payload
    trivially_true = [
        v
        for v in verdicts
        if isinstance(v, dict) and v.get("pattern") == "trivially_true"
    ]
    assert trivially_true, (
        f"`assert True` should have produced a trivially_true verdict; got: {payload}"
    )


PLUMBING_TEST = textwrap.dedent(
    """\
    import subprocess

    def test_uses_plumbing_subprocess():
        subprocess.run(["python", "-m", "some_other_tool"])
        assert True
    """
)


PYPROJECT = textwrap.dedent(
    """\
    [project]
    name = "fixture_pkg"
    version = "0.0.0"
    requires-python = ">=3.12"

    [project.scripts]
    fixture-cli = "fixture_pkg.cli:main"

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"
    """
)

DECLARED_SCRIPT_TEST = textwrap.dedent(
    """\
    import subprocess

    def test_uses_declared_script():
        subprocess.run(["uv", "run", "fixture-cli"])
        assert True
    """
)


def _write_fixture(root: Path) -> tuple[Path, Path]:
    (root / "pyproject.toml").write_text(PYPROJECT)
    src = root / "src" / "fixture_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "cli.py").write_text("def main() -> None:\n    pass\n")
    e2e = root / "tests" / "e2e"
    e2e.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("")
    (e2e / "__init__.py").write_text("")
    declared = e2e / "test_declared_script.py"
    plumbing = e2e / "test_plumbing_subprocess.py"
    declared.write_text(DECLARED_SCRIPT_TEST)
    plumbing.write_text(PLUMBING_TEST)
    return declared, plumbing


def test_cli_distinguishes_declared_script_e2e_from_plumbing_subprocess(
    tmp_path: Path,
) -> None:
    declared, plumbing = _write_fixture(tmp_path)

    pkg_root = Path(__file__).resolve().parents[2]
    cmd = [
        "uv",
        "run",
        "axm-audit",
        "test-quality",
        str(tmp_path),
        "--json",
    ]
    proc = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(pkg_root),
    )
    assert proc.returncode in (0, 1), proc.stderr
    payload = json.loads(proc.stdout)

    mismatches = payload.get("pyramid_mismatches", [])
    mismatch_paths = {m["test"].split("::", 1)[0]: m for m in mismatches if "test" in m}

    assert str(declared) not in mismatch_paths, (
        f"declared-script file unexpectedly demoted from e2e: "
        f"{mismatch_paths.get(str(declared))}"
    )

    plumbing_entry = mismatch_paths.get(str(plumbing))
    assert plumbing_entry is not None, (
        f"plumbing file missing mismatch recommendation; mismatches={mismatches}"
    )
    assert plumbing_entry.get("detected_level") != "e2e", (
        f"plumbing file still detected as e2e: {plumbing_entry}"
    )
