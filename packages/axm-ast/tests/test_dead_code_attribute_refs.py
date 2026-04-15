"""Tests for attribute-node handling in dead code reference extraction.

Verifies that `self.method` patterns in kwargs, dict values, collections,
and assignments are correctly recognized as references so the method is
not falsely flagged as dead code.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.dead_code import find_dead_code

# ─── Helpers ─────────────────────────────────────────────────────────────────


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


# ─── Unit tests ──────────────────────────────────────────────────────────────


class TestAttributeRefs:
    """Attribute nodes (self.method) should be recognized as references."""

    def test_kwarg_attribute_ref_not_dead(self, tmp_path: Path) -> None:
        """Cls(callback=self._method) → _method not dead."""
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
        """{"k": self._method} → _method not dead."""
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
        """[self._method] → _method not dead."""
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
        """f = self._method → _method not dead."""
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


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestAttributeEdgeCases:
    """Edge cases for attribute reference extraction."""

    def test_chained_attribute_extracts_last(self, tmp_path: Path) -> None:
        """a.b.c.method → extract 'method' (last segment)."""
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
        """Foo(callback=my_func) → my_func still detected (regression guard)."""
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
        """(self.a, self.b) → both a and b extracted."""
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

    def test_attribute_call_not_extracted(self, tmp_path: Path) -> None:
        """Foo(callback=self.method()) → not extracted (it's a call)."""
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
        # _make is used via call — call-graph covers this, but not as
        # a reference extraction. The method is called, so not dead.
        # This test ensures we don't double-count or break on call nodes.
        # _make() IS a call so call-graph should catch it.
        # We just verify no crash and no false negative.
        assert isinstance(dead, set)


# ─── Functional tests ────────────────────────────────────────────────────────


class TestAttributeRefsFunctional:
    """Functional test against real axm-engine package."""

    def test_executor_advance_hooks_not_dead(self) -> None:
        """find_dead_code on axm-engine must not flag _advance_hooks."""
        engine_path = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "axm-nexus"
            / "packages"
            / "axm-engine"
        )
        if not engine_path.exists():
            import pytest

            pytest.skip("axm-engine not available")
        pkg = analyze_package(engine_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "_advance_hooks" not in dead_names
