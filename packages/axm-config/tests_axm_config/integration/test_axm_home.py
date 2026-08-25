"""Split from ``test_home.py``."""

import stat
from pathlib import Path

import pytest

from axm_config import axm_home


def test_axm_home_creates_0700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC2: axm_home() creates ~/.axm with mode 0700."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    home = axm_home()

    assert home == (tmp_path / ".axm").resolve()
    assert home.is_dir()
    assert stat.S_IMODE(home.stat().st_mode) == 0o700


def test_axm_home_idempotent_tightens_perms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: a pre-existing dir with looser perms is tightened to 0700, idempotently."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    loose = tmp_path / ".axm"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)

    first = axm_home()
    second = axm_home()

    assert first == second
    assert stat.S_IMODE(second.stat().st_mode) == 0o700
