"""Integration: migration audit script lists name-only exempted tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.no_package_symbol_ok]

_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "audit_name_based_tautology_opt_outs.py"
)


def _make_test_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_script_lists_name_only_exemptions(tmp_path: Path) -> None:
    """AC5: script flags name-only matches, omits structural and unrelated tests."""
    src_dir = tmp_path / "src" / "mypkg"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("")
    (src_dir / "protocols.py").write_text(
        "from typing import Protocol\n\n\n"
        "class MyProtocol(Protocol):\n"
        "    def do(self) -> None: ...\n"
    )

    tests_dir = tmp_path / "tests"

    _make_test_file(
        tests_dir / "test_name_only.py",
        (
            "def test_Foo_satisfies_AXMTool():\n"
            "    x = object()\n"
            "    assert isinstance(x, object)\n"
        ),
    )
    _make_test_file(
        tests_dir / "test_structural.py",
        (
            "def test_Foo_satisfies_MyProtocol():\n"
            "    x = object()\n"
            "    assert isinstance(x, MyProtocol)\n"
        ),
    )
    _make_test_file(
        tests_dir / "test_unrelated.py",
        "def test_simple():\n    assert 1 == 1\n",
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = result.stdout

    assert "test_Foo_satisfies_AXMTool" in stdout
    assert "test_Foo_satisfies_MyProtocol" not in stdout
    assert "test_simple" not in stdout
