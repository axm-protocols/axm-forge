"""Tests covering the (GitProfileConfig, load_config) symbol tuple.

Split from a former combined test file: tests whose assertions reach into
GitProfileConfig's shape (.default, .profiles, .schedule.rules) live here;
tests that only assert on load_config's return-or-None contract live in
test_load_config.py.
"""

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
    """Tests asserting on GitProfileConfig shape after load_config."""

    def test_load_config_valid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        config = load_config(cfg_file)
        assert config is not None
        assert isinstance(config, GitProfileConfig)
        assert config.default.name == "Gabriel"
        assert "axiom" in config.profiles
        assert len(config.schedule.rules) == 1
