"""PyPI Adapter — check package name availability.

Uses PyPI JSON API to verify if a package name is taken.
"""

from enum import Enum

import httpx


class AvailabilityStatus(Enum):
    """Package name availability status."""

    AVAILABLE = "available"
    TAKEN = "taken"
    ERROR = "error"


class PyPIAdapter:
    """Adapter for PyPI package name availability checks.

    Uses the PyPI JSON API to check if a package exists.
    """

    PYPI_URL = "https://pypi.org/pypi/{name}/json"
    TIMEOUT = 10.0

    def check_availability(self, name: str) -> AvailabilityStatus:
        """Check if a package name is available on PyPI.

        Args:
            name: Package name to check.

        Returns:
            AvailabilityStatus indicating if name is available.
        """
        if not name or not name.strip():
            return AvailabilityStatus.ERROR

        try:
            url = self.PYPI_URL.format(name=name.lower().strip())
            response = httpx.get(url, timeout=self.TIMEOUT, follow_redirects=True)

            if response.status_code == 404:
                return AvailabilityStatus.AVAILABLE
            if response.status_code == 200:
                return AvailabilityStatus.TAKEN
            return AvailabilityStatus.ERROR

        except httpx.HTTPError:
            return AvailabilityStatus.ERROR
