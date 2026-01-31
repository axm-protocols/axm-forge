"""Tests for PyPIAdapter — RED phase."""


class TestAvailabilityStatus:
    """Tests for AvailabilityStatus enum."""

    def test_status_values(self) -> None:
        """Enum has expected values."""
        from axm_init.adapters.pypi import AvailabilityStatus

        assert AvailabilityStatus.AVAILABLE.value == "available"
        assert AvailabilityStatus.TAKEN.value == "taken"
        assert AvailabilityStatus.ERROR.value == "error"


class TestPyPIAdapter:
    """Tests for PyPI availability checking."""

    def test_check_taken_package(self) -> None:
        """Known packages return TAKEN."""
        from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

        adapter = PyPIAdapter()
        # 'requests' is definitely taken
        status = adapter.check_availability("requests")
        assert status == AvailabilityStatus.TAKEN

    def test_check_available_package(self) -> None:
        """Random unique name returns AVAILABLE."""
        from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

        adapter = PyPIAdapter()
        # Very unlikely to be taken
        status = adapter.check_availability("axm-test-pkg-xyz-12345-nonexistent")
        assert status == AvailabilityStatus.AVAILABLE

    def test_check_invalid_name(self) -> None:
        """Invalid package names handled gracefully."""
        from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

        adapter = PyPIAdapter()
        # Empty or invalid names
        status = adapter.check_availability("")
        assert status == AvailabilityStatus.ERROR
