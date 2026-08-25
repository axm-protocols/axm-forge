"""Integration tests for extract_shared_helpers + extract_shared_helpers_once."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import (
    extract_shared_helpers,
    extract_shared_helpers_once,
)

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


def test_extract_shared_helpers_dedups_ambiguous_across_iterations(
    tmp_path: Path,
) -> None:
    """The fixed-point loop reports each ambiguous *fixture* exactly once.

    ``extract_shared_helpers`` runs ``_once`` repeatedly; a permanently
    ambiguous fixture re-surfaces on every pass (proven by calling ``_once``
    directly), but the iterating entry point must collapse it to a single
    message in the returned list.
    """
    fixture_a = (
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def client():\n    return {'mode': 'a'}\n\n\n"
    )
    fixture_b = (
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def client():\n    return {'mode': 'b', 'extra': 1}\n\n\n"
    )
    project, _ = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": (
                fixture_a + "def test_a(client):\n    assert client['mode'] == 'a'\n"
            ),
            "tests/integration/test_b.py": (
                fixture_b + "def test_b(client):\n    assert client['mode'] == 'b'\n"
            ),
        },
    )

    # A single pass already reports the divergent fixture as ambiguous.
    once_msgs = extract_shared_helpers_once(project)
    assert any("ambiguous fixture `client`" in m for m in once_msgs)

    # The fixed-point loop must not duplicate it across its iterations.
    msgs = extract_shared_helpers(project)
    ambiguous = [m for m in msgs if "ambiguous fixture `client`" in m]
    assert len(ambiguous) == 1
