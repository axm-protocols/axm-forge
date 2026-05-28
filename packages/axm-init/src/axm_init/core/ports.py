"""Application ports for the ``core`` layer.

Defines the abstractions (``Protocol``) that the application depends
on. Concrete implementations live in ``axm_init.adapters`` and depend
on these ports, never the reverse (hexagonal dependency rule).
"""

from __future__ import annotations

from typing import Protocol

from axm_init.models.results import AvailabilityStatus

__all__ = ["AvailabilityChecker"]


class AvailabilityChecker(Protocol):
    """Port for checking package-name availability on an index."""

    def check_availability(self, name: str) -> AvailabilityStatus:
        """Return the availability status of ``name`` on the index."""
        ...
