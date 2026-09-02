"""Integration coverage for the profile-aware ticket database path."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import paths


@pytest.fixture
def isolated_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Redirect profile and production stores to an isolated real filesystem."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AXM_HOME", raising=False)
    monkeypatch.delenv("AXM_TICKETS_DB_PATH", raising=False)
    return tmp_path


@pytest.mark.integration
def test_tickets_db_uses_the_production_default(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: production defaults to the historical ~/axm ticket store."""
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = paths.tickets_db()

    assert result == isolated_home / "axm" / "tickets" / "tickets.db"


@pytest.mark.integration
def test_tickets_db_uses_the_dev_profile_root(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an unconfigured dev store is contained by its profile root."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    profile_root = isolated_home / ".axm" / "profiles" / "dev"

    result = paths.tickets_db()

    assert result.is_relative_to(profile_root)


@pytest.mark.integration
def test_tickets_db_honours_the_active_profile_store(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: the active dev profile's configured ticket path wins."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    profile_root = isolated_home / ".axm" / "profiles" / "dev"
    configured = profile_root / "db" / "custom.db"
    profile_root.mkdir(parents=True)
    (profile_root / "config.toml").write_text(
        f'[tickets]\ndb_path = "{configured}"\n',
        encoding="utf-8",
    )

    result = paths.tickets_db()

    assert result == configured.resolve()
