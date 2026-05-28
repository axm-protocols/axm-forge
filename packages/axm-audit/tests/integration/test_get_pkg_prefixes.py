"""Split from ``test_shared_helpers_io.py``."""

from collections.abc import Callable
from pathlib import Path

from axm_audit.core.rules.test_quality._shared import get_pkg_prefixes


def test_get_pkg_prefixes_returns_src_dirs(tmp_path: Path) -> None:
    (tmp_path / "src" / "foo").mkdir(parents=True)
    (tmp_path / "src" / "bar").mkdir(parents=True)
    (tmp_path / "src" / ".hidden").mkdir(parents=True)
    assert get_pkg_prefixes(tmp_path) == {"foo", "bar"}


def test_get_pkg_prefixes_reads_deptry_config(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: exposes the first-party package name (deptry-config friendly setup)."""
    pkg = make_pkg(
        pyproject_extras='[tool.deptry]\nknown_first_party = ["mypkg"]\n',
        pkg_name="mypkg",
    )
    assert get_pkg_prefixes(pkg) == {"mypkg"}


def test_get_pkg_prefixes_falls_back_to_src_scan(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: derives package name by scanning src/ when no deptry config present."""
    pkg = make_pkg(pkg_name="mypkg")
    assert get_pkg_prefixes(pkg) == {"mypkg"}
