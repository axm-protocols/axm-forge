"""axm - AXM CLI — thin autodiscovery wrapper for the AXM ecosystem"""

from axm._version import __version__

__all__ = ["__version__"]


def hello() -> str:
    """Return a greeting message."""
    return "Hello from axm!"
