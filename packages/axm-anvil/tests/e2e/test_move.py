from __future__ import annotations

import subprocess
import sys
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


def test_cli_move_no_f811_with_overlapping_target_imports(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pkg.models import ClassInfo\n\n"
        "class Foo:\n"
        "    def run(self) -> ClassInfo:\n"
        "        return ClassInfo()\n"
    )
    tgt.write_text(
        "from __future__ import annotations\nfrom pkg.models.nodes import ClassInfo\n"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\nversion='0.0.0'\n")

    move_result = subprocess.run(
        ["uv", "run", "axm-anvil", "move", str(src), str(tgt), "Foo"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert move_result.returncode == 0, move_result.stderr
    # AC4: no ruff fallback warning surfaced through CLI output.
    assert "ruff check exited" not in move_result.stdout
    assert "ruff check exited" not in move_result.stderr

    # Independently verify the rewritten target file has no F811.
    ruff_result = subprocess.run(
        ["uv", "run", "ruff", "check", str(tgt)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert ruff_result.returncode == 0, ruff_result.stdout + ruff_result.stderr


def test_cli_move_reexport_flag(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg / "new.py").write_text("")
    caller_text = "from pkg.old import Foo\n\nFoo()\n"
    (pkg / "caller.py").write_text(caller_text)

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(pkg / "old.py"),
            str(pkg / "new.py"),
            "Foo",
            "--reexport",
            "--path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    source = (pkg / "old.py").read_text()
    assert "from pkg.new import Foo" in source
    assert "# re-export for backwards compat" in source
    assert (pkg / "caller.py").read_text() == caller_text


@pytest.mark.e2e
def test_cli_shared_helpers_error_mode(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n    return 1\n\n"
        "def moved_A():\n    return _shared()\n\n"
        "def remaining_B():\n    return _shared()\n"
    )
    target.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm_anvil",
            "move",
            str(source),
            str(target),
            "moved_A",
            "--shared-helpers",
            "error",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "shared" in combined
    assert "_shared" in result.stderr + result.stdout


@pytest.mark.e2e
def test_cli_shared_helpers_invalid_choice(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text("def foo():\n    return 1\n")
    target.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm_anvil",
            "move",
            str(source),
            str(target),
            "foo",
            "--shared-helpers",
            "extract",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_move_rewrites_caller(tmp_path: Path) -> None:
    """AC1, AC2: `axm-anvil move` rewrites the caller on disk via the CLI."""
    root = tmp_path
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    old = pkg / "old.py"
    old.write_text("def Foo():\n    return 1\n")
    new = pkg / "new.py"
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo\n\nFoo()\n")

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(old),
            str(new),
            "Foo",
            "--path",
            str(root),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "from pkg.new import Foo" in caller.read_text()
    assert "callers updated" in result.stdout.lower()


def test_cli_rename_option(tmp_path: Path) -> None:
    """AC4: the CLI move command exposes --rename forwarded to the core move."""
    root = tmp_path
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    old = pkg / "old.py"
    old.write_text("def OldName():\n    return 1\n")
    new = pkg / "new.py"
    new.write_text("")

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(old),
            str(new),
            "OldName",
            "--rename",
            '{"OldName":"NewName"}',
            "--path",
            str(root),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "NewName" in new.read_text()


SOURCE_WITH_METHOD = (
    "def real_toplevel() -> int:\n"
    "    return 42\n\n\n"
    "class TestBasicThing:\n"
    "    def test_basic(self) -> None:\n"
    "        assert True\n"
)


def test_move_method_name_exits_zero_with_warning(tmp_path: Path) -> None:
    """AC1: moving a method name via the CLI exits 0 with no traceback."""
    source = tmp_path / "source_mod.py"
    target = tmp_path / "target_mod.py"
    source.write_text(SOURCE_WITH_METHOD)
    target.write_text('"""Target."""\n')
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\nversion='0.0.0'\n")

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(source),
            str(target),
            "test_basic",
            "--path",
            str(tmp_path),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "Traceback" not in combined
    assert "SymbolNotFoundError" not in combined
    # The skipped name is surfaced to the user.
    assert "test_basic" in combined
