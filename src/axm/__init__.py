"""AXM CLI — Unified command-line interface for the AXM ecosystem."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("axm")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
