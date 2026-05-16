"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

from axm_init.checks.structure import check_src_layout


class TestCheckSrcLayout:
    def test_pass(self, gold_project: Path) -> None:
        r = check_src_layout(gold_project)
        assert r.passed is True

    def test_fail_no_src(self, empty_project: Path) -> None:
        r = check_src_layout(empty_project)
        assert r.passed is False

    def test_fail_flat_layout(self, tmp_path: Path) -> None:
        pkg = tmp_path / "my_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        r = check_src_layout(tmp_path)
        assert r.passed is False

    def test_pass_flat_package(self, tmp_path: Path) -> None:
        """Standard flat package: src/pkg/__init__.py -> PASS, 1 package."""
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "pkg" / "__init__.py").touch()
        r = check_src_layout(tmp_path)
        assert r.passed is True
        assert "1 package" in r.message

    def test_pass_namespace_package(self, tmp_path: Path) -> None:
        """Namespace package: no src/ns/__init__.py -> PASS, 1 package."""
        (tmp_path / "src" / "ns" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "ns" / "pkg" / "__init__.py").touch()
        r = check_src_layout(tmp_path)
        assert r.passed is True
        assert "1 package" in r.message

    def test_fail_empty_src(self, tmp_path: Path) -> None:
        """src/ exists but empty -> FAIL."""
        (tmp_path / "src").mkdir()
        r = check_src_layout(tmp_path)
        assert r.passed is False
        assert "No Python package found" in r.message

    def test_pass_mixed_layout(self, tmp_path: Path) -> None:
        """Mixed: flat pkg + namespace-nested pkg -> PASS, 2 packages."""
        (tmp_path / "src" / "flat_pkg").mkdir(parents=True)
        (tmp_path / "src" / "flat_pkg" / "__init__.py").touch()
        (tmp_path / "src" / "ns" / "nested").mkdir(parents=True)
        (tmp_path / "src" / "ns" / "nested" / "__init__.py").touch()
        r = check_src_layout(tmp_path)
        assert r.passed is True
        assert "2 package" in r.message

    def test_pass_deep_namespace(self, tmp_path: Path) -> None:
        """Deep namespace: src/a/b/c/__init__.py -> PASS."""
        (tmp_path / "src" / "a" / "b" / "c").mkdir(parents=True)
        (tmp_path / "src" / "a" / "b" / "c" / "__init__.py").touch()
        r = check_src_layout(tmp_path)
        assert r.passed is True
