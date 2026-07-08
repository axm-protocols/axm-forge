"""Shared pytest fixtures for axm-edit tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _assume_tools_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to ruff available; degradation tests override explicitly."""
    monkeypatch.setattr("axm_edit.services.lint._has_ruff", True)


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with sample files.

    Layout::

        tmp_path/
        ├── src/
        │   └── foo.py   (5 lines)
        │   └── bar.py   (7 lines)
        └── README.md    (1 line)
    """
    src = tmp_path / "src"
    src.mkdir()

    foo_content = "import os\nimport sys\n\ndef hello():\n    return 42\n"
    bar_content = (
        "import foo\n\ndef greet():\n"
        "    return foo.hello()\n\ndef bye():\n    return 0\n"
    )
    (src / "foo.py").write_text(foo_content)
    (src / "bar.py").write_text(bar_content)
    (tmp_path / "README.md").write_text("# Test Project\n")

    return tmp_path
