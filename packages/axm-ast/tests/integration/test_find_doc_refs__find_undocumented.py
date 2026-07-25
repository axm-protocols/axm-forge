"""Split from ``test_doc_impact.py``."""

from pathlib import Path

from axm_ast.core.doc_impact import find_doc_refs, find_undocumented
from axm_ast.models.nodes import FunctionInfo


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


class TestFindUndocumented:
    """Test detection of symbols absent from documentation."""

    def test_undocumented_detected(self, tmp_path: Path) -> None:
        """Public docstring-less symbol absent from docs → still undocumented.

        Contract update (L4): ``find_undocumented`` now consults the shared
        ``is_documentation_required`` policy via the ``symbol_nodes`` index, so
        the flagged symbol must be a genuine gap (public + no docstring). The
        previous fixture used a *docstringed* ``secret_func`` and asserted it
        was flagged — that encoded the false positive this ticket removes.
        """
        root = _make_pkg(
            tmp_path,
            src_code="def secret_func() -> None:\n    pass\n",
            readme="# My Project\n\nNothing about secret_func here.\n",
            docs={"guide.md": "# Guide\n\nNo mention of secret_func.\n"},
        )
        # find_doc_refs returns empty for secret_func; the node has no docstring
        # → is_documentation_required True → still undocumented.
        refs = find_doc_refs(root, ["secret_func"])
        nodes = {
            "secret_func": FunctionInfo(
                name="secret_func", docstring=None, line_start=1, line_end=2
            )
        }
        undocumented = find_undocumented(refs, nodes)
        assert "secret_func" in undocumented

    def test_docstringed_public_symbol_not_flagged(self, tmp_path: Path) -> None:
        """Docstringed public symbol with no prose ref → NOT undocumented.

        Contract update (L4): carrying a docstring satisfies the policy even
        when the symbol is absent from prose docs.
        """
        root = _make_pkg(
            tmp_path,
            src_code=(
                'def documented() -> None:\n    """Has a docstring."""\n    pass\n'
            ),
            readme="# My Project\n\nNothing here.\n",
        )
        refs = find_doc_refs(root, ["documented"])
        nodes = {
            "documented": FunctionInfo(
                name="documented",
                docstring="Has a docstring.",
                line_start=1,
                line_end=2,
            )
        }
        undocumented = find_undocumented(refs, nodes)
        assert "documented" not in undocumented
