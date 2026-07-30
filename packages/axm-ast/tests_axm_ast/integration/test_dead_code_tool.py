"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.dead_code import DeadCodeTool


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def test_dead_code_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:
    from axm_ast.tools.dead_code import DeadCodeTool

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.dead_code.find_dead_code",
        side_effect=RuntimeError("dead boom"),
    )
    result = DeadCodeTool().execute(path=str(pkg))
    assert result.success is False
    assert "dead boom" in (result.error or "")


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


class TestDeadCodeToolEdgeCases:
    """Edge cases for DeadCodeTool."""

    def test_not_a_directory(self, tool: DeadCodeTool, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("x = 1\n")
        result = tool.execute(path=str(f))
        assert result.success is False
        assert result.error is not None
        assert "Not a directory" in result.error
