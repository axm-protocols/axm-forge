"""Split from ``test_doc_impact.py``."""

from pathlib import Path
from unittest.mock import MagicMock, patch


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


class TestDocImpactHook:
    """Test the engine hook wrapper for doc impact."""

    def test_doc_impact_hook_full_report(self, tmp_path: Path) -> None:
        """Hook execute with undocumented symbol → metadata contains undocumented."""
        from axm_ast.hooks.impact import DocImpactHook

        root = _make_pkg(
            tmp_path,
            src_code=('def secret() -> None:\n    """Not in docs."""\n    pass\n'),
            readme="# Project\n\nNo mention of secret here.\n",
        )
        hook = DocImpactHook()
        result = hook.execute(context={}, symbol="secret", path=str(root))

        assert result.success is True
        assert "undocumented" in result.metadata
        assert "secret" in result.metadata["undocumented"]

    def test_doc_impact_hook_stale_key_present(self, tmp_path: Path) -> None:
        """Hook execute with any symbol → stale_signatures key exists in metadata."""
        from axm_ast.hooks.impact import DocImpactHook

        root = _make_pkg(
            tmp_path,
            src_code=('class Foo:\n    """A foo."""\n    pass\n'),
            readme="# Project\n\nUse `Foo`.\n",
        )
        hook = DocImpactHook()
        result = hook.execute(context={}, symbol="Foo", path=str(root))

        assert result.success is True
        assert "stale_signatures" in result.metadata


class TestDocImpactHookExecuteIntegration:
    """Tests for DocImpactHook — single and multi-symbol doc impact analysis."""

    @patch("axm_ast.core.doc_impact.analyze_doc_impact")
    def test_doc_impact_hook_execute(
        self,
        mock_doc_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Context with path + symbols → HookResult success with doc_refs."""
        from axm_ast.hooks.impact import DocImpactHook

        mock_doc_impact.return_value = {
            "doc_refs": {
                "Foo": [{"file": "README.md", "line": 10}],
            },
            "undocumented": [],
            "stale_signatures": [],
        }

        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo", path=str(tmp_path))

        assert result.success
        mock_doc_impact.assert_called_once_with(tmp_path, ["Foo"])
        assert result.metadata["doc_refs"] == {
            "Foo": [{"file": "README.md", "line": 10}],
        }

    @patch("axm_ast.core.doc_impact.analyze_doc_impact")
    def test_doc_impact_hook_multi_symbols(
        self,
        mock_doc_impact: MagicMock,
        tmp_path: Path,
    ) -> None:
        """symbols="Foo\\nBar" → Results for both symbols."""
        from axm_ast.hooks.impact import DocImpactHook

        mock_doc_impact.return_value = {
            "doc_refs": {
                "Foo": [{"file": "README.md", "line": 5}],
                "Bar": [{"file": "docs/api.md", "line": 12}],
            },
            "undocumented": [],
            "stale_signatures": [],
        }

        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo\nBar", path=str(tmp_path))

        assert result.success
        mock_doc_impact.assert_called_once_with(tmp_path, ["Foo", "Bar"])
        assert "Foo" in result.metadata["doc_refs"]
        assert "Bar" in result.metadata["doc_refs"]
