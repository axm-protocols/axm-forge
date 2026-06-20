"""Unit tests for the Node tooling gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.tooling import (
    check_engines_pinned,
    check_eslint_config,
    check_prettier_config,
    check_test_script,
)


def test_engines_pinned_passes(tmp_path: Path) -> None:
    """package.json with engines.node passes."""
    (tmp_path / "package.json").write_text(json.dumps({"engines": {"node": ">=20"}}))
    assert check_engines_pinned(tmp_path).passed is True


def test_engines_absent_fails(tmp_path: Path) -> None:
    """package.json without engines fails."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}))
    assert check_engines_pinned(tmp_path).passed is False


def test_prettier_config_file_passes(tmp_path: Path) -> None:
    """A .prettierrc file passes."""
    (tmp_path / ".prettierrc.json").write_text("{}")
    assert check_prettier_config(tmp_path).passed is True


def test_prettier_config_in_package_json_passes(tmp_path: Path) -> None:
    """A `prettier` key in package.json passes."""
    (tmp_path / "package.json").write_text(json.dumps({"prettier": {"semi": True}}))
    assert check_prettier_config(tmp_path).passed is True


def test_prettier_config_absent_fails(tmp_path: Path) -> None:
    """No Prettier config fails."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}))
    assert check_prettier_config(tmp_path).passed is False


def test_eslint_config_present_passes(tmp_path: Path) -> None:
    """A flat ESLint config passes."""
    (tmp_path / "eslint.config.js").write_text("export default [];")
    assert check_eslint_config(tmp_path).passed is True


def test_eslint_config_absent_fails(tmp_path: Path) -> None:
    """No ESLint config fails."""
    assert check_eslint_config(tmp_path).passed is False


def test_test_script_present_passes(tmp_path: Path) -> None:
    """A package.json with a test script passes."""
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}})
    )
    assert check_test_script(tmp_path).passed is True


def test_test_script_absent_fails(tmp_path: Path) -> None:
    """A package.json without a test script fails."""
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"lint": "eslint"}}))
    assert check_test_script(tmp_path).passed is False
