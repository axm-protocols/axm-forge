"""Unit tests for the Node tsconfig gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.tsconfig import (
    check_tsconfig_exists,
    check_tsconfig_strict,
)


def test_missing_tsconfig_fails_exists(tmp_path: Path) -> None:
    """No tsconfig.json fails the existence check."""
    assert check_tsconfig_exists(tmp_path).passed is False


def test_present_tsconfig_passes_exists(tmp_path: Path) -> None:
    """A parsable tsconfig.json passes the existence check."""
    (tmp_path / "tsconfig.json").write_text("{}")
    assert check_tsconfig_exists(tmp_path).passed is True


def test_strict_true_passes(tmp_path: Path) -> None:
    """strict: true passes the strict check."""
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True}})
    )
    assert check_tsconfig_strict(tmp_path).passed is True


def test_strict_false_fails(tmp_path: Path) -> None:
    """strict: false (or absent) fails the strict check."""
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": False}})
    )
    assert check_tsconfig_strict(tmp_path).passed is False
