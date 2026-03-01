"""Tests for PyPIAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter


class TestAvailabilityStatus:
    """Tests for AvailabilityStatus enum."""

    def test_status_values(self) -> None:
        """Enum has expected values."""
        assert AvailabilityStatus.AVAILABLE.value == "available"
        assert AvailabilityStatus.TAKEN.value == "taken"
        assert AvailabilityStatus.ERROR.value == "error"


class TestPyPIAdapter:
    """Tests for PyPI availability checking."""

    def test_check_taken_package(self) -> None:
        """Known packages return TAKEN."""
        adapter = PyPIAdapter()
        # 'requests' is definitely taken
        status = adapter.check_availability("requests")
        assert status == AvailabilityStatus.TAKEN

    def test_check_available_package(self) -> None:
        """Random unique name returns AVAILABLE."""
        adapter = PyPIAdapter()
        # Very unlikely to be taken
        status = adapter.check_availability("axm-test-pkg-xyz-12345-nonexistent")
        assert status == AvailabilityStatus.AVAILABLE

    def test_check_invalid_name(self) -> None:
        """Invalid package names handled gracefully."""
        adapter = PyPIAdapter()
        # Empty or invalid names
        status = adapter.check_availability("")
        assert status == AvailabilityStatus.ERROR


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
