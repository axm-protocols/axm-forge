from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture.coupling import (
    read_coupling_config,
)


class TestCouplingHelpersIntegration:
    def test_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml -> all defaults."""
        result = read_coupling_config(tmp_path)
        # Returns the 4-tuple of defaults
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_malformed_toml(self, tmp_path: Path) -> None:
        """Invalid TOML content -> all defaults."""
        (tmp_path / "pyproject.toml").write_text("{{not valid toml", encoding="utf-8")
        result = read_coupling_config(tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_missing_coupling_section(self, tmp_path: Path) -> None:
        """Valid TOML without [tool.axm-audit.coupling] -> all defaults."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [project]
            name = "demo"
            """),
            encoding="utf-8",
        )
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
