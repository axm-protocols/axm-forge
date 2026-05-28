"""Tests for core/reserver.py — models, dry-run, subprocess paths, full flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from axm_init.core.reserver import (
    reserve_pypi,
)
from axm_init.models.results import AvailabilityStatus


def test_reserve_checks_availability_first(tmp_path: Path) -> None:
    """reserve_pypi checks availability before proceeding."""
    checker = MagicMock()
    checker.check_availability.return_value = AvailabilityStatus.TAKEN

    result = reserve_pypi(
        name="requests",  # Known taken
        author="Test",
        email="test@example.com",
        token="pypi-test",
        dry_run=True,
        checker=checker,
    )

    assert result.success is False
    assert "taken" in result.message.lower()


def test_reserve_dry_run_skips_publish(tmp_path: Path) -> None:
    """dry_run=True skips actual publish."""
    checker = MagicMock()
    checker.check_availability.return_value = AvailabilityStatus.AVAILABLE

    result = reserve_pypi(
        name="unique-test-pkg-xyz",
        author="Test",
        email="test@example.com",
        token="pypi-test",
        dry_run=True,
        checker=checker,
    )

    assert result.success is True
    assert "dry run" in result.message.lower()
