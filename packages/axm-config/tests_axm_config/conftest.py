"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Redirect ``HOME`` so ``~/.axm`` resolves inside a tmp dir.

    ``axm_config.home.axm_home`` calls ``Path.home()`` live on every call
    (no module-level cache / lru_cache), so redirecting ``HOME`` is enough to
    keep every test hermetic — the real ``~/.axm`` is never read or written.
    Any leaked ``AXM_*`` provenance variable is also cleared so layer probes
    start from a clean slate regardless of test ordering.

    A *dedicated* tmp dir is used (not the function-scoped ``tmp_path``) so the
    ``~/.axm`` directory that ``axm_home()`` eagerly creates never pollutes a
    test's own ``tmp_path`` snapshot (e.g. no-mutation assertions).
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    for name in [key for key in os.environ if key.startswith("AXM_")]:
        monkeypatch.delenv(name, raising=False)
    yield home
