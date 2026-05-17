"""Split from ``test_doc_impact.py``."""

from pathlib import Path

from axm_ast.core.doc_impact import analyze_doc_impact


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


class TestAnalyzeDocImpact:
    """Functional tests for the full doc impact pipeline."""

    def test_analyze_doc_impact_full(self, tmp_path: Path) -> None:
        """sample_pkg with README + docs/ → complete return structure."""
        root = _make_pkg(
            tmp_path,
            src_code=(
                "class Documented:\n"
                '    """A documented class."""\n'
                "    pass\n"
                "\n"
                "def undoc_func() -> None:\n"
                '    """Not in docs."""\n'
                "    pass\n"
                "\n"
                "def stale_func(a: int, b: int) -> int:\n"
                '    """Stale in docs."""\n'
                "    return a + b\n"
            ),
            readme=(
                "# Project\n\n"
                "Use `Documented` for things.\n\n"
                "```python\n"
                "def stale_func(a):\n"
                "    ...\n"
                "```\n"
            ),
            docs={"api.md": "# API\n\n## Documented\n\nThe `Documented` class.\n"},
        )
        symbols = ["Documented", "undoc_func", "stale_func"]
        result = analyze_doc_impact(root, symbols)

        # Structure check
        assert "doc_refs" in result
        assert "undocumented" in result
        assert "stale_signatures" in result

        # Documented → has refs
        assert len(result["doc_refs"]["Documented"]) >= 1

        # undoc_func → undocumented
        assert "undoc_func" in result["undocumented"]

        # stale_func → stale signature
        assert any(s["symbol"] == "stale_func" for s in result["stale_signatures"])
