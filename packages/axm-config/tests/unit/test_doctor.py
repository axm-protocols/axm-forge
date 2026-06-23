from __future__ import annotations

import pytest

from axm_config.doctor import config_doctor_data


def test_provenance_env_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC3: an env-supplied key resolves to the 'env' layer, present True."""
    monkeypatch.setenv("AXM_DEMO_KEY", "from-env")

    report = config_doctor_data(namespace="demo")

    assert "demo.key" in report
    entry = report["demo.key"]
    assert entry["layer"] == "env"
    assert entry["present"] is True


def test_provenance_default_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: with nothing set, a key resolves to 'default' layer, present False."""
    monkeypatch.delenv("AXM_DEMO_KEY", raising=False)

    report = config_doctor_data(namespace="demo")

    for entry in report.values():
        assert entry["layer"] == "default"
        assert entry["present"] is False
