"""Test package version and public API."""

from __future__ import annotations


class TestVersionUnit:
    def test_version_importable(self) -> None:
        from axm_smelt import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_public_api_exports(self) -> None:
        import axm_smelt

        assert hasattr(axm_smelt, "__all__")
        assert "__version__" in axm_smelt.__all__
