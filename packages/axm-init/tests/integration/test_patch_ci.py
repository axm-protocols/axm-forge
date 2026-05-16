"""Tests for adapters.workspace_patcher.patch_ci — matrix insertion + YAML safety."""

from pathlib import Path

import pytest
import yaml

from axm_init.adapters.workspace_patcher import patch_ci
from tests.integration._helpers import _make_realistic_ci


class TestCiMatrixGetsMember:
    """patch_ci adds the new member to the CI build matrix."""

    def test_adds_package_to_matrix(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert "- my-lib" in content
        assert "- existing-pkg" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_ci(workspace_root, "my-lib")
        content1 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        patch_ci(workspace_root, "my-lib")
        content2 = (workspace_root / ".github" / "workflows" / "ci.yml").read_text()
        assert content1 == content2

    def test_missing_ci_workflow_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_ci(tmp_path, "my-lib")


# ─ YAML safety regression tests ──────────────────────────────────────────
#
# Regression coverage for a bug where `_find_yaml_list_range` captured
# `- ` items past the target list (e.g. items inside `steps:`), causing
# patch_ci to insert the new entry inside the wrong block and produce
# unparseable YAML.


def test_patch_ci_keeps_yaml_parseable(tmp_path: Path) -> None:
    """patch_ci produces a dict with the expected CI job structure."""
    ci = _make_realistic_ci(tmp_path)
    patch_ci(tmp_path, "my-lib")
    parsed = yaml.safe_load(ci.read_text())
    assert isinstance(parsed, dict)
    assert "jobs" in parsed
    assert "test" in parsed["jobs"]


def test_patch_ci_inserts_into_matrix_not_steps(tmp_path: Path) -> None:
    """Inserted entry ends up in ``matrix.package``, never in ``steps``."""
    ci = _make_realistic_ci(tmp_path)
    patch_ci(tmp_path, "my-lib")
    parsed = yaml.safe_load(ci.read_text())
    matrix_packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
    assert "my-lib" in matrix_packages
    assert matrix_packages == ["existing-pkg", "another-pkg", "my-lib"]
    # Steps must remain untouched — no "my-lib" string anywhere in them.
    steps = parsed["jobs"]["test"]["steps"]
    for step in steps:
        assert "my-lib" not in str(step)


@pytest.mark.parametrize("member", ["lib-one", "lib-two", "lib-three"])
def test_patch_ci_repeated_calls_keep_yaml_valid(tmp_path: Path, member: str) -> None:
    """Sequential patches for multiple members stay parseable."""
    _make_realistic_ci(tmp_path)
    for m in ["lib-one", "lib-two", "lib-three"]:
        patch_ci(tmp_path, m)
        if m == member:
            break
    parsed = yaml.safe_load((tmp_path / ".github" / "workflows" / "ci.yml").read_text())
    packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
    assert member in packages
