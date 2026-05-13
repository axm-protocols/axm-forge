"""Integration tests for doc-impact text rendering against real packages."""

from __future__ import annotations

from pathlib import Path


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
