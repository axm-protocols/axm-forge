"""Integration tests for strip_def_and_inject_import."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import strip_def_and_inject_import

pytestmark = pytest.mark.integration


def test_strip_def_and_inject_import_no_match_injects_nothing(tmp_path: Path) -> None:
    """When the name is absent, no def is stripped and no import is injected."""
    target = tmp_path / "mod.py"
    original = "def keep():\n    return 1\n"
    target.write_text(original)

    strip_def_and_inject_import(target, "absent", "tests.unit._helpers", tmp_path)

    body = target.read_text()
    assert "import" not in body
    assert "def keep" in body


def test_strip_def_and_inject_import_places_import_after_docstring(
    tmp_path: Path,
) -> None:
    """The injected import lands below a module docstring and existing imports."""
    target = tmp_path / "mod.py"
    target.write_text(
        '"""Module doc."""\n\n'
        "import os\n\n\n"
        "def moved():\n    return os.getcwd()\n\n\n"
        "def test_it():\n    assert moved()\n"
    )

    strip_def_and_inject_import(target, "moved", "tests.unit._helpers", tmp_path)

    lines = [ln for ln in target.read_text().splitlines() if ln.strip()]
    assert "def moved" not in target.read_text()
    import_line = "from tests.unit._helpers import moved"
    assert import_line in lines
    # Import sits after the docstring and the pre-existing `import os`.
    assert lines.index(import_line) > lines.index("import os")
    assert lines.index('"""Module doc."""') < lines.index(import_line)
