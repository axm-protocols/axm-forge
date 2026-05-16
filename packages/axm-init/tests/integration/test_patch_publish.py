"""Registering a new member patches CI workflows (build matrix + publish tags)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from axm_init.adapters.workspace_patcher import patch_publish
from tests.integration._helpers import _make_realistic_publish, _publish_with


class TestPublishWorkflowGetsMemberTag:
    """patch_publish adds member-prefixed tag pattern."""

    def test_adds_tag_pattern(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "workflows" / "publish.yml").read_text()
        assert "my-lib/v*" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_publish(workspace_root, "my-lib")
        content1 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        patch_publish(workspace_root, "my-lib")
        content2 = (
            workspace_root / ".github" / "workflows" / "publish.yml"
        ).read_text()
        assert content1 == content2

    def test_missing_publish_workflow_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_publish(tmp_path, "my-lib")

    def test_adds_tags_section_when_absent(self, tmp_path: Path) -> None:
        """patch_publish adds tags section if missing from existing publish.yml."""
        publish_file = tmp_path / ".github" / "workflows" / "publish.yml"
        publish_file.parent.mkdir(parents=True, exist_ok=True)
        publish_file.write_text("name: Publish\n\njobs:\n  build:\n")

        patch_publish(tmp_path, "my-lib")

        content = publish_file.read_text()
        assert "tags:" in content
        assert "my-lib/v*" in content


# ─ YAML edge cases (covered via public patch_publish) ────────────────────────────


def test_marker_present_but_no_list_items(tmp_path: Path) -> None:
    """`tags:` marker present but no `- ` items → original is preserved."""
    body = (
        "name: Publish\n\n"
        "on:\n  push:\n    tags:\n      nothing_here: true\n\n"
        "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v6\n"
    )
    publish_yml = _publish_with(tmp_path, body)
    patch_publish(tmp_path, "my-lib")
    content = publish_yml.read_text()
    assert "nothing_here: true" in content


def test_no_tags_marker_creates_section(tmp_path: Path) -> None:
    """No `tags:` in publish.yml → push.tags trigger is created."""
    body = (
        "name: Publish\n\n"
        "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v6\n"
    )
    publish_yml = _publish_with(tmp_path, body)
    patch_publish(tmp_path, "my-lib")
    content = publish_yml.read_text()
    assert '"my-lib/v*"' in content
    assert "push:" in content
    assert "tags:" in content


def test_existing_tags_with_default_indent(tmp_path: Path) -> None:
    """Existing tags list → indent is detected from the last item."""
    body = (
        "name: Publish\n\n"
        "on:\n  push:\n    tags:\n"
        '      - "existing/v*"\n\n'
        "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v6\n"
    )
    publish_yml = _publish_with(tmp_path, body)
    patch_publish(tmp_path, "my-lib")
    content = publish_yml.read_text()
    assert '      - "existing/v*"' in content
    assert '      - "my-lib/v*"' in content


# ─ YAML safety regression tests ──────────────────────────────────────────


def test_patch_publish_keeps_yaml_parseable(tmp_path: Path) -> None:
    """patch_publish produces a dict with tag-push trigger + publish job."""
    publish = _make_realistic_publish(tmp_path)
    patch_publish(tmp_path, "my-lib")
    parsed = yaml.safe_load(publish.read_text())
    assert isinstance(parsed, dict)
    assert True in parsed and "push" in parsed[True]
    assert "jobs" in parsed and "publish" in parsed["jobs"]


def test_patch_publish_inserts_into_tags_not_steps(tmp_path: Path) -> None:
    """Tag pattern goes into ``on.push.tags``, never into ``steps``."""
    publish = _make_realistic_publish(tmp_path)
    patch_publish(tmp_path, "my-lib")
    parsed = yaml.safe_load(publish.read_text())
    # YAML 1.1: bare `on:` parses as the boolean key True, not "on".
    tags = parsed[True]["push"]["tags"]
    assert "my-lib/v*" in tags
    steps = parsed["jobs"]["publish"]["steps"]
    for step in steps:
        assert "my-lib/v*" not in str(step)
