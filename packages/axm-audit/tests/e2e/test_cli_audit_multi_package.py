from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

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
