"""Tests for adapters.workspace_patcher.patch_release — detect block + YAML safety."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from axm_init.adapters.workspace_patcher import patch_release
from tests_axm_init.integration._helpers import _make_realistic_release

INLINE_TAGS_RELEASE = (
    "name: Release\n\n"
    "on:\n"
    "  push:\n"
    '    tags: ["v*"]\n\n'
    "jobs:\n"
    "  release:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - name: Detect package\n"
    "        run: |\n"
    "          TAG=${GITHUB_REF#refs/tags/}\n"
    '          if [[ "$TAG" == v* ]]; then\n'
    '            echo "package=root" >> "$GITHUB_OUTPUT"\n'
    '          elif [[ "$TAG" == axm-foo/* ]]; then\n'
    '            echo "package=axm-foo" >> "$GITHUB_OUTPUT"\n'
    '            echo "package-dir=packages/axm-foo" >> "$GITHUB_OUTPUT"\n'
    "          else\n"
    '            echo "unknown tag"\n'
    "          fi\n"
    "      - name: Publish\n"
    "        run: echo publish\n"
)


@pytest.fixture()
def release_root(tmp_path: Path) -> Path:
    """Workspace root with a release.yml."""
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "release.yml").write_text(
        "name: Release\n\non:\n  push:\n    tags:\n"
        '      - "v*"\n\njobs:\n  release:\n'
        "    steps:\n"
        "      - name: detect\n"
        "        run: |\n"
        "          TAG=${GITHUB_REF#refs/tags/}\n"
        '          if [[ "$TAG" == v* ]]; then\n'
        '            echo "package=root" >> "$GITHUB_OUTPUT"\n'
        "          else\n"
        '            echo "unknown tag"\n'
        "          fi\n"
    )
    return tmp_path


def test_adds_tag_and_detect_block(release_root: Path) -> None:
    """patch_release adds tag pattern and detect elif block."""
    patch_release(release_root, "my-lib")
    content = (release_root / ".github" / "workflows" / "release.yml").read_text()
    assert "my-lib/v*" in content
    assert 'elif [[ "$TAG" == my-lib/* ]]' in content
    assert "package=my-lib" in content
    assert "package-dir=packages/my-lib" in content


def test_idempotent(release_root: Path) -> None:
    """Calling patch_release twice produces same content."""
    patch_release(release_root, "my-lib")
    content1 = (release_root / ".github" / "workflows" / "release.yml").read_text()
    patch_release(release_root, "my-lib")
    content2 = (release_root / ".github" / "workflows" / "release.yml").read_text()
    assert content1 == content2


def test_missing_release_yml_raises(tmp_path: Path) -> None:
    """Missing release.yml raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        patch_release(tmp_path, "my-lib")


def test_no_else_block(tmp_path: Path) -> None:
    """release.yml without 'else' only adds tag pattern."""
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "release.yml").write_text(
        "name: Release\n\non:\n  push:\n    tags:\n"
        '      - "v*"\n\njobs:\n  release:\n'
        "    steps:\n      - checkout\n"
    )
    patch_release(tmp_path, "my-lib")
    content = (ci_dir / "release.yml").read_text()
    assert "my-lib/v*" in content
    assert "elif" not in content


def test_no_tags_section(tmp_path: Path) -> None:
    """release.yml without 'tags:' section skips tag insertion."""
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "release.yml").write_text(
        "name: Release\n\njobs:\n  release:\n"
        "    steps:\n"
        "          else\n"
        "            echo done\n"
    )
    patch_release(tmp_path, "my-lib")
    content = (ci_dir / "release.yml").read_text()
    assert "elif" in content


def test_patch_release_keeps_yaml_parseable(tmp_path: Path) -> None:
    """patch_release produces a dict with tag-push trigger + release job."""
    release = _make_realistic_release(tmp_path)
    patch_release(tmp_path, "my-lib")
    parsed = yaml.safe_load(release.read_text())
    assert isinstance(parsed, dict)
    assert True in parsed and "push" in parsed[True]
    assert "jobs" in parsed and "release" in parsed["jobs"]


def test_patch_release_inserts_into_tags_not_steps(tmp_path: Path) -> None:
    """Release tag goes into ``on.push.tags``, not between ``steps``."""
    release = _make_realistic_release(tmp_path)
    patch_release(tmp_path, "my-lib")
    parsed = yaml.safe_load(release.read_text())
    # YAML 1.1: bare `on:` parses as the boolean key True, not "on".
    tags = parsed[True]["push"]["tags"]
    assert "my-lib/v*" in tags
    steps = parsed["jobs"]["release"]["steps"]
    for step in steps:
        # The tag pattern must not leak into any step.
        assert '"my-lib/v*"' not in str(step)


@pytest.fixture()
def inline_tags_release_root(tmp_path: Path) -> Path:
    """Workspace root containing the local inline-tags workflow fixture."""
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "release.yml").write_text(INLINE_TAGS_RELEASE)
    return tmp_path


def _steps_block(content: str) -> str:
    """Return the exact workflow suffix beginning at the job's steps key."""
    return content[content.index("    steps:\n") :]


@pytest.mark.integration
def test_inline_tags_trigger_contains_new_pattern(
    inline_tags_release_root: Path,
) -> None:
    """AC1: inline ``tags`` gains the new pattern without touching job steps."""
    release = inline_tags_release_root / ".github" / "workflows" / "release.yml"
    steps_before = _steps_block(release.read_text())

    patch_release(inline_tags_release_root, "axm-foo")

    content = release.read_text()
    assert '    tags: ["v*", "axm-foo-v*"]' in content.splitlines()
    assert _steps_block(content) == steps_before


@pytest.mark.integration
def test_inline_tags_patch_preserves_steps_bytes(
    inline_tags_release_root: Path,
) -> None:
    """AC2: the complete ``steps`` block remains byte-for-byte identical."""
    release = inline_tags_release_root / ".github" / "workflows" / "release.yml"
    steps_before = _steps_block(release.read_text())

    patch_release(inline_tags_release_root, "axm-foo")

    assert _steps_block(release.read_text()) == steps_before


@pytest.mark.integration
def test_inline_tags_patch_keeps_real_yaml_steps(
    inline_tags_release_root: Path,
) -> None:
    """AC3: parsed steps remain mappings carrying ``uses`` or ``run``."""
    release = inline_tags_release_root / ".github" / "workflows" / "release.yml"
    steps_before = _steps_block(release.read_text())

    patch_release(inline_tags_release_root, "axm-foo")

    content = release.read_text()
    parsed = yaml.safe_load(content)
    steps = parsed["jobs"]["release"]["steps"]
    assert all(
        isinstance(step, dict) and ("uses" in step or "run" in step) for step in steps
    )
    assert _steps_block(content) == steps_before
