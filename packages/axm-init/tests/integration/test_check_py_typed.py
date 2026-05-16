"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

from axm_init.checks.structure import check_py_typed


class TestCheckPyTyped:
    def test_pass(self, gold_project: Path) -> None:
        r = check_py_typed(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        r = check_py_typed(tmp_path)
        assert r.passed is False

    def test_py_typed_flat_package(self, tmp_path: Path) -> None:
        """Flat package with py.typed -> PASS."""
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        (pkg / "py.typed").touch()
        r = check_py_typed(tmp_path)
        assert r.passed is True

    def test_py_typed_namespace_package(self, tmp_path: Path) -> None:
        """Namespace package: src/ns/pkg/__init__.py + src/ns/pkg/py.typed -> PASS."""
        pkg = tmp_path / "src" / "ns" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        (pkg / "py.typed").touch()
        r = check_py_typed(tmp_path)
        assert r.passed is True

    def test_py_typed_missing(self, tmp_path: Path) -> None:
        """Flat package without py.typed -> FAIL."""
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        r = check_py_typed(tmp_path)
        assert r.passed is False

    def test_py_typed_namespace_missing(self, tmp_path: Path) -> None:
        """Namespace package without py.typed -> FAIL."""
        pkg = tmp_path / "src" / "ns" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        r = check_py_typed(tmp_path)
        assert r.passed is False

    def test_py_typed_in_namespace_dir_not_package(self, tmp_path: Path) -> None:
        """py.typed in namespace dir (not real package) -> FAIL.

        src/ns/py.typed exists but __init__.py is in src/ns/pkg/.
        py.typed must be in the real package, not the namespace dir.
        """
        ns = tmp_path / "src" / "ns"
        pkg = ns / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        (ns / "py.typed").touch()  # Wrong location
        r = check_py_typed(tmp_path)
        assert r.passed is False
