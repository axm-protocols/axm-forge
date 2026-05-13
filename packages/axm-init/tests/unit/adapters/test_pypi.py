"""Tests for PyPIAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter


class TestAvailabilityStatus:
    """Tests for AvailabilityStatus enum."""

    def test_status_values(self) -> None:
        """Enum has expected values."""
        assert AvailabilityStatus.AVAILABLE.value == "available"
        assert AvailabilityStatus.TAKEN.value == "taken"
        assert AvailabilityStatus.ERROR.value == "error"

    def test_availability_status_is_str(self) -> None:
        """StrEnum members are instances of str."""
        assert isinstance(AvailabilityStatus.AVAILABLE, str)
        assert isinstance(AvailabilityStatus.TAKEN, str)
        # Direct string comparison works with StrEnum
        assert AvailabilityStatus.TAKEN == "taken"  # type: ignore[comparison-overlap]


class TestPyPIAdapter:
    """Tests for PyPI availability checking."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            pytest.param("requests", AvailabilityStatus.TAKEN, id="taken"),
            pytest.param(
                "axm-test-pkg-xyz-12345-nonexistent",
                AvailabilityStatus.AVAILABLE,
                id="available",
            ),
            pytest.param("", AvailabilityStatus.ERROR, id="invalid"),
        ],
    )
    def test_check_availability(self, name: str, expected: AvailabilityStatus) -> None:
        """check_availability returns the expected status for each name."""
        adapter = PyPIAdapter()
        assert adapter.check_availability(name) == expected


# ── Error path edge cases ────────────────────────────────────────────────────


class TestPyPIAdapterError:
    """Cover adapters/pypi.py error paths."""

    def test_empty_name_returns_error(self) -> None:
        """Empty package name returns ERROR status."""
        adapter = PyPIAdapter()
        assert adapter.check_availability("") == AvailabilityStatus.ERROR

    @patch("axm_init.adapters.pypi.httpx.get")
    def test_unexpected_status_returns_error(self, mock_get: MagicMock) -> None:
        """Non-200/404 status code returns ERROR."""
        mock_get.return_value.status_code = 500
        adapter = PyPIAdapter()
        assert adapter.check_availability("test") == AvailabilityStatus.ERROR
