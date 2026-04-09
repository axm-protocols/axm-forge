"""Tests for namespace-module heuristic in dead code detection.

Public functions in modules imported as namespace objects (e.g. `import pkg.mod`
or `from pkg import mod`) should not be flagged as dead, because they may be
called via dynamic attribute access (`mod.func()`).
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


# ─── Unit: namespace module — public functions exempt ────────────────────────


class TestNamespaceModulePublicExempt:
    """Public functions in namespace-imported modules should not be flagged."""

    def test_public_fn_in_namespace_module_not_dead(self, tmp_path: Path) -> None:
        """Module B imported as object by A; B.func() has no direct callers.

        Not dead because B is a namespace module.
        """
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
        # Public functions in a namespace-imported module → exempt
        assert "compute" not in dead_names
        assert "transform" not in dead_names


# ─── Unit: namespace module — private functions still dead ───────────────────


class TestNamespaceModulePrivateStillDead:
    """Private functions in namespace-imported modules should still be flagged."""

    def test_private_fn_in_namespace_module_still_dead(self, tmp_path: Path) -> None:
        """Module B imported as object; B._helper() has no callers → still dead."""
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


# ─── Unit: non-namespace module — public functions still dead ────────────────


class TestNonNamespaceModulePublicStillDead:
    """Public functions in modules NOT imported as namespace objects are still dead."""

    def test_public_fn_not_in_namespace_module_still_dead(self, tmp_path: Path) -> None:
        """Module B not imported as object anywhere; B.orphan() → dead."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "utils.py": ("def orphan():\n    return 1\n"),
                "main.py": (
                    "from mypkg.utils import orphan\n\n"
                    "# imported symbol directly, not the module\n"
                    "# but orphan has no callers in this file\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        dead = find_dead_code(pkg)
        dead_names = {d.name for d in dead}
        assert "orphan" in dead_names


# ─── Edge: module with __all__ and namespace import ──────────────────────────


class TestNamespaceModuleWithAll:
    """Module with __all__ imported as namespace — both mechanisms exempt."""

    def test_all_plus_namespace(self, tmp_path: Path) -> None:
        """Module has __all__ = ['func'] and is imported as namespace.

        func exempt via __all__ (existing); other public funcs exempt via
        namespace heuristic.
        """
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
        # func exempt via __all__, other_public exempt via namespace heuristic
        assert "func" not in dead_names
        assert "other_public" not in dead_names
        # _private still dead (private + no callers)
        assert "_private" in dead_names


# ─── Edge: module imported both ways ─────────────────────────────────────────


class TestNamespaceModuleImportedBothWays:
    """Module imported both as namespace and with from-import."""

    def test_imported_both_ways(self, tmp_path: Path) -> None:
        """from B import x AND import B → treated as namespace module."""
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
        # Both public funcs should be safe
        assert "compute" not in dead_names
        assert "extra" not in dead_names


# ─── Edge: all public functions already have callers ─────────────────────────


class TestNamespaceModuleAllFunctionsHaveCallers:
    """Namespace module where all public functions already have direct callers."""

    def test_all_public_fns_have_callers(self, tmp_path: Path) -> None:
        """All funcs called directly — namespace heuristic is a no-op."""
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
        # Already have callers — no change needed
        assert "compute" not in dead_names
        assert "transform" not in dead_names
