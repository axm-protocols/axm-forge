"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def shared_helper_fixture(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n"
        "    return 42\n"
        "\n"
        "def moved_A():\n"
        "    return _shared()\n"
        "\n"
        "def remaining_B():\n"
        "    return _shared()\n"
    )
    target.write_text("")
    return tmp_path, source, target


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal `src/pkg/` workspace with an empty package."""
    root = tmp_path
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    return root
