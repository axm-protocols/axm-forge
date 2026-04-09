from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.dependencies import (
    _detect_first_party_packages,
    _run_deptry,
)

# ---------------------------------------------------------------------------
# Unit tests for _detect_first_party_packages
# ---------------------------------------------------------------------------


def test_detect_first_party_src_layout(tmp_path: Path) -> None:
    """Standard src layout with __init__.py is detected."""
    (tmp_path / "src" / "axm_foo").mkdir(parents=True)
    (tmp_path / "src" / "axm_foo" / "__init__.py").touch()

    result = _detect_first_party_packages(tmp_path)

    assert result == ["axm_foo"]


def test_detect_first_party_namespace(tmp_path: Path) -> None:
    """Namespace package (no __init__.py at top level) is detected."""
    (tmp_path / "src" / "openleaf" / "performance").mkdir(parents=True)
    (tmp_path / "src" / "openleaf" / "performance" / "__init__.py").touch()
    # No src/openleaf/__init__.py — this is a namespace package

    result = _detect_first_party_packages(tmp_path)

    assert result == ["openleaf"]


def test_detect_first_party_multiple(tmp_path: Path) -> None:
    """Multiple packages under src/ are all detected."""
    for name in ("pkg_a", "pkg_b"):
        (tmp_path / "src" / name).mkdir(parents=True)
        (tmp_path / "src" / name / "__init__.py").touch()

    result = _detect_first_party_packages(tmp_path)

    assert sorted(result) == ["pkg_a", "pkg_b"]


def test_detect_first_party_no_src(tmp_path: Path) -> None:
    """Flat layout (no src/) falls back to root scan."""
    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "__init__.py").touch()

    result = _detect_first_party_packages(tmp_path)

    assert result == ["mypkg"]


def test_detect_skips_existing_config(tmp_path: Path) -> None:
    """Skip auto-detection when pyproject.toml already configures known_first_party."""
    (tmp_path / "src" / "foo").mkdir(parents=True)
    (tmp_path / "src" / "foo" / "__init__.py").touch()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.deptry]\nknown_first_party = ["foo"]\n'
    )

    result = _detect_first_party_packages(tmp_path)

    assert result == []


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

    result = _run_deptry(tmp_path)

    assert result == []
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "--known-first-party" in cmd
    kfp_idx = cmd.index("--known-first-party")
    assert cmd[kfp_idx + 1] == "openleaf"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_detect_no_src_directory_flat_layout(tmp_path: Path) -> None:
    """Project uses flat layout — falls back to root scan."""
    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "__init__.py").touch()
    # Excluded directories should be ignored
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").touch()
    (tmp_path / "docs").mkdir()

    result = _detect_first_party_packages(tmp_path)

    assert result == ["mypkg"]


def test_detect_empty_src(tmp_path: Path) -> None:
    """Empty src/ directory returns empty list."""
    (tmp_path / "src").mkdir()

    result = _detect_first_party_packages(tmp_path)

    assert result == []


def test_detect_src_with_only_pycache(tmp_path: Path) -> None:
    """src/ with only __pycache__ is filtered out."""
    (tmp_path / "src" / "__pycache__").mkdir(parents=True)

    result = _detect_first_party_packages(tmp_path)

    assert result == []


def test_detect_multiple_namespace_levels(tmp_path: Path) -> None:
    """Deep namespace (src/a/b/c/__init__.py) returns top-level only."""
    (tmp_path / "src" / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "src" / "a" / "b" / "c" / "__init__.py").touch()

    result = _detect_first_party_packages(tmp_path)

    assert result == ["a"]
