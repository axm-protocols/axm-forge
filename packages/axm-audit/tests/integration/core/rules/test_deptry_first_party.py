from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.dependencies import (
    detect_first_party_packages,
    run_deptry,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Unit tests for _detect_first_party_packages
# ---------------------------------------------------------------------------


def _setup_src_layout(root: Path) -> None:
    (root / "src" / "axm_foo").mkdir(parents=True)
    (root / "src" / "axm_foo" / "__init__.py").touch()


def _setup_namespace(root: Path) -> None:
    (root / "src" / "openleaf" / "performance").mkdir(parents=True)
    (root / "src" / "openleaf" / "performance" / "__init__.py").touch()


def _setup_no_src(root: Path) -> None:
    (root / "mypkg").mkdir()
    (root / "mypkg" / "__init__.py").touch()


def _setup_existing_config(root: Path) -> None:
    (root / "src" / "foo").mkdir(parents=True)
    (root / "src" / "foo" / "__init__.py").touch()
    (root / "pyproject.toml").write_text('[tool.deptry]\nknown_first_party = ["foo"]\n')


def _setup_flat_layout_with_excluded(root: Path) -> None:
    (root / "mypkg").mkdir()
    (root / "mypkg" / "__init__.py").touch()
    (root / "tests").mkdir()
    (root / "tests" / "__init__.py").touch()
    (root / "docs").mkdir()


def _setup_empty_src(root: Path) -> None:
    (root / "src").mkdir()


def _setup_src_only_pycache(root: Path) -> None:
    (root / "src" / "__pycache__").mkdir(parents=True)


def _setup_deep_namespace(root: Path) -> None:
    (root / "src" / "a" / "b" / "c").mkdir(parents=True)
    (root / "src" / "a" / "b" / "c" / "__init__.py").touch()


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param(_setup_src_layout, ["axm_foo"], id="src_layout"),
        pytest.param(_setup_namespace, ["openleaf"], id="namespace_package"),
        pytest.param(_setup_no_src, ["mypkg"], id="flat_no_src"),
        pytest.param(_setup_existing_config, [], id="skips_existing_config"),
        pytest.param(
            _setup_flat_layout_with_excluded,
            ["mypkg"],
            id="flat_layout_excludes_tests_docs",
        ),
        pytest.param(_setup_empty_src, [], id="empty_src"),
        pytest.param(_setup_src_only_pycache, [], id="src_only_pycache"),
        pytest.param(_setup_deep_namespace, ["a"], id="deep_namespace_top_level"),
    ],
)
def test_detect_first_party_packages(
    tmp_path: Path,
    setup: Callable[[Path], None],
    expected: list[str],
) -> None:
    """detect_first_party_packages handles src/flat/namespace/edge layouts."""
    setup(tmp_path)

    result = detect_first_party_packages(tmp_path)

    assert result == expected


def test_detect_first_party_multiple(tmp_path: Path) -> None:
    """Multiple packages under src/ are all detected."""
    for name in ("pkg_a", "pkg_b"):
        (tmp_path / "src" / name).mkdir(parents=True)
        (tmp_path / "src" / name / "__init__.py").touch()

    result = detect_first_party_packages(tmp_path)

    assert sorted(result) == ["pkg_a", "pkg_b"]


# ---------------------------------------------------------------------------
# Functional test
# ---------------------------------------------------------------------------


def test_deptry_namespace_no_false_positives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_deptry passes --known-first-party for namespace pkgs."""
    # Avoids DEP003 false positives for namespace packages.
    # Set up a namespace package structure
    (tmp_path / "src" / "openleaf" / "performance").mkdir(parents=True)
    (tmp_path / "src" / "openleaf" / "performance" / "__init__.py").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

    captured_cmds: list[list[str]] = []

    def fake_run_in_project(
        cmd: list[str],
        project_path: Path,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured_cmds.append(cmd)
        # Write empty JSON array to the tmp file (path is last arg of --json-output)
        json_idx = cmd.index("--json-output")
        json_path = Path(cmd[json_idx + 1])
        json_path.write_text("[]")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "axm_audit.core.rules.dependencies.run_in_project", fake_run_in_project
    )

    result = run_deptry(tmp_path)

    assert result == []
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "--known-first-party" in cmd
    kfp_idx = cmd.index("--known-first-party")
    assert cmd[kfp_idx + 1] == "openleaf"
