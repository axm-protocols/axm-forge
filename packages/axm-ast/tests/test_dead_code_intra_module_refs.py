"""Tests for intra-module class reference detection in dead code analysis.

Verifies that classes referenced within their own module via attribute
access (ClassName.ATTR), method calls (ClassName.method()), type
annotations, or alias assignments are NOT falsely flagged as dead code.
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


class TestIntraModuleClassRefs:
    """Classes referenced within their own module must not be flagged dead."""

    def test_class_with_intra_module_attr_access_not_dead(self, tmp_path: Path) -> None:
        """_Sections.FOO attribute access → _Sections not dead."""
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
        """Registry.get() method call → Registry not dead."""
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
        """Class with no references anywhere → still flagged as dead."""
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


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestIntraModuleClassEdgeCases:
    """Edge cases for intra-module class reference detection."""

    def test_class_in_type_annotation_not_dead(self, tmp_path: Path) -> None:
        """def foo(x: MyClass) in same module → MyClass not dead."""
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
        """Class name in docstring/string only → still flagged as dead."""
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
        """S = _Sections; S.FOO → _Sections not dead (assignment detected)."""
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
