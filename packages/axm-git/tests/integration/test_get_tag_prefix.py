"""Split from ``test_tag.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.tools.tag import get_tag_prefix

# ── Tag prefix regression tests (AXM-371) ────────────────────


class TestGetTagPrefix:
    """Regression tests for get_tag_prefix helper."""

    @pytest.mark.parametrize(
        ("pyproject_content", "expected"),
        [
            pytest.param(
                '[tool.hatch.version]\ntag-pattern = "git/v(?P<version>.*)"\n',
                "git/",
                id="reads_pattern",
            ),
            pytest.param(
                '[tool.hatch.version]\nsource = "vcs"\n',
                "",
                id="no_pattern",
            ),
            pytest.param(None, "", id="no_pyproject"),
        ],
    )
    def test_get_tag_prefix(
        self, tmp_path: Path, pyproject_content: str | None, expected: str
    ) -> None:
        """Resolves prefix from pyproject.toml, empty when missing/absent."""
        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        assert get_tag_prefix(tmp_path) == expected
