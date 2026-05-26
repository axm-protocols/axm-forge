"""Source fixture with classes, imports, and constants."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "data"
OTHER = "other"


class PackageCache:
    def __init__(self) -> None:
        self.items: list[str] = []


class TestFilesystemInvalidation:
    def test_something(self) -> None:
        p = FIXTURES / "x"
        assert p is not None


class TestEdgeCases:
    def test_edge(self) -> None:
        assert True


class KeepMe:
    def test_keep(self) -> None:
        assert OTHER == "other"
