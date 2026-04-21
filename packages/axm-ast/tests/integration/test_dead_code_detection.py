"""Integration tests for dead code detection through the filesystem.

Exercises ``analyze_package`` + ``find_dead_code`` end-to-end on temporary
packages written to disk, plus ``DeadCodeTool.execute`` for the MCP tool layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.dead_code import (
    find_dead_code,
)
from axm_ast.tools.dead_code import DeadCodeTool

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _init_git_repo(path: Path) -> None:
    """Initialise a minimal git repo so .gitignore is respected."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


def _dead_names(tmp_path: Path, files: dict[str, str]) -> set[str]:
    """Build package, run dead code analysis, return dead symbol names."""
    pkg_path = _make_pkg(tmp_path, files)
    pkg = analyze_package(pkg_path)
    dead = find_dead_code(pkg)
    return {d.name for d in dead}


# ═══════════════════════════════════════════════════════════════════════════
# Basic detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestBasicDetection:
    """Simple alive/dead detection scenarios."""

    def test_find_dead_simple(self, tmp_path: Path) -> None:
        """Package with 1 uncalled function -> returns it as dead."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def used():\n    pass\n\ndef unused():\n    pass\n",
                "main.py": "from .core import used\n\ndef run():\n    used()\n",
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "unused" in dead_names
        assert "used" not in dead_names

    def test_no_dead_code(self, tmp_path: Path) -> None:
        """All functions called -> greet not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def greet():\n    return 'hi'\n",
                "main.py": "from .core import greet\n\ndef run():\n    greet()\n",
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        assert not any(d.name == "greet" for d in dead)

    def test_sample_pkg(self, tmp_path: Path) -> None:
        """Realistic multi-file package -> known dead symbols detected."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": '__all__ = ["greet"]\n\nfrom .core import greet\n',
                "core.py": (
                    "def greet(name: str) -> str:\n"
                    "    return f'Hello, {name}'\n\n"
                    "def _helper():\n"
                    "    pass\n\n"
                    "def stale_function():\n"
                    "    pass\n"
                ),
                "utils.py": (
                    "def format_name(name: str) -> str:\n"
                    "    return name.strip()\n\n"
                    "def deprecated_fn():\n"
                    "    pass\n"
                ),
                "main.py": (
                    "from .core import greet\n"
                    "from .utils import format_name\n\n"
                    "def run():\n"
                    "    name = format_name('world')\n"
                    "    greet(name)\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "stale_function" in dead_names
        assert "deprecated_fn" in dead_names
        assert "_helper" in dead_names
        assert "greet" not in dead_names
        assert "format_name" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Exemptions
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestExemptions:
    """Symbols exempt from dead code flags."""

    def test_exempt_dunder(self, tmp_path: Path) -> None:
        """__repr__ with no callers -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": (
                    "class Foo:\n    def __repr__(self):\n        return 'Foo()'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Foo.__repr__" not in dead_names

    def test_exempt_test_function(self, tmp_path: Path) -> None:
        """test_foo() with no callers -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def test_foo():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "test_foo" not in dead_names

    def test_exempt_all_export(self, tmp_path: Path) -> None:
        """Function in __all__ -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "api.py": (
                    '__all__ = ["public_fn"]\n\n'
                    "def public_fn():\n"
                    "    pass\n\n"
                    "def private_fn():\n"
                    "    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "public_fn" not in dead_names
        assert "private_fn" in dead_names

    def test_exempt_decorated(self, tmp_path: Path) -> None:
        """@app.route function -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "routes.py": (
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n\n"
                    "@app.route('/')\n"
                    "def index():\n"
                    "    return 'hello'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "index" not in dead_names

    def test_exempt_property(self, tmp_path: Path) -> None:
        """@property method -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": (
                    "class Foo:\n    @property\n    def bar(self):\n        return 42\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Foo.bar" not in dead_names

    def test_exempt_abstract(self, tmp_path: Path) -> None:
        """@abstractmethod -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "base.py": (
                    "from abc import abstractmethod, ABC\n\n"
                    "class Base(ABC):\n"
                    "    @abstractmethod\n"
                    "    def process(self):\n"
                    "        pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Base.process" not in dead_names

    def test_exempt_protocol_method(self, tmp_path: Path) -> None:
        """Method on Protocol class -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "protocols.py": (
                    "from typing import Protocol\n\n"
                    "class Processor(Protocol):\n"
                    "    def process(self, data: str) -> str:\n"
                    "        ...\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Processor.process" not in dead_names

    def test_existing_exemptions_unchanged(self, tmp_path: Path) -> None:
        """Regression guard: all exemption categories still work."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": (
                    "from typing import Protocol\n\n"
                    '__all__ = ["exported_fn"]\n\n'
                    "def exported_fn():\n    pass\n\n"
                    "class Foo:\n"
                    "    def __repr__(self):\n"
                    "        return 'Foo()'\n\n"
                    "class Handler(Protocol):\n"
                    "    def handle(self, data: str) -> str:\n"
                    "        ...\n\n"
                    "def test_something():\n    pass\n\n"
                    "def truly_unused():\n    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "exported_fn" not in dead_names
        assert "Foo.__repr__" not in dead_names
        assert "Handler.handle" not in dead_names
        assert "test_something" not in dead_names
        assert "truly_unused" in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Mixin / base class detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestMixinBaseClass:
    """Mixin classes used as base classes should not be flagged as dead."""

    def test_mixin_base_class_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mixins.py": (
                    "class _Mixin:\n    def helper(self):\n        return 42\n"
                ),
                "models.py": (
                    "from .mixins import _Mixin\n\nclass Foo(_Mixin):\n    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_Mixin" not in dead_names

    def test_unused_mixin_still_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mixins.py": (
                    "class _Mixin:\n    def helper(self):\n        return 42\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_Mixin" in dead_names

    def test_multi_inheritance_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mixins.py": (
                    "class _MixinA:\n"
                    "    def help_a(self):\n"
                    "        return 'a'\n\n"
                    "class _MixinB:\n"
                    "    def help_b(self):\n"
                    "        return 'b'\n"
                ),
                "models.py": (
                    "from abc import ABC\n"
                    "from .mixins import _MixinA, _MixinB\n\n"
                    "class Foo(_MixinA, _MixinB, ABC):\n"
                    "    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_MixinA" not in dead_names
        assert "_MixinB" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Override detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestOverrides:
    """Method override detection through analyze_package."""

    def test_override_non_dead(self, tmp_path: Path) -> None:
        """Override of called base method -> not flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "base.py": (
                    "class Base:\n    def process(self):\n        return 'base'\n"
                ),
                "child.py": (
                    "from .base import Base\n\n"
                    "class Child(Base):\n"
                    "    def process(self):\n"
                    "        return 'child'\n"
                ),
                "main.py": (
                    "from .base import Base\n\n"
                    "def run():\n"
                    "    b = Base()\n"
                    "    b.process()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Child.process" not in dead_names

    def test_override_dead_base(self, tmp_path: Path) -> None:
        """Override of dead base method -> flagged."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "base.py": (
                    "class Base:\n    def process(self):\n        return 'base'\n"
                ),
                "child.py": (
                    "from .base import Base\n\n"
                    "class Child(Base):\n"
                    "    def process(self):\n"
                    "        return 'child'\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Child.process" in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestEdgeCases:
    """Edge cases for dead code detection."""

    def test_empty_package(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, {"__init__.py": ""})
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        assert dead == []

    def test_all_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "waste.py": (
                    "def a():\n    pass\n\ndef b():\n    pass\n\ndef c():\n    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert dead_names == {"a", "b", "c"}

    def test_all_exempt(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": '__all__ = ["handle"]\n',
                "core.py": ('__all__ = ["handle"]\n\ndef handle():\n    pass\n'),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        assert not any(d.name == "handle" for d in dead)

    def test_circular_calls(self, tmp_path: Path) -> None:
        """A calls B, B calls A — mutual callers, neither flagged (known limitation)."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "circular.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "func_a" not in dead_names
        assert "func_b" not in dead_names

    def test_dead_code_excludes_gitignored(self, tmp_path: Path) -> None:
        """Symbols in gitignored directories are not reported as dead."""
        pkg = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def used():\n    pass\n",
                "main.py": "from .core import used\n\ndef run():\n    used()\n",
                "archive/old.py": "def abandoned():\n    pass\n",
            },
        )
        _init_git_repo(pkg)
        (pkg / ".gitignore").write_text("archive/\n")

        result = analyze_package(pkg)
        dead = find_dead_code(result)
        dead_names = {d.name for d in dead}
        assert "abandoned" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Dict / list / kwarg dispatch detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestDictDispatch:
    """Functions referenced in data structures should not be flagged."""

    def test_dict_dispatch_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "handlers.py": (
                    "def handle_a():\n"
                    "    return 'a'\n\n"
                    "def handle_b():\n"
                    "    return 'b'\n\n"
                    "HANDLERS = {\n"
                    '    "a": handle_a,\n'
                    '    "b": handle_b,\n'
                    "}\n"
                ),
                "main.py": (
                    "from .handlers import HANDLERS\n\n"
                    "def dispatch(key: str):\n"
                    "    handler = HANDLERS.get(key)\n"
                    "    if handler:\n"
                    "        handler()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "handle_a" not in dead_names
        assert "handle_b" not in dead_names

    def test_list_dispatch_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "pipeline.py": (
                    "def step_one():\n"
                    "    pass\n\n"
                    "def step_two():\n"
                    "    pass\n\n"
                    "STEPS = [step_one, step_two]\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "step_one" not in dead_names
        assert "step_two" not in dead_names

    def test_unreferenced_still_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "handlers.py": (
                    "def handle_a():\n"
                    "    return 'a'\n\n"
                    "def orphan():\n"
                    "    return 'orphan'\n\n"
                    "HANDLERS = {\n"
                    '    "a": handle_a,\n'
                    "}\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "handle_a" not in dead_names
        assert "orphan" in dead_names

    def test_kwarg_reference_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "helpers.py": (
                    "def _collate_flight_samples(batch):\n    return batch\n"
                ),
                "main.py": (
                    "from .helpers import _collate_flight_samples\n\n"
                    "class DataLoader:\n"
                    "    def __init__(self, collate_fn=None):\n"
                    "        self.collate_fn = collate_fn\n\n"
                    "def run():\n"
                    "    loader = DataLoader(collate_fn=_collate_flight_samples)\n"
                    "    return loader\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_collate_flight_samples" not in dead_names

    def test_default_param_reference(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    "def _default_sort(items):\n"
                    "    return sorted(items)\n\n"
                    "def process(data, sort_fn=_default_sort):\n"
                    "    return sort_fn(data)\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_default_sort" not in dead_names

    def test_data_structure_refs_unchanged(self, tmp_path: Path) -> None:
        """Regression guard: dict dispatch still works."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "dispatch.py": (
                    "def func_a():\n"
                    "    return 'a'\n\n"
                    "def func_b():\n"
                    "    return 'b'\n\n"
                    "dispatch = {'a': func_a, 'b': func_b}\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "func_a" not in dead_names
        assert "func_b" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Entry-point exemption
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestEntryPointExemption:
    """Symbols registered as entry points should not be flagged."""

    def test_entry_point_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "tools.py": (
                    "class MyTool:\n    def execute(self):\n        return 'result'\n"
                ),
            },
        )
        pyproject = pkg_path / "pyproject.toml"
        pyproject.write_text(
            '[project.entry-points."my.tools"]\nmy_tool = "mypkg.tools:MyTool"\n'
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "MyTool" not in dead_names
        assert "MyTool.execute" not in dead_names

    def test_no_pyproject_graceful(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def orphan():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "orphan" in dead_names

    def test_entry_point_missing_symbol(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def real_func():\n    pass\n",
            },
        )
        pyproject = pkg_path / "pyproject.toml"
        pyproject.write_text(
            '[project.entry-points."my.tools"]\nghost = "mypkg.core:GhostClass"\n'
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "real_func" in dead_names

    def test_scripts_entry_point_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "cli.py": "def main():\n    print('hello')\n",
            },
        )
        pyproject = pkg_path / "pyproject.toml"
        pyproject.write_text('[project.scripts]\nmy-cli = "mypkg.cli:main"\n')
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "main" not in dead_names

    def test_scripts_entry_point_src_layout(self, tmp_path: Path) -> None:
        """[project.scripts] found via parent traversal in src layout."""
        project_root = tmp_path / "myproject"
        project_root.mkdir()
        src = project_root / "src" / "mypkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "cli.py").write_text("def main():\n    print('hello')\n")
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text('[project.scripts]\nmy-cli = "mypkg.cli:main"\n')
        pkg = analyze_package(src)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "main" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Test directory exclusion / inclusion
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestIncludeTests:
    """Test directory exclusion/inclusion control."""

    def test_exclude_tests_default(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        fixtures = pkg_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "__init__.py").write_text("")
        (fixtures / "sample.py").write_text("def fixture_func():\n    pass\n")
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "fixture_func" not in dead_names

    def test_include_tests_flag(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        fixtures = pkg_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "__init__.py").write_text("")
        (fixtures / "sample.py").write_text("def fixture_func():\n    pass\n")
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg, include_tests=True)
        dead_names = {d.name for d in dead}
        assert "fixture_func" in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Test caller scanning
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestTestCallerScanning:
    """Symbols used only in tests/ should NOT be flagged as dead."""

    def test_symbol_used_in_tests_not_dead(self, tmp_path: Path) -> None:
        src_pkg = tmp_path / "src" / "mypkg"
        src_pkg.mkdir(parents=True)
        (src_pkg / "__init__.py").write_text("")
        (src_pkg / "core.py").write_text(
            "def _reset_state():\n    pass\n\ndef public_fn():\n    pass\n"
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_core.py").write_text(
            "from mypkg.core import _reset_state\n\n"
            "def test_something():\n    _reset_state()\n"
        )
        pkg = analyze_package(src_pkg)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_reset_state" not in dead_names

    def test_symbol_unused_everywhere_still_dead(self, tmp_path: Path) -> None:
        src_pkg = tmp_path / "src" / "mypkg"
        src_pkg.mkdir(parents=True)
        (src_pkg / "__init__.py").write_text("")
        (src_pkg / "core.py").write_text("def truly_dead():\n    pass\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_core.py").write_text(
            "def test_something():\n    assert True\n"
        )
        pkg = analyze_package(src_pkg)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "truly_dead" in dead_names

    def test_no_tests_dir_graceful(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def orphan():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "orphan" in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Lazy import detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestLazyImports:
    """Symbols imported inside function bodies should not be flagged."""

    def test_lazy_import_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": "class StampType:\n    pass\n",
                "executor.py": (
                    "def run():\n"
                    "    from .models import StampType\n"
                    "    return StampType()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "StampType" not in dead_names

    def test_top_level_import_still_works(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": "class MyModel:\n    pass\n",
                "service.py": (
                    "from .models import MyModel\n\n"
                    "def create():\n    return MyModel()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "MyModel" not in dead_names

    def test_lazy_import_in_if_block(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "models.py": "class Config:\n    pass\n",
                "service.py": (
                    "from typing import TYPE_CHECKING\n\n"
                    "if TYPE_CHECKING:\n"
                    "    from .models import Config\n\n"
                    "def get_config() -> 'Config':\n"
                    "    from .models import Config\n"
                    "    return Config()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "Config" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Intra-module class references
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestIntraModuleClassRefs:
    """Classes referenced within their own module must not be flagged dead."""

    def test_class_with_intra_module_attr_access_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class _Sections:\n"
                    "    WING_AREA = 'wing_area'\n"
                    "    FUSELAGE = 'fuselage'\n\n"
                    "def get_section():\n"
                    "    return _Sections.WING_AREA\n"
                ),
            },
        )
        assert "_Sections" not in dead

    def test_class_with_intra_module_method_call_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Registry:\n"
                    "    _items: dict = {}\n\n"
                    "    @classmethod\n"
                    "    def get(cls, key: str) -> object:\n"
                    "        return cls._items.get(key)\n\n"
                    "def lookup(key: str) -> object:\n"
                    "    return Registry.get(key)\n"
                ),
            },
        )
        assert "Registry" not in dead

    def test_truly_dead_class_still_detected(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Orphan:\n    value = 42\n\ndef do_work():\n    return 99\n"
                ),
            },
        )
        assert "Orphan" in dead

    def test_class_in_type_annotation_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class MyClass:\n"
                    "    pass\n\n"
                    "def process(x: MyClass) -> None:\n"
                    "    pass\n"
                ),
            },
        )
        assert "MyClass" not in dead

    def test_class_name_only_in_string_still_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class _Sections:\n"
                    "    WING_AREA = 'wing_area'\n\n"
                    "def info():\n"
                    '    """Uses _Sections internally."""\n'
                    "    return '_Sections is referenced here'\n"
                ),
            },
        )
        assert "_Sections" in dead

    def test_class_used_via_alias_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class _Sections:\n"
                    "    FOO = 'foo'\n\n"
                    "S = _Sections\n\n"
                    "def get_foo():\n"
                    "    return S.FOO\n"
                ),
            },
        )
        assert "_Sections" not in dead


# ═══════════════════════════════════════════════════════════════════════════
# Namespace module heuristic
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestNamespaceModules:
    """Namespace-imported modules: public functions exempt, private still dead."""

    def test_public_fn_in_namespace_module_not_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    "def compute():\n    return 42\n\ndef transform():\n    return 99\n"
                ),
                "main.py": (
                    "from mypkg import utils\n\n"
                    "def run():\n"
                    "    return utils.compute()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "compute" not in dead_names
        assert "transform" not in dead_names

    def test_private_fn_in_namespace_module_still_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    "def compute():\n    return 42\n\ndef _helper():\n    return 0\n"
                ),
                "main.py": (
                    "from mypkg import utils\n\n"
                    "def run():\n"
                    "    return utils.compute()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_helper" in dead_names

    def test_public_fn_not_in_namespace_module_still_dead(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": ("def orphan():\n    return 1\n"),
                "main.py": (
                    "from mypkg.utils import orphan\n\n"
                    "# imported symbol directly, not the module\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "orphan" in dead_names

    def test_all_plus_namespace(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    '__all__ = ["func"]\n\n'
                    "def func():\n"
                    "    return 1\n\n"
                    "def other_public():\n"
                    "    return 2\n\n"
                    "def _private():\n"
                    "    return 3\n"
                ),
                "main.py": (
                    "from mypkg import utils\n\ndef run():\n    return utils.func()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "func" not in dead_names
        assert "other_public" not in dead_names
        assert "_private" in dead_names

    def test_imported_both_ways(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    "def compute():\n    return 42\n\ndef extra():\n    return 99\n"
                ),
                "main.py": (
                    "from mypkg.utils import compute\n"
                    "from mypkg import utils\n\n"
                    "def run():\n"
                    "    compute()\n"
                    "    utils.extra()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "compute" not in dead_names
        assert "extra" not in dead_names

    def test_all_public_fns_have_callers(self, tmp_path: Path) -> None:
        """Namespace heuristic is a no-op when all funcs already have callers."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": (
                    "def compute():\n    return 42\n\ndef transform():\n    return 99\n"
                ),
                "main.py": (
                    "from mypkg import utils\n"
                    "from mypkg.utils import compute, transform\n\n"
                    "def run():\n"
                    "    compute()\n"
                    "    transform()\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "compute" not in dead_names
        assert "transform" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# Attribute reference detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestAttributeRefs:
    """Attribute nodes (self.method) should be recognized as references."""

    def test_kwarg_attribute_ref_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Processor:\n"
                    "    def _method(self):\n"
                    "        return 42\n\n"
                    "    def run(self):\n"
                    "        return Dispatcher(callback=self._method)\n\n\n"
                    "class Dispatcher:\n"
                    "    def __init__(self, callback=None):\n"
                    "        self.callback = callback\n"
                ),
            },
        )
        assert "_method" not in dead

    def test_dict_attribute_ref_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Router:\n"
                    "    def _handle(self):\n"
                    "        return 'ok'\n\n"
                    "    def routes(self):\n"
                    '        return {"action": self._handle}\n'
                ),
            },
        )
        assert "_handle" not in dead

    def test_list_attribute_ref_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Pipeline:\n"
                    "    def _step(self):\n"
                    "        pass\n\n"
                    "    def steps(self):\n"
                    "        return [self._step]\n"
                ),
            },
        )
        assert "_step" not in dead

    def test_assignment_attribute_ref_not_dead(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Worker:\n"
                    "    def _process(self):\n"
                    "        pass\n\n"
                    "    def run(self):\n"
                    "        f = self._process\n"
                    "        return f()\n"
                ),
            },
        )
        assert "_process" not in dead

    def test_chained_attribute_extracts_last(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Inner:\n"
                    "    def method(self):\n"
                    "        return 1\n\n"
                    "class Outer:\n"
                    "    def __init__(self):\n"
                    "        self.inner = Inner()\n\n"
                    "    def run(self):\n"
                    "        return Executor(callback=self.inner.method)\n\n\n"
                    "class Executor:\n"
                    "    def __init__(self, callback=None):\n"
                    "        self.callback = callback\n"
                ),
            },
        )
        assert "method" not in dead

    def test_bare_identifier_still_works(self, tmp_path: Path) -> None:
        """Regression guard: Foo(callback=my_func) still detected."""
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def my_func():\n"
                    "    return 1\n\n"
                    "class Builder:\n"
                    "    def __init__(self, callback=None):\n"
                    "        self.callback = callback\n\n"
                    "def run():\n"
                    "    return Builder(callback=my_func)\n"
                ),
            },
        )
        assert "my_func" not in dead

    def test_attribute_in_tuple(self, tmp_path: Path) -> None:
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Multi:\n"
                    "    def _step_a(self):\n"
                    "        pass\n\n"
                    "    def _step_b(self):\n"
                    "        pass\n\n"
                    "    def steps(self):\n"
                    "        return (self._step_a, self._step_b)\n"
                ),
            },
        )
        assert "_step_a" not in dead
        assert "_step_b" not in dead

    def test_attribute_call_not_false_negative(self, tmp_path: Path) -> None:
        """self._make() is a call, not a reference — call-graph catches it."""
        dead = _dead_names(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "class Maker:\n"
                    "    def _make(self):\n"
                    "        return lambda: None\n\n"
                    "    def run(self):\n"
                    "        return Config(handler=self._make())\n\n\n"
                    "class Config:\n"
                    "    def __init__(self, handler=None):\n"
                    "        self.handler = handler\n"
                ),
            },
        )
        assert "_make" not in dead

    def test_executor_advance_hooks_not_dead(self) -> None:
        """find_dead_code on axm-engine must not flag _advance_hooks."""
        engine_path = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "axm-nexus"
            / "packages"
            / "axm-engine"
        )
        if not engine_path.exists():
            pytest.skip("axm-engine not available")
        pkg = analyze_package(engine_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_advance_hooks" not in dead_names


# ═══════════════════════════════════════════════════════════════════════════
# DeadCodeTool (MCP tool wrapper)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def tool() -> DeadCodeTool:
    """Provide a fresh DeadCodeTool instance."""
    return DeadCodeTool()


@pytest.fixture()
def dead_pkg(tmp_path: Path) -> Path:
    """Create a package with intentional dead code."""
    pkg = tmp_path / "deadcodedemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Dead code demo."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        "def used_function() -> str:\n"
        '    """Used."""\n'
        '    return "ok"\n\n\n'
        "def unused_function() -> str:\n"
        '    """Not called anywhere."""\n'
        '    return "dead"\n\n\n'
        "class UsedClass:\n"
        '    """Used class."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run method."""\n'
        "        used_function()\n"
    )
    return pkg


@pytest.mark.integration
class TestDeadCodeToolExecute:
    """Tests for DeadCodeTool.execute."""

    def test_returns_result(self, tool: DeadCodeTool, dead_pkg: Path) -> None:
        result = tool.execute(path=str(dead_pkg))
        assert result.success is True
        assert "dead_symbols" in result.data
        assert "total" in result.data

    def test_detects_unused_function(self, tool: DeadCodeTool, dead_pkg: Path) -> None:
        result = tool.execute(path=str(dead_pkg))
        assert result.success is True
        names = [s["name"] for s in result.data["dead_symbols"]]
        assert "unused_function" in names

    def test_clean_package(self, tool: DeadCodeTool, tmp_path: Path) -> None:
        """Package with no dead code -> empty list."""
        pkg = tmp_path / "clean"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Clean."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\n\n'
            '__all__ = ["greet"]\n\n\n'
            "def greet() -> str:\n"
            '    """Say hi."""\n'
            '    return "hi"\n'
        )
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert result.data["total"] == 0


@pytest.mark.integration
class TestDeadCodeToolEdgeCases:
    """Edge cases for DeadCodeTool."""

    def test_bad_path(self, tool: DeadCodeTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False

    def test_not_a_directory(self, tool: DeadCodeTool, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("x = 1\n")
        result = tool.execute(path=str(f))
        assert result.success is False
        assert result.error is not None
        assert "Not a directory" in result.error
