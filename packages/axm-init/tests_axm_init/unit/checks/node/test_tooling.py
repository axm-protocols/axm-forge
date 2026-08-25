"""Unit tests for the Node tooling gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.tooling import (
    check_commitlint,
    check_engines_pinned,
    check_eslint_config,
    check_git_hooks,
    check_prettier_config,
    check_test_script,
)


def test_git_hooks_husky_dir_passes(tmp_path: Path) -> None:
    """A .husky directory satisfies the git-hooks check."""
    (tmp_path / ".husky").mkdir()
    assert check_git_hooks(tmp_path).passed is True


def test_git_hooks_devdep_passes(tmp_path: Path) -> None:
    """A husky devDependency satisfies the git-hooks check."""
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"husky": "^9"}})
    )
    assert check_git_hooks(tmp_path).passed is True


def test_git_hooks_absent_fails(tmp_path: Path) -> None:
    """No git-hook manager fails."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}))
    assert check_git_hooks(tmp_path).passed is False


def test_commitlint_config_passes(tmp_path: Path) -> None:
    """A commitlint.config.js passes."""
    (tmp_path / "commitlint.config.js").write_text("export default {};")
    assert check_commitlint(tmp_path).passed is True


def test_commitlint_absent_fails(tmp_path: Path) -> None:
    """No commitlint config fails."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}))
    assert check_commitlint(tmp_path).passed is False


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
