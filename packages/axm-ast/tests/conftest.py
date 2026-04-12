"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_data() -> dict[str, str]:
    """Provide sample test data."""
    return {"key": "value"}


@pytest.fixture()
def rich_pkg(tmp_path: Path) -> str:
    """Create a package with functions, classes, variables, and modules."""
    pkg = tmp_path / "richpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Rich demo package."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        'VERSION = "1.0.0"\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello to someone.\n\n'
        "    Args:\n"
        "        name: The person to greet.\n\n"
        "    Returns:\n"
        "        A greeting string.\n"
        '    """\n'
        '    return f"Hello {name}"\n\n\n'
        "class Greeter:\n"
        '    """A greeting helper class."""\n\n'
        '    def __init__(self, prefix: str = "Hi") -> None:\n'
        "        self.prefix = prefix\n\n"
        "    def say_hello(self, name: str) -> str:\n"
        '        """Greet someone with a prefix.\n\n'
        "        Args:\n"
        "            name: The person to greet.\n\n"
        "        Returns:\n"
        "            A greeting string.\n"
        '        """\n'
        '        return f"{self.prefix} {name}"\n'
    )
    (pkg / "rich_mod.py").write_text(
        '"""A rich module with several symbols."""\n\n'
        "MAGIC = 42\n\n\n"
        "def helper() -> int:\n"
        '    """Return a magic number."""\n'
        "    return MAGIC\n\n\n"
        "class Widget:\n"
        '    """A widget."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run the widget."""\n'
    )
    return str(pkg)
