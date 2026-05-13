from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_ast.models.nodes import PackageInfo
from axm_ast.tools.inspect_resolve import inspect_module


@pytest.fixture()
def small_pkg(tmp_path: Path) -> PackageInfo:
    """Minimal package with a small module."""
    src = tmp_path / "src" / "demo"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    (src / "greet.py").write_text(
        textwrap.dedent("""\
            \"\"\"Greeting helpers.\"\"\"

            def hello(name: str) -> str:
                return f"Hello, {name}"
        """)
    )
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "demo"
            version = "0.1.0"
            [tool.hatch.build.targets.wheel]
            packages = ["src/demo"]
        """)
    )
    from axm_ast.core.cache import get_package

    return get_package(tmp_path)


@pytest.fixture()
def large_pkg(tmp_path: Path) -> PackageInfo:
    """Package with a module exceeding 200 lines."""
    src = tmp_path / "src" / "largepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    lines = ['"""Big module."""', ""]
    for i in range(250):
        lines.append(f"VAR_{i} = {i}")
    (src / "big.py").write_text("\n".join(lines) + "\n")
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "largepkg"
            version = "0.1.0"
            [tool.hatch.build.targets.wheel]
            packages = ["src/largepkg"]
        """)
    )
    from axm_ast.core.cache import get_package

    return get_package(tmp_path)


@pytest.fixture()
def empty_pkg(tmp_path: Path) -> PackageInfo:
    """Package with an empty module (no functions/classes)."""
    src = tmp_path / "src" / "emptymod"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    (src / "bare.py").write_text('"""Just a docstring."""\n\nimport os\n')
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "emptymod"
            version = "0.1.0"
            [tool.hatch.build.targets.wheel]
            packages = ["src/emptymod"]
        """)
    )
    from axm_ast.core.cache import get_package

    return get_package(tmp_path)


class TestInspectModuleSource:
    """Tests for inspect_module source parameter."""

    def test_inspect_module_source_forwarded(self, small_pkg):
        """When source=True, returned detail includes a 'source' key."""
        result = inspect_module(small_pkg, "greet", source=True)
        assert result is not None
        assert result.success is True
        detail = result.data["symbol"]
        assert "source" in detail
        assert "hello" in detail["source"]

    def test_inspect_module_no_source_by_default(self, small_pkg):
        """Default call (source=False) omits 'source' key."""
        result = inspect_module(small_pkg, "greet")
        assert result is not None
        assert result.success is True
        detail = result.data["symbol"]
        assert "source" not in detail


class TestInspectModuleSourceEdgeCases:
    """Edge cases for source parameter."""

    def test_large_module_source_capped(self, large_pkg):
        """Large module (>200 lines) with source=True: source truncated."""
        result = inspect_module(large_pkg, "big", source=True)
        assert result is not None
        assert result.success is True
        detail = result.data["symbol"]
        assert "source" in detail
        source_lines = detail["source"].splitlines()
        assert len(source_lines) <= 210  # capped around 200 lines

    def test_empty_module_source(self, empty_pkg):
        """Empty module (no functions/classes) with source=True: source included."""
        result = inspect_module(empty_pkg, "bare", source=True)
        assert result is not None
        assert result.success is True
        detail = result.data["symbol"]
        assert "source" in detail
        assert len(detail["source"]) > 0
