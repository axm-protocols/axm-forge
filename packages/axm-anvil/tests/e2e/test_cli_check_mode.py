from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _write_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )


def _setup_clean_fixture(tmp_path: Path) -> tuple[Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return a, b


def _setup_cycle_fixture(tmp_path: Path) -> tuple[Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text(
        "from mypkg.b import helper\n"
        "\n"
        "def Bar():\n"
        "    return 1\n"
        "\n"
        "def uses_helper():\n"
        "    return helper()\n"
        "\n"
        "def Foo():\n"
        "    return Bar()\n"
    )
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return a, b


def test_cli_check_mode_exits_nonzero_on_cycle(tmp_path: Path) -> None:
    a, b = _setup_cycle_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            "--from-file",
            str(a),
            "--to-file",
            str(b),
            "--symbols",
            "Foo",
            "--path",
            str(tmp_path),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Import cycle:" in (result.stderr + result.stdout)
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_cli_check_mode_exits_zero_on_clean(tmp_path: Path) -> None:
    a, b = _setup_clean_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            "--from-file",
            str(a),
            "--to-file",
            str(b),
            "--symbols",
            "Foo",
            "--path",
            str(tmp_path),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before
