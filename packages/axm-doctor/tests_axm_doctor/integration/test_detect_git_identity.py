"""Integration: git-identity detection resolves a real ``axm_config`` store."""

from __future__ import annotations

from pathlib import Path

import axm_config
import pytest

from axm_doctor.detect import detect_git_identity


@pytest.mark.integration
def test_store_default_makes_identity_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC2, AC6: a real ``[git].default`` written to the store -> configured.

    The store presence alone decides the verdict — the git subprocess is never
    needed and the identity value is never read by the detector.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # ``[git].default`` is a profile NAME (a scalar), per axm-git's identity
    # store contract — not a nested table. axm-config stores a nested dict as a
    # child namespace, so a dict value would be unreadable as a key; the real
    # production shape is a truthy string.
    axm_config.set_("git", "default", "gabriel")

    status = detect_git_identity()

    assert status.state == "configured"
