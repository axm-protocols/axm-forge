"""Split from ``test_identity.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.identity import (
    GitProfileConfig,
    load_config,
)

pytestmark = pytest.mark.integration

AXM_WORKSPACE_ROOT = Path("/tmp/axm-workspaces-test-root")
AXM_WORKSPACE = AXM_WORKSPACE_ROOT / "axm-nexus" / "packages" / "axm-nexus"

VALID_TOML = f"""\
workspace_paths = ["{AXM_WORKSPACE_ROOT}"]

[default]
name = "Gabriel"
email = "gabriel@example.com"

[profiles.axiom]
name = "Axiom"
email = "axiom@axm-protocol.io"

[[schedule.rules]]
profile = "axiom"
days = ["mon", "tue", "wed", "thu", "fri"]
start = "09:00"
end = "18:00"
"""


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_valid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        config = load_config(cfg_file)
        assert config is not None
        assert isinstance(config, GitProfileConfig)
        assert config.default.name == "Gabriel"
        assert "axiom" in config.profiles
        assert len(config.schedule.rules) == 1

    def test_load_config_missing_file(self, tmp_path: Path) -> None:
        result = load_config(tmp_path / "nonexistent.toml")
        assert result is None

    def test_load_config_invalid_toml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text("[[[invalid toml")
        result = load_config(cfg_file)
        assert result is None

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Config file exists but is 0 bytes."""
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text("")
        result = load_config(cfg_file)
        assert result is None
