from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

__all__: list[str] = []


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

PLUMBING_TEST = textwrap.dedent(
    """\
    import subprocess

    def test_uses_plumbing_subprocess():
        subprocess.run(["python", "-m", "some_other_tool"])
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
