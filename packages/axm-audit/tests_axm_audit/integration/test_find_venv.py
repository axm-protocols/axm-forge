"""Split from ``test_subprocess_runner_layouts.py``."""

from collections.abc import Callable
from pathlib import Path

import pytest


def _layout_local(tmp_path: Path) -> tuple[Path, Path]:
    """.venv directly in project_path."""
    (tmp_path / "pyproject.toml").touch()
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()
    return tmp_path, tmp_path / ".venv"


def _layout_workspace_root(tmp_path: Path) -> tuple[Path, Path]:
    """.venv at workspace root, subpackage as direct child (uv workspace siblings)."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "pyproject.toml").touch()
    venv_bin = workspace_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    subpackage = workspace_root / "my-lib"
    subpackage.mkdir()
    (subpackage / "pyproject.toml").touch()
    return subpackage, workspace_root / ".venv"


def _layout_packages_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Workspace with intermediate packages/ dir lacking pyproject.toml."""
    # workspace/
    # ├── .venv/bin/python
    # ├── pyproject.toml
    # └── packages/          ← no pyproject.toml
    #     └── my-pkg/
    #         └── pyproject.toml
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").touch()
    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    packages = workspace / "packages"
    packages.mkdir()  # no pyproject.toml

    pkg = packages / "my-pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").touch()
    return pkg, workspace / ".venv"


def _layout_flat_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Flat workspace layout: subpackage as direct sibling under workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").touch()
    venv_bin = workspace / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    pkg = workspace / "my-lib"
    pkg.mkdir()
    (pkg / "pyproject.toml").touch()
    return pkg, workspace / ".venv"


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(_layout_local, id="local_venv"),
        pytest.param(_layout_workspace_root, id="workspace_root_venv"),
        pytest.param(_layout_packages_dir, id="packages_layout"),
        pytest.param(_layout_flat_workspace, id="flat_workspace"),
    ],
)
def test_find_venv_locates_venv(
    build: Callable[[Path], tuple[Path, Path]],
    tmp_path: Path,
) -> None:
    """find_venv walks up to the first .venv across supported workspace layouts."""
    from axm_audit.core.runner import find_venv

    target, expected = build(tmp_path)
    assert find_venv(target) == expected


def test_returns_none_when_no_venv(tmp_path: Path) -> None:
    """Returns None when no .venv exists anywhere in the project tree."""
    from axm_audit.core.runner import find_venv

    (tmp_path / "pyproject.toml").touch()
    result = find_venv(tmp_path)
    assert result is None
