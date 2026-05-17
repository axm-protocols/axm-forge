"""Split from ``test_tag.py``."""

from __future__ import annotations

from pathlib import Path

from axm_git.tools.tag import _get_tag_prefix

# ── Tag prefix regression tests (AXM-371) ────────────────────


class TestGetTagPrefix:
    """Regression tests for _get_tag_prefix helper."""

    def test_get_tag_prefix_reads_pattern(self, tmp_path: Path) -> None:
        """Reads tag-pattern and extracts prefix."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.hatch.version]\ntag-pattern = "git/v(?P<version>.*)"\n'
        )
        assert _get_tag_prefix(tmp_path) == "git/"

    def test_get_tag_prefix_no_pattern(self, tmp_path: Path) -> None:
        """Returns empty when no tag-pattern in pyproject."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.hatch.version]\nsource = "vcs"\n')
        assert _get_tag_prefix(tmp_path) == ""

    def test_get_tag_prefix_no_pyproject(self, tmp_path: Path) -> None:
        """Returns empty when pyproject.toml does not exist."""
        assert _get_tag_prefix(tmp_path) == ""
