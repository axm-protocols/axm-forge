"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality._shared import get_pkg_prefixes


def test_get_pkg_prefixes_returns_src_dirs(tmp_path: Path) -> None:
    (tmp_path / "src" / "foo").mkdir(parents=True)
    (tmp_path / "src" / "bar").mkdir(parents=True)
    (tmp_path / "src" / ".hidden").mkdir(parents=True)
    assert get_pkg_prefixes(tmp_path) == {"foo", "bar"}
