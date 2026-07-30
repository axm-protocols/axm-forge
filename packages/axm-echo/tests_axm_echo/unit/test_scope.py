"""Unit tests for ``axm_echo.scope.load_scope`` (axm-config delegation).

The shared config access is mocked at the ``axm_echo.scope.axm_config.get``
seam (module-level ``import axm_config``), so these stay in-memory -- no real
filesystem, no ``~/.axm`` touched.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from axm_echo.scope import load_scope

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_load_scope_via_config(mocker: MockerFixture, tmp_path: Path) -> None:
    """AC1, AC2: roots resolved through axm_config.get, de-duplicated."""
    root_a = tmp_path / "ws_a"
    root_b = tmp_path / "ws_b"
    # A duplicate entry proves the de-dup post-processing still runs.
    mocker.patch(
        "axm_echo.scope.axm_config.get",
        return_value=[str(root_a), str(root_b), str(root_a)],
    )

    roots = load_scope()

    assert roots == [root_a.resolve(), root_b.resolve()]


def test_load_scope_absent_degrades_to_cwd(
    mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: an absent value degrades to [cwd], never raises."""
    mocker.patch("axm_echo.scope.axm_config.get", return_value=None)
    monkeypatch.chdir(tmp_path)

    roots = load_scope()

    assert roots == [tmp_path.resolve()]


def test_load_scope_config_error_degrades_to_cwd(
    mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: an axm_config error is swallowed and degrades to [cwd]."""
    mocker.patch("axm_echo.scope.axm_config.get", side_effect=RuntimeError("boom"))
    monkeypatch.chdir(tmp_path)

    roots = load_scope()

    assert roots == [tmp_path.resolve()]


def test_load_scope_env_string_is_pathsep_split(
    mocker: MockerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: the env layer returns a raw str -> split on os.pathsep, resolved."""
    root_a = tmp_path / "ws_a"
    root_b = tmp_path / "ws_b"
    raw = os.pathsep.join([str(root_a), str(root_b)])
    monkeypatch.setenv("AXM_ECHO_WORKSPACE_ROOTS", raw)
    mocker.patch("axm_echo.scope.axm_config.get", return_value=raw)

    roots = load_scope()

    assert roots == [root_a.resolve(), root_b.resolve()]


def test_load_scope_non_string_entries_skipped(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    """AC2: a list mixing a valid path with a non-string keeps only the path."""
    root_a = tmp_path / "ws_a"
    mocker.patch("axm_echo.scope.axm_config.get", return_value=[str(root_a), 42])

    roots = load_scope()

    assert roots == [root_a.resolve()]
