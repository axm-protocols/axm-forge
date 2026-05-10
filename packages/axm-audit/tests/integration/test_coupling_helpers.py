from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.coupling import (
    read_coupling_config,
)


class TestCouplingHelpersIntegration:
    @pytest.mark.parametrize(
        ("toml_content",),
        [
            pytest.param(None, id="no_pyproject"),
            pytest.param("{{not valid toml", id="malformed_toml"),
            pytest.param('[project]\nname = "demo"\n', id="missing_coupling_section"),
        ],
    )
    def test_defaults_returned(self, tmp_path: Path, toml_content: str | None) -> None:
        """No/malformed/missing-section pyproject.toml -> 4-tuple of defaults."""
        if toml_content is not None:
            (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")
        result = read_coupling_config(tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_zero_threshold(self, tmp_path: Path) -> None:
        """fan_out_threshold = 0 is valid (not negative)."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.axm-audit.coupling]
            fan_out_threshold = 0
            """),
            encoding="utf-8",
        )
        threshold, _overrides, _bonus, _multiplier = read_coupling_config(tmp_path)
        assert threshold == 0
