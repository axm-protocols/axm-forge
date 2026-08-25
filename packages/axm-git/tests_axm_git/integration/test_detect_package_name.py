"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import detect_package_name


class TestDetectPackageName:
    """Test detect_package_name helper."""

    def test_valid_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-pkg"\n')
        assert detect_package_name(tmp_path) == "my-pkg"

    @pytest.mark.parametrize(
        "pyproject_content",
        [
            pytest.param(None, id="missing_pyproject"),
            pytest.param("[build-system]\n", id="no_project_section"),
            pytest.param("{{invalid toml}}", id="invalid_toml"),
        ],
    )
    def test_returns_none_on_invalid_pyproject(
        self, tmp_path: Path, pyproject_content: str | None
    ) -> None:
        """All non-extractable pyproject states return None."""
        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        assert detect_package_name(tmp_path) is None
