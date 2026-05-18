"""Split from ``test_subprocess_runner_layouts.py``."""

from pathlib import Path


def test_find_venv_bounded_depth(tmp_path: Path) -> None:
    """Returns None when .venv is beyond _MAX_VENV_SEARCH_DEPTH levels up."""
    from axm_audit.core.runner import _MAX_VENV_SEARCH_DEPTH, find_venv

    # Create a .venv at the top, then nest deeper than the limit
    top = tmp_path / "top"
    top.mkdir()
    venv_bin = top / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    # Build a path _MAX_VENV_SEARCH_DEPTH levels deep (beyond the limit)
    deep = top
    for i in range(_MAX_VENV_SEARCH_DEPTH):
        deep = deep / f"level{i}"
        deep.mkdir()

    result = find_venv(deep)
    assert result is None
