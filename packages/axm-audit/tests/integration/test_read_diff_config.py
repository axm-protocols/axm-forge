"""Split from ``test_quality_rule_io.py``."""

from pathlib import Path

import pytest


class TestDiffSizeRule:
    """Integration tests for DiffSizeRule config reading (real pyproject.toml I/O)."""

    @pytest.mark.parametrize(
        ("pyproject_content", "expected_ideal", "expected_max"),
        [
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = 300\n",
                300,
                1200,
                id="override_ideal",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_max = 1000\n",
                400,
                1000,
                id="override_max",
            ),
            pytest.param(
                '[project]\nname = "demo"\n',
                400,
                1200,
                id="no_axm_audit_section_uses_defaults",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = 250\n",
                250,
                1200,
                id="partial_config_ideal_only",
            ),
            pytest.param(
                '[tool.axm-audit]\ndiff_size_ideal = "abc"\n',
                400,
                1200,
                id="invalid_non_numeric_falls_back",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = -10\n",
                400,
                1200,
                id="negative_threshold_falls_back",
            ),
            pytest.param(None, 400, 1200, id="missing_pyproject_uses_defaults"),
        ],
    )
    def test_read_diff_config(
        self,
        tmp_path: Path,
        pyproject_content: str | None,
        expected_ideal: int,
        expected_max: int,
    ) -> None:
        """read_diff_config honours config overrides and falls back to defaults."""
        from axm_audit.core.rules.quality import read_diff_config

        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == expected_ideal
        assert max_lines == expected_max
