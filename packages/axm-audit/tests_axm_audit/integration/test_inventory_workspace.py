"""Inventory follows uv's actual workspace lock selection."""

import hashlib
from pathlib import Path

import pytest

from axm_audit.core.rules.dependency_inventory import export_inventory

pytestmark = pytest.mark.integration


def _lock(root: Path, name: str, source: str, dependency: str) -> None:
    (root / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = ">=3.12"\n'
        f'[[package]]\nname = "{name}"\nversion = "1"\n'
        f'source = {{ virtual = "{source}" }}\n'
        f'dependencies = [{{ name = "{dependency}" }}]\n'
        f'[[package]]\nname = "{dependency}"\nversion = "1"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "packages/member").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/member"]\n'
        'exclude = ["packages/excluded", "packages/nested"]\n'
    )
    (tmp_path / "packages/member/pyproject.toml").write_text(
        '[project]\nname = "member"\nversion = "1"\n'
    )
    _lock(tmp_path, "member", "packages/member", "parent-dependency")
    return tmp_path


@pytest.mark.parametrize("child_name", ["foreign", "member"])
def test_workspace_member_uses_parent_lock_despite_child_lock(
    workspace: Path, child_name: str
) -> None:
    child = workspace / "packages/member"
    _lock(child, child_name, ".", "child-dependency")
    inventory, evidence = export_inventory(child)
    assert inventory.strip() == "parent-dependency==1"
    assert evidence["lock_path"] == str(workspace / "uv.lock")
    assert (
        evidence["lock_sha256"]
        == hashlib.sha256((workspace / "uv.lock").read_bytes()).hexdigest()
    )


def test_missing_workspace_lock_does_not_fall_back_to_child(workspace: Path) -> None:
    child = workspace / "packages/member"
    _lock(child, "member", ".", "child-dependency")
    (workspace / "uv.lock").unlink()
    with pytest.raises(RuntimeError, match="missing from workspace root"):
        export_inventory(child)


def test_excluded_project_uses_own_lock(workspace: Path) -> None:
    child = workspace / "packages/excluded"
    child.mkdir()
    (child / "pyproject.toml").write_text(
        '[project]\nname = "excluded"\nversion = "1"\n'
    )
    _lock(child, "excluded", ".", "excluded-dependency")
    inventory, evidence = export_inventory(child)
    assert inventory.strip() == "excluded-dependency==1"
    assert evidence["lock_path"] == str(child / "uv.lock")


def test_nested_workspace_uses_nested_lock(workspace: Path) -> None:
    nested = workspace / "packages/nested"
    member = nested / "member"
    member.mkdir(parents=True)
    (nested / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["member"]\n'
    )
    (member / "pyproject.toml").write_text(
        '[project]\nname = "nested-member"\nversion = "1"\n'
    )
    _lock(nested, "nested-member", "member", "nested-dependency")
    inventory, evidence = export_inventory(member)
    assert inventory.strip() == "nested-dependency==1"
    assert evidence["lock_path"] == str(nested / "uv.lock")
