"""Integration tests for rejected catalog contributions in vault_doctor."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest

from axm_vault.catalog import load_catalog
from axm_vault.tools import VaultDoctorTool


@pytest.fixture
def broken_credential_contribution(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Install a malformed axm.credentials contribution on the real import path."""
    (tmp_path / "fake_broken.py").write_text(
        "ALREADY_BUILT = object()\n",
        encoding="utf-8",
    )
    dist_info = tmp_path / "broken-0.1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: broken\nVersion: 0.1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        "[axm.credentials]\nbroken = fake_broken:ALREADY_BUILT\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    load_catalog.cache_clear()
    yield
    load_catalog.cache_clear()


@pytest.mark.integration
def test_doctor_result_carries_skipped_contribution_as_data(
    broken_credential_contribution: None,
) -> None:
    """AC1: rejected contributions remain observable in vault_doctor data."""
    result = VaultDoctorTool().execute()

    assert result.success is True
    assert any(
        rejection.get("entry_point") == "broken" and rejection.get("reason")
        for rejection in result.data["rejections"]
    )


@pytest.mark.integration
def test_doctor_text_names_skipped_contribution(
    broken_credential_contribution: None,
) -> None:
    """AC2: vault_doctor text names every skipped contribution."""
    result = VaultDoctorTool().execute()

    assert result.text is not None
    assert any(
        "skipped contributions" in line.lower() and "broken" in line
        for line in result.text.splitlines()
    )
