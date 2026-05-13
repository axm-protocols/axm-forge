"""Tests for core/reserver.py — models, dry-run, subprocess paths, full flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from axm_init.adapters.pypi import AvailabilityStatus
from axm_init.core.reserver import (
    reserve_pypi,
)

# ── Core reservation logic ──────────────────────────────────────────────────


class TestReserver:
    """Tests for PyPI reservation."""

    def test_create_minimal_package(self, tmp_path: Path) -> None:
        """Creates minimal package structure for reservation."""
        from axm_init.core.reserver import create_minimal_package

        create_minimal_package(
            name="test-pkg",
            author="Test Author",
            email="test@example.com",
            target_path=tmp_path,
        )

        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "src" / "test_pkg" / "__init__.py").exists()

    def test_reserve_checks_availability_first(self, tmp_path: Path) -> None:
        """reserve_pypi checks availability before proceeding."""
        with patch("axm_init.core.reserver.PyPIAdapter") as mock_adapter:
            mock_adapter.return_value.check_availability.return_value = (
                AvailabilityStatus.TAKEN
            )

            result = reserve_pypi(
                name="requests",  # Known taken
                author="Test",
                email="test@example.com",
                token="pypi-test",
                dry_run=True,
            )

            assert result.success is False
            assert "taken" in result.message.lower()

    def test_reserve_dry_run_skips_publish(self, tmp_path: Path) -> None:
        """dry_run=True skips actual publish."""
        with patch("axm_init.core.reserver.PyPIAdapter") as mock_adapter:
            mock_adapter.return_value.check_availability.return_value = (
                AvailabilityStatus.AVAILABLE
            )

            result = reserve_pypi(
                name="unique-test-pkg-xyz",
                author="Test",
                email="test@example.com",
                token="pypi-test",
                dry_run=True,
            )

            assert result.success is True
            assert "dry run" in result.message.lower()
