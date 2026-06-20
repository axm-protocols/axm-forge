"""Unit tests for the Node tooling gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.tooling import check_eslint_config, check_test_script


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
