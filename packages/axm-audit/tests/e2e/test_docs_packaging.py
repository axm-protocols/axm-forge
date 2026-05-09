from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_built_wheel_contains_docs_test_quality_md(tmp_path: Path) -> None:
    result = subprocess.run(  # noqa: S603
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"uv build failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert wheels, f"no wheel produced in {tmp_path}"
    with zipfile.ZipFile(wheels[0]) as zf:
        names = zf.namelist()
    assert any(n.endswith("docs/test_quality.md") for n in names), (
        f"docs/test_quality.md not shipped in wheel; members: {names}"
    )
