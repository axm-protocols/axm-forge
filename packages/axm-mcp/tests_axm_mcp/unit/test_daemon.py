from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Protocol, cast

import pytest

from axm_mcp.settings import (
    NonProductionPortError,
    resolve_http_port,
    resolve_pid_file,
)


class _DaemonModule(Protocol):
    def daemon_descriptor(self) -> Mapping[str, object]: ...


def _daemon_module() -> _DaemonModule:
    return cast(_DaemonModule, importlib.import_module("axm_mcp.daemon"))


def _only_service() -> dict[str, object]:
    descriptor = _daemon_module().daemon_descriptor()
    assert len(descriptor) == 1
    service = next(iter(descriptor.values()))
    assert isinstance(service, dict)
    return service


def test_descriptor_has_exact_contract_and_profile_pid_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: publish only the supervisor contract and the active PID path."""
    monkeypatch.setenv("AXM_PROFILE", "production")

    service = _only_service()

    assert set(service) == {
        "argv",
        "pid_file",
        "log_file",
        "probe",
        "environment",
    }
    assert service["pid_file"] == str(resolve_pid_file())


def test_http_probe_uses_active_profile_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: publish an HTTP probe using the resolved development port."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.setenv("AXM_MCP_PORT", "9500")

    probe = _only_service()["probe"]

    assert isinstance(probe, dict)
    assert probe["kind"] == "http"
    assert probe["url"].endswith(f":{resolve_http_port()}")
    assert probe["url"].endswith(":9500")


def test_environment_propagates_profile_and_explicit_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: propagate the profile inputs required by the supervised process."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.setenv("AXM_MCP_PORT", "9500")

    environment = _only_service()["environment"]

    assert environment == {"AXM_PROFILE": "dev", "AXM_MCP_PORT": "9500"}


def test_dev_profile_without_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: preserve the settings refusal when a dev port is unspecified."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.delenv("AXM_MCP_PORT", raising=False)

    with pytest.raises(NonProductionPortError):
        _daemon_module().daemon_descriptor()


def test_dev_profile_publishes_hashed_service_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: key the development descriptor by its exact profile-derived id."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.setenv("AXM_MCP_PORT", "9500")

    descriptor = _daemon_module().daemon_descriptor()

    assert set(descriptor) == {"io.axm.mcp.dev3680d487"}


def test_staging_profile_publishes_hashed_service_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: key the staging descriptor by its exact profile-derived id."""
    monkeypatch.setenv("AXM_PROFILE", "staging")
    monkeypatch.setenv("AXM_MCP_PORT", "9501")

    descriptor = _daemon_module().daemon_descriptor()

    assert set(descriptor) == {"io.axm.mcp.staginge0df4265"}


def test_production_and_dev_descriptors_coexist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: preserve two isolated services when production and dev are merged."""
    monkeypatch.setenv("AXM_PROFILE", "production")
    monkeypatch.delenv("AXM_MCP_PORT", raising=False)
    production = _daemon_module().daemon_descriptor()

    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.setenv("AXM_MCP_PORT", "9500")
    development = _daemon_module().daemon_descriptor()

    registry = {**production, **development}
    assert len(registry) == 2

    services = list(registry.values())
    assert all(isinstance(service, dict) for service in services)
    pid_files = {service["pid_file"] for service in services}
    ports = {
        service["probe"]["url"].rsplit(":", maxsplit=1)[-1] for service in services
    }
    assert len(pid_files) == 2
    assert len(ports) == 2
