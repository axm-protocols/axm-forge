"""The profile-owned network listening point resolved end to end.

The guarantee worth protecting is twofold. Production is frozen: with nothing
configured a service observes exactly the adopted default it ships with today,
so wiring an existing installation up changes nothing. Outside production the
profile itself supplies a usable port, and it does so only as the ``default``
argument handed to :func:`axm_config.paths.get_int`, so the established
``env > file > default`` precedence stays untouched.

These cases exercise the real resolution boundary -- an isolated ``AXM_HOME``
on disk plus the process environment -- hence the integration level.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import paths, profile, resolver

pytestmark = pytest.mark.integration

_PORT_ENV_VARS = (
    "AXM_NETWORK_MCP_PORT",
    "AXM_NETWORK_ORISON_WEB_PORT",
    "AXM_MCP_PORT",
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty AXM home with every port variable cleared from the environment."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    for name in _PORT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_production_serves_the_adopted_defaults(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: production returns the two adopted ports byte for byte."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, profile.DEFAULT_PROFILE)

    assert paths.service_port("mcp") == 9427
    assert paths.service_port("orison_web") == 8840


def test_a_non_production_profile_obtains_a_usable_port(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an unconfigured profile still gets a port instead of a refusal."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")

    mcp = paths.service_port("mcp")
    orison_web = paths.service_port("orison_web")

    assert isinstance(mcp, int)
    assert isinstance(orison_web, int)
    assert 1024 <= mcp <= 65535
    assert 1024 <= orison_web <= 65535


def test_two_resolutions_under_one_profile_agree(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: the allocation is stable, so a restart rebinds the same port."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")

    assert paths.service_port("mcp") == paths.service_port("mcp")


def test_two_profiles_do_not_share_the_mcp_port(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: two installations on one machine do not fight over a port."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")
    alpha = paths.service_port("mcp")
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "beta")
    beta = paths.service_port("mcp")

    assert alpha != beta


def test_two_services_under_one_profile_do_not_share_a_port(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: one profile hosts both services at once, so they must differ."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")

    assert paths.service_port("mcp") != paths.service_port("orison_web")


def test_a_configured_environment_value_preempts_the_profile_allocation(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6: the profile only supplies a default, env still outranks it."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")
    monkeypatch.setenv(resolver._env_name("network", "mcp_port"), "5555")

    assert paths.service_port("mcp") == 5555


def test_an_unknown_service_id_is_a_typed_configuration_error(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7: an unregistered service is refused, naming the offending id."""
    monkeypatch.setenv(profile.PROFILE_ENV_VAR, "alpha")

    with pytest.raises(resolver.ConfigError) as exc_info:
        paths.service_port("nope")

    assert "nope" in str(exc_info.value)
