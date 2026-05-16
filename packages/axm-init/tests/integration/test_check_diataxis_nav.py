"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

from axm_init.checks.docs import check_diataxis_nav


class TestCheckDiataxisNav:
    def test_pass(self, gold_project: Path) -> None:
        r = check_diataxis_nav(gold_project)
        assert r.passed is True

    def test_fail_flat_nav(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False

    def test_fail_partial(self, tmp_path: Path) -> None:
        mkdocs = "nav:\n  - Tutorials:\n    - t.md\n  - Reference:\n    - r.md\n"
        (tmp_path / "mkdocs.yml").write_text(mkdocs)
        r = check_diataxis_nav(tmp_path)
        assert r.passed is False
        # Should report which Diátaxis sections are missing


def test_diataxis_nav_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for nav check."""
    result = check_diataxis_nav(workspace_member)
    assert result.passed is True
