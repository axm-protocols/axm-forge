from __future__ import annotations

from pathlib import Path

import pytest

from axm_config.home import resolve_safe

pytestmark = pytest.mark.integration


def test_in_repo_path_rejected(tmp_path: Path) -> None:
    """AC3: a path resolving inside a git repo / source checkout is refused."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    target = repo / "subdir" / "secrets.toml"

    with pytest.raises(ValueError):
        resolve_safe(target)


def test_out_of_repo_path_accepted(tmp_path: Path) -> None:
    """AC3: a path with no .git marker in its ancestry is resolved and returned."""
    target = tmp_path / "plain" / "config.toml"

    result = resolve_safe(target)

    assert result == target.resolve()
