"""Split from ``test_python_file_discovery.py``."""

from pathlib import Path

import pytest


class TestGetPythonFiles:
    """Tests for get_python_files()."""

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        """Should find .py files recursively, ignoring non-Python files."""
        from axm_audit.core.rules._helpers import get_python_files

        sub = tmp_path / "pkg" / "sub"
        sub.mkdir(parents=True)
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (sub / "mod.py").write_text("")
        (sub / "data.txt").write_text("")

        result = get_python_files(tmp_path)
        names = {p.name for p in result}
        assert "__init__.py" in names
        assert "mod.py" in names
        assert "data.txt" not in names

    @pytest.mark.parametrize(
        "subpath",
        [
            pytest.param("", id="empty_directory"),
            pytest.param("does_not_exist", id="nonexistent_directory"),
        ],
    )
    def test_returns_empty_list_for_no_python_files(
        self, tmp_path: Path, subpath: str
    ) -> None:
        """No-Python-files paths (empty/nonexistent dir) return []."""
        from axm_audit.core.rules._helpers import get_python_files

        target = tmp_path / subpath if subpath else tmp_path
        assert get_python_files(target) == []

    def test_nested_init_files(self, tmp_path: Path) -> None:
        """Should include __init__.py at all nesting levels."""
        from axm_audit.core.rules._helpers import get_python_files

        pkg = tmp_path / "a" / "b"
        pkg.mkdir(parents=True)
        (tmp_path / "a" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text("")

        result = get_python_files(tmp_path)
        names = [p.name for p in result]
        assert names.count("__init__.py") == 2
        assert "core.py" in names
