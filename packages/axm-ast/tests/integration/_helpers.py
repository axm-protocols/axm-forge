"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

_ANALYZER = "axm_ast.core.analyzer"


def _assert_tool_result(result: Any) -> None:
    """Assert result is a valid ToolResult."""
    assert hasattr(result, "success")
    assert hasattr(result, "data")
    assert isinstance(result.data, dict)


def _make_func(name: str, kind: str = "function") -> SimpleNamespace:
    return SimpleNamespace(name=name, kind=kind)


def _make_import_heuristic_project(tmp_path: Path) -> Path:
    """Create a project with an untested symbol whose module is imported."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Mypkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models module."""\n'
        "class InternalCfg:\n"
        '    """Internal configuration dataclass."""\n'
        '    name: str = "default"\n'
    )
    (pkg / "cli.py").write_text(
        '"""CLI module."""\ndef main() -> None:\n    """Main."""\n    pass\n'
    )
    # Tests directory: imports the models *module* but does NOT mention "InternalCfg"
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_models.py").write_text(
        '"""Test models."""\n'
        "import mypkg.models\n"
        "\n"
        "def test_something() -> None:\n"
        '    """Test."""\n'
        "    assert True\n"
    )
    # A non-test file that imports the module (should be excluded)
    (tmp_path / "helper_script.py").write_text(
        '"""Not a test."""\nimport mypkg.models\n'
    )
    return pkg


def _make_mock_mod(path: Path) -> MagicMock:
    """Create a mock module with given path."""
    mod = MagicMock()
    mod.path = path
    return mod


def _make_mod(
    *,
    path: Path,
    name: str | None = None,
    functions: list[SimpleNamespace] | None = None,
    classes: list[SimpleNamespace] | None = None,
    variables: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        path=path,
        name=name,
        functions=functions or [],
        classes=classes or [],
        variables=variables or [],
    )


def _make_project_with_test_callers(tmp_path: Path) -> Path:
    """Create a project where a symbol is called from both prod and test code."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\ndef main() -> None:\n    """Main."""\n    helper(42)\n'
    )
    # Test callers — module names will start with "tests." or "test_"
    (pkg / "tests").mkdir()
    (pkg / "tests" / "__init__.py").write_text('"""Tests."""\n')
    (pkg / "tests" / "test_runner.py").write_text(
        '"""Test runner."""\n'
        "def test_helper() -> None:\n"
        '    """Test."""\n'
        "    helper(1)\n"
    )
    # Also a top-level test_ module
    (pkg / "test_smoke.py").write_text(
        '"""Smoke tests."""\ndef smoke() -> None:\n    """Smoke."""\n    helper(99)\n'
    )
    return pkg


def _make_project_with_test_callers__from_impact_test_filter(tmp_path: Path) -> Path:
    """Create a project where a symbol is called by both prod and test modules.

    Test files live **inside** the package so ``find_callers`` picks them up.

    Layout:
        pkg/
            __init__.py
            core.py        → def target_fn(x): ...
            engine.py      → calls target_fn (prod caller)
            test_a.py      → calls target_fn directly (direct test caller)
            tests/
                __init__.py
                test_b.py  → calls engine.run() (transitive only)
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\n'
        "def target_fn(x: int) -> int:\n"
        '    """Target function."""\n'
        "    return x + 1\n"
    )
    (pkg / "engine.py").write_text(
        '"""Engine."""\n'
        "def run() -> int:\n"
        '    """Run engine."""\n'
        "    return target_fn(42)\n"
    )
    # test_a: calls target_fn directly — top-level test module in package
    (pkg / "test_a.py").write_text(
        '"""Direct test."""\n'
        "def test_target_direct() -> None:\n"
        '    """Test."""\n'
        "    target_fn(1)\n"
    )
    # test_b: calls engine.run() only (transitive reference to target_fn)
    tests = pkg / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text('"""Tests."""\n')
    (tests / "test_b.py").write_text(
        '"""Transitive test."""\n'
        "def test_via_engine() -> None:\n"
        '    """Test."""\n'
        "    run()\n"
    )
    return pkg


def _write_module(root: Path, code: str, module: str = "pkg.mod") -> Path:
    parts = module.split(".")
    directory = root / "src" / Path(*parts[:-1])
    directory.mkdir(parents=True, exist_ok=True)
    py_file = directory / f"{parts[-1]}.py"
    py_file.write_text(code, encoding="utf-8")
    return py_file


def _write_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a minimal Python package under *tmp_path* and return its root."""
    pkg_dir = tmp_path / "pkg"
    src = pkg_dir / "src" / "mypkg"
    src.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "mypkg"
            version = "0.1.0"
            [tool.hatch.build.targets.wheel]
            packages = ["src/mypkg"]
        """),
    )
    for name, body in files.items():
        target = src / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body))
    return pkg_dir


def _write_pyproject(pkg_dir: Path, pkg_name: str) -> None:
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{pkg_name}"\nversion = "0.1.0"\n'
    )


def _write_src_module(pkg_dir: Path, pkg_name: str) -> None:
    """Create a source module with a public function and class."""
    src = pkg_dir / "src" / pkg_name
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text(
        "from __future__ import annotations\n\n"
        "def compute(x: int) -> int:\n"
        '    """Compute something."""\n'
        "    return x * 2\n\n"
        "class Engine:\n"
        '    """Main engine."""\n'
        "    def run(self) -> None:\n"
        "        pass\n"
    )


def _write_test_modules(pkg_dir: Path) -> None:
    """Create test modules with test functions and a test class."""
    tests = pkg_dir / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "__init__.py").write_text("")
    (tests / "test_core.py").write_text(
        "from __future__ import annotations\n\n"
        "def test_compute_doubles():\n"
        "    assert 2 * 2 == 4\n\n"
        "def test_compute_zero():\n"
        "    assert 0 * 2 == 0\n\n"
        "class TestEngine:\n"
        "    def test_run(self):\n"
        "        pass\n"
    )
    (tests / "conftest.py").write_text(
        "from __future__ import annotations\n\n"
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def sample_input():\n"
        "    return 42\n"
    )
