"""Integration tests for doc-impact text rendering against real packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.doc_impact import DocImpactTool


def _make_tmp_package(tmp_path: Path, *, with_docs: bool = True) -> Path:
    """Create a minimal Python package for functional testing."""
    src = tmp_path / "src" / "mypkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text(
        "def documented_func(x: int) -> int:\n    return x\n\n"
        "def undocumented_func(y: int) -> int:\n    return y\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )
    if with_docs:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "api.md").write_text("# API\n`documented_func`\n")
    return tmp_path


def test_tool_returns_text(tmp_path):
    pkg = _make_tmp_package(tmp_path)
    from axm_ast.tools.doc_impact import DocImpactTool

    tool = DocImpactTool()
    result = tool.execute(
        path=str(pkg), symbols=["documented_func", "undocumented_func"]
    )
    assert result.success
    assert result.text is not None
    assert isinstance(result.text, str)
    assert "doc_refs" in result.data
    assert "undocumented" in result.data
    assert "stale_signatures" in result.data


def test_tool_text_matches_data(tmp_path):
    pkg = _make_tmp_package(tmp_path)
    from axm_ast.tools.doc_impact import DocImpactTool

    tool = DocImpactTool()
    result = tool.execute(
        path=str(pkg), symbols=["documented_func", "undocumented_func"]
    )
    assert result.success
    data = result.data
    text = result.text
    assert text is not None

    n_symbols = len(data["doc_refs"])
    n_documented = sum(1 for refs in data["doc_refs"].values() if refs)
    n_undocumented = len(data["undocumented"])
    n_stale = len(data["stale_signatures"])

    assert f"{n_symbols} symbols" in text
    assert f"{n_documented} documented" in text
    assert f"{n_undocumented} undocumented" in text
    assert f"{n_stale} stale" in text


def test_all_symbols_undocumented(tmp_path):
    pkg = _make_tmp_package(tmp_path, with_docs=False)
    from axm_ast.tools.doc_impact import DocImpactTool

    tool = DocImpactTool()
    result = tool.execute(
        path=str(pkg), symbols=["documented_func", "undocumented_func"]
    )
    assert result.success
    text = result.text
    assert text is not None
    assert "refs:" not in text
    assert "undocumented:" in text


def _make_pkg(
    tmp_path: Path,
    *,
    src_code: str,
    readme: str | None = None,
    docs: dict[str, str] | None = None,
) -> Path:
    """Create a minimal Python package with optional docs.

    Returns the project root (tmp_path), not the src dir.
    """
    # Source package
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""mypkg."""\n')
    (pkg / "core.py").write_text(src_code)

    # pyproject.toml (needed for analyze_package)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )

    # README
    if readme is not None:
        (tmp_path / "README.md").write_text(readme)

    # docs/
    if docs is not None:
        for name, content in docs.items():
            doc_path = tmp_path / "docs" / name
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content)

    return tmp_path


@pytest.fixture()
def doc_impact_tool() -> DocImpactTool:
    return DocImpactTool()


class TestDocImpactTool:
    """Test the MCP tool wrapper."""

    def test_tool_execute(self, tmp_path: Path) -> None:
        """DocImpactTool.execute on sample_pkg → ToolResult success."""
        from axm_ast.tools.doc_impact import DocImpactTool

        root = _make_pkg(
            tmp_path,
            src_code=('class MyClass:\n    """A class."""\n    pass\n'),
            readme="# Project\n\nUse `MyClass`.\n",
        )
        tool = DocImpactTool()
        result = tool.execute(path=str(root), symbols=["MyClass"])

        assert result.success is True
        assert result.data is not None
        assert "doc_refs" in result.data
        assert "undocumented" in result.data
        assert "stale_signatures" in result.data


class TestDocImpactNoDocstring:
    """Call doc_impact on symbol without docstring → handles None."""

    def test_doc_impact_no_docstring(
        self, doc_impact_tool: DocImpactTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.doc_impact.analyze_doc_impact",
            return_value=[
                {
                    "symbol": "greet",
                    "has_docstring": False,
                    "docstring": None,
                    "impact": "low",
                }
            ],
        )
        result = doc_impact_tool.execute(path=str(simple_pkg), symbols=["greet"])
        assert result.success is True
        items: list[dict[str, Any]] = result.data  # type: ignore[assignment]
        assert items[0]["has_docstring"] is False
        assert items[0]["docstring"] is None


class TestDocImpactToolEdgeCasesIntegration:
    """DocImpactTool edge cases — exception."""

    def test_exception(
        self, doc_impact_tool: DocImpactTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.doc_impact.analyze_doc_impact",
            side_effect=RuntimeError("boom"),
        )
        result = doc_impact_tool.execute(path=str(simple_pkg), symbols=["greet"])
        assert result.success is False
        assert "boom" in (result.error or "")
