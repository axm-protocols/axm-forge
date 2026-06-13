"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

import pytest

from axm_init.checks.structure import check_py_typed


class TestCheckPyTyped:
    def test_pass(self, gold_project: Path) -> None:
        r = check_py_typed(gold_project)
        assert r.passed is True

    @pytest.mark.parametrize(
        ("files", "expected"),
        [
            pytest.param(["src/pkg/__init__.py"], False, id="flat_missing_py_typed"),
            pytest.param(
                ["src/pkg/__init__.py", "src/pkg/py.typed"],
                True,
                id="flat_with_py_typed",
            ),
            pytest.param(
                ["src/ns/pkg/__init__.py", "src/ns/pkg/py.typed"],
                True,
                id="namespace_with_py_typed",
            ),
            pytest.param(
                ["src/ns/pkg/__init__.py"], False, id="namespace_missing_py_typed"
            ),
            pytest.param(
                ["src/ns/pkg/__init__.py", "src/ns/py.typed"],
                False,
                id="py_typed_in_namespace_dir_not_package",
            ),
        ],
    )
    def test_py_typed_layouts(
        self, tmp_path: Path, files: list[str], expected: bool
    ) -> None:
        """check_py_typed passes only when py.typed sits in the real package dir."""
        for rel in files:
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        r = check_py_typed(tmp_path)
        assert r.passed is expected
