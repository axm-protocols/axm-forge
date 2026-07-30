"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

from axm_init.checks.docs import check_gen_ref_pages


class TestCheckDocsGenRefPages:
    def test_gen_ref_pages_in_package(self, gold_project: Path) -> None:
        """File exists in package docs/ → check passes."""
        r = check_gen_ref_pages(gold_project)
        assert r.passed is True
        assert r.name == "docs.gen_ref_pages"

    def test_gen_ref_pages_in_workspace(self, tmp_path: Path) -> None:
        """Absent from package, present in workspace root → check passes."""
        # Simulate workspace layout: workspace/packages/my-pkg/
        workspace = tmp_path / "workspace"
        pkg = workspace / "packages" / "my-pkg"
        pkg.mkdir(parents=True)
        # No docs/gen_ref_pages.py in package
        # But present at workspace root
        ws_docs = workspace / "docs"
        ws_docs.mkdir()
        (ws_docs / "gen_ref_pages.py").write_text("")
        r = check_gen_ref_pages(pkg)
        assert r.passed is True

    def test_gen_ref_pages_nowhere(self, tmp_path: Path) -> None:
        """Absent from both package and workspace → check fails."""
        workspace = tmp_path / "workspace"
        pkg = workspace / "packages" / "my-pkg"
        pkg.mkdir(parents=True)
        r = check_gen_ref_pages(pkg)
        assert r.passed is False

    def test_gen_ref_pages_no_workspace(self, tmp_path: Path) -> None:
        """Standalone package (no workspace) → fails if absent."""
        # Package directly in tmp_path, no packages/ parent structure
        r = check_gen_ref_pages(tmp_path)
        assert r.passed is False
