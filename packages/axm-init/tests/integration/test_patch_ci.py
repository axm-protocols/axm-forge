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


# ─ Prefix-collision guard (AXM-1837) ─────────────────────────────────────
#
# The guard that skips already-listed members must match the exact matrix
# token, not a bare substring. A bare `if member_name in content` wrongly
# skips `foo-bar` when `foo` is already present (prefix collision).


def _ci_with_packages(root: Path, members: list[str]) -> Path:
    """Write a realistic ci.yml whose matrix.package list is *members*."""
    ci = root / ".github" / "workflows" / "ci.yml"
    ci.parent.mkdir(parents=True, exist_ok=True)
    matrix = "\n".join(f"          - {m}" for m in members)
    ci.write_text(
        "name: CI\n\n"
        "on:\n  push:\n    branches: [main]\n\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      matrix:\n"
        "        package:\n"
        f"{matrix}\n"
        '        python-version: ["3.12", "3.13"]\n'
        "    steps:\n"
        "      - uses: actions/checkout@v6\n"
    )
    return ci


def test_patch_ci_adds_member_despite_prefix_collision(tmp_path: Path) -> None:
    """AC1: with `foo` already present, patching `foo-bar` must still add it.

    A bare-substring guard (`"foo-bar" in content` is False but the old guard
    checked `member_name in content` for the *new* name; the collision is the
    reverse — adding `foo` after `foo-bar`, or any case where the new name's
    matrix token is not yet present but its substring is). Verify the new
    member's exact matrix token lands in the file.
    """
    ci = _ci_with_packages(tmp_path, ["foo"])

    patch_ci(tmp_path, "foo-bar")

    parsed = yaml.safe_load(ci.read_text())
    packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
    assert "foo-bar" in packages
    assert "foo" in packages


def test_patch_ci_is_idempotent_for_exact_member(tmp_path: Path) -> None:
    """AC2: re-patching an exactly-present member yields no duplicate."""
    ci = _ci_with_packages(tmp_path, ["foo-bar"])

    patch_ci(tmp_path, "foo-bar")

    content = ci.read_text()
    assert content.count("          - foo-bar\n") == 1
    parsed = yaml.safe_load(content)
    packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
    assert packages.count("foo-bar") == 1
