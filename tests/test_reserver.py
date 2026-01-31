"""Tests for PyPI Reserver — RED phase."""

from pathlib import Path
from unittest.mock import patch


class TestReserveResult:
    """Tests for ReserveResult model."""

    def test_reserve_result_success(self) -> None:
        """ReserveResult captures success state."""
        from axm_init.core.reserver import ReserveResult

        result = ReserveResult(
            success=True,
            package_name="my-package",
            version="0.0.1.dev0",
            message="Published successfully",
        )
        assert result.success is True
        assert result.package_name == "my-package"


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
        from axm_init.adapters.pypi import AvailabilityStatus
        from axm_init.core.reserver import reserve_pypi

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
        from axm_init.adapters.pypi import AvailabilityStatus
        from axm_init.core.reserver import reserve_pypi

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
