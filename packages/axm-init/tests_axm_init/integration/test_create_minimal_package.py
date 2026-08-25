"""Split from ``test_package_name_reservation_flow.py``."""

from pathlib import Path


def test_create_minimal_package(tmp_path: Path) -> None:
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
