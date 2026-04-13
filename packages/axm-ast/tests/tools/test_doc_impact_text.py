from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_ast.tools.doc_impact_text import render_doc_impact_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _make_result():
    """Factory for doc-impact result dicts."""

    def _factory(
        doc_refs: dict[str, Any] | None = None,
        undocumented: list[str] | None = None,
        stale_signatures: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "doc_refs": doc_refs or {},
            "undocumented": undocumented or [],
            "stale_signatures": stale_signatures or [],
        }

    return _factory


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_header_counts(_make_result):
    result = _make_result(
        doc_refs={"A": [{"file": "README.md", "line": 1}], "B": []},
        undocumented=["B"],
        stale_signatures=[],
    )
    text = render_doc_impact_text(result)
    assert "2 symbols" in text
    assert "1 documented" in text
    assert "1 undocumented" in text
    assert "0 stale" in text


def test_refs_grouped_by_file(_make_result):
    result = _make_result(
        doc_refs={
            "sym": [
                {"file": "a.md", "line": 1},
                {"file": "a.md", "line": 5},
                {"file": "b.md", "line": 3},
            ]
        },
    )
    text = render_doc_impact_text(result)
    assert "sym (3)" in text
    assert "a.md:1,5" in text
    assert "b.md:3" in text
    # File groups separated by ·
    assert "\u00b7" in text


def test_empty_refs_omitted(_make_result):
    result = _make_result(
        doc_refs={"A": []},
        undocumented=["A"],
    )
    text = render_doc_impact_text(result)
    assert "refs:" not in text


def test_undocumented_comma_joined(_make_result):
    result = _make_result(
        undocumented=["foo", "bar", "baz"],
    )
    text = render_doc_impact_text(result)
    assert "undocumented: foo, bar, baz" in text


def test_empty_undocumented_omitted(_make_result):
    result = _make_result(
        doc_refs={"A": [{"file": "README.md", "line": 1}]},
        undocumented=[],
    )
    text = render_doc_impact_text(result)
    assert "undocumented" not in text.split("\n", 1)[-1]  # not in body (only header)


def test_stale_rendering(_make_result):
    result = _make_result(
        stale_signatures=[
            {
                "symbol": "f",
                "file": "R.md",
                "line": 4,
                "doc_sig": "def f(a)",
                "actual_sig": "def f(a, b)",
            }
        ],
    )
    text = render_doc_impact_text(result)
    assert "f @ R.md:4" in text
    assert "doc:" in text
    assert "actual:" in text
    assert "def f(a)" in text
    assert "def f(a, b)" in text


def test_empty_stale_omitted(_make_result):
    result = _make_result(
        doc_refs={"A": [{"file": "README.md", "line": 1}]},
        stale_signatures=[],
    )
    text = render_doc_impact_text(result)
    assert "stale:" not in text


def test_all_empty(_make_result):
    result = _make_result()
    text = render_doc_impact_text(result)
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    assert len(lines) == 1  # header only
    assert "0 symbols" in lines[0]


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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


def test_single_ref_single_symbol(_make_result):
    result = _make_result(
        doc_refs={"only_sym": [{"file": "README.md", "line": 7}]},
    )
    text = render_doc_impact_text(result)
    assert "only_sym (1)" in text
    assert "README.md:7" in text


def test_symbol_with_refs_in_many_files(_make_result):
    refs = [{"file": f"docs/f{i}.md", "line": i * 10} for i in range(1, 12)]
    result = _make_result(doc_refs={"big_sym": refs})
    text = render_doc_impact_text(result)
    assert "big_sym (11)" in text
    # All file groups separated by ·
    ref_line = next(ln for ln in text.splitlines() if "big_sym" in ln and "(11)" in ln)
    assert ref_line.count("\u00b7") == 10  # 11 files -> 10 separators
