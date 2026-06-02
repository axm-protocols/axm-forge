"""Integration tests for the extract_shared_helpers fixed-point loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import extract_shared_helpers

pytestmark = pytest.mark.integration


def _make_tier(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """Write *files* (relative to the project root) and return (project, tier)."""
    project = tmp_path / "proj"
    tier_dir = project / "tests" / "integration"
    tier_dir.mkdir(parents=True)
    for rel, content in files.items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return project, tier_dir


def test_extract_shared_helpers_promotes_then_reaches_fixed_point(
    tmp_path: Path,
) -> None:
    """The loop applies an extraction, then converges with no further changes."""
    helper = "def _shared(x):\n    return x - 1\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": helper
            + "def test_a():\n    assert _shared(2) == 1\n",
            "tests/integration/test_b.py": helper
            + "def test_b():\n    assert _shared(3) == 2\n",
        },
    )

    msgs = extract_shared_helpers(project)

    assert "def _shared" in (tier / "_helpers.py").read_text()
    # Exactly one extraction message — the second pass finds nothing to move.
    assert sum("extracted helper `_shared`" in m for m in msgs) == 1
