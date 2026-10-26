from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot import Member, resolve_workspace

pytestmark = pytest.mark.integration


def _member(root: Path) -> Member:
    return Member(name=root.name, path=root)


def _package(src: Path, name: str, *, init: bool = True) -> Path:
    directory = src / name
    directory.mkdir(parents=True)
    if init:
        (directory / "__init__.py").write_text("", encoding="utf-8")
    return directory


def test_source_dirs_lists_packages_sorted(tmp_path: Path) -> None:
    """Each ``src/<module>/`` holding ``__init__.py`` is returned, sorted."""
    src = tmp_path / "src"
    zeta = _package(src, "zeta")
    alpha = _package(src, "alpha")

    assert _member(tmp_path).source_dirs == (alpha, zeta)


def test_source_dirs_skips_dirs_without_init(tmp_path: Path) -> None:
    """A namespace-style directory without ``__init__.py`` is not a package."""
    src = tmp_path / "src"
    kept = _package(src, "kept")
    _package(src, "namespace", init=False)

    assert _member(tmp_path).source_dirs == (kept,)


def test_source_dirs_ignores_plain_files(tmp_path: Path) -> None:
    """Single-file modules and stray files under ``src/`` are ignored."""
    src = tmp_path / "src"
    kept = _package(src, "kept")
    (src / "single.py").write_text("", encoding="utf-8")
    (src / "__init__.py").write_text("", encoding="utf-8")

    assert _member(tmp_path).source_dirs == (kept,)


def test_source_dirs_empty_without_src(tmp_path: Path) -> None:
    """A member with no ``src/`` directory has no source dirs."""
    assert _member(tmp_path).source_dirs == ()


def test_source_dirs_empty_when_src_is_a_file(tmp_path: Path) -> None:
    """``src`` being a regular file is treated as absent."""
    (tmp_path / "src").write_text("", encoding="utf-8")

    assert _member(tmp_path).source_dirs == ()


def test_source_dirs_of_resolved_member(tmp_path: Path) -> None:
    """Works on resolver-produced members (absolute, resolved paths)."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n', encoding="utf-8"
    )
    member_root = tmp_path / "packages" / "alpha"
    member_root.mkdir(parents=True)
    (member_root / "pyproject.toml").write_text("", encoding="utf-8")
    package = _package(member_root / "src", "alpha")

    workspace = resolve_workspace(tmp_path)

    assert workspace is not None
    assert workspace.members[0].source_dirs == (package.resolve(),)
