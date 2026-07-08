from __future__ import annotations

import pytest

from axm_config import ConfigError
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
    """AC1: with nothing set, an env-visible key resolves to a non-env layer.

    A file key seeds the report so the loop actually runs (the old test
    iterated an empty report -- vacuously green). Only the env var for a
    *different* key is set, so the seeded key must report ``file``/``present``.
    """
    monkeypatch.delenv("AXM_DEMO_KEY", raising=False)
    monkeypatch.setattr(
        "axm_config.doctor._store",
        _StubStore({"demo": {"token": "seeded"}}),
    )

    report = config_doctor_data(namespace="demo")

    assert report["demo.token"] == {"layer": "file", "present": True}


class _StubStore:
    """In-memory stand-in for the doctor's ``_store`` (no real I/O)."""

    def __init__(self, data: dict[str, dict[str, object]]) -> None:
        self._data = data

    def read(self, ns: str) -> dict[str, object]:
        return dict(self._data.get(ns, {}))

    def namespaces(self) -> list[str]:
        return sorted(self._data)


def test_doctor_drops_child_namespace_ghost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P0-1: a child namespace's env var must not leak as a key of the parent.

    ``AXM_A__B_C`` belongs to namespace ``a.b`` (key ``c``), but it shares the
    ``AXM_A_`` prefix of namespace ``a``. The doctor must not report a phantom
    ``a._b_c`` (a bogus leading-underscore key) for namespace ``a``; the var is
    a legitimate ``a.b.c`` env key for the *child* namespace instead. Exercised
    through the public ``config_doctor_data`` surface.
    """
    monkeypatch.setenv("AXM_A__B_C", "1")
    monkeypatch.setattr("axm_config.doctor._store", _StubStore({}))

    assert config_doctor_data(namespace="a") == {}
    assert config_doctor_data(namespace="a.b") == {
        "a.b.c": {"layer": "env", "present": True}
    }


def test_doctor_keeps_legal_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed env var for the namespace is still reported as an env key."""
    monkeypatch.setenv("AXM_A_FRED_API_KEY", "1")
    monkeypatch.setattr("axm_config.doctor._store", _StubStore({}))

    assert config_doctor_data(namespace="a") == {
        "a.fred_api_key": {"layer": "env", "present": True}
    }


def test_doctor_invalid_namespace_raises_config_error() -> None:
    """P1-1: an invalid namespace is refused as ConfigError, not a raw ValueError.

    ``config_doctor_data`` is a public surface; it must validate its namespace
    like every other boundary so the CLI (which catches ``ConfigError``)
    never leaks a raw traceback for a traversal argument.
    """
    with pytest.raises(ConfigError):
        config_doctor_data(namespace="../x")
