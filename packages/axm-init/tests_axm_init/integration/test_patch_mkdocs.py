"""Split from ``test_register_member_in_workspace_root.py``."""

from pathlib import Path
from typing import Any

import yaml

from axm_init.adapters.workspace_patcher import patch_mkdocs


class TestMkdocsGetsMemberInclude:
    """patch_mkdocs adds nav include for the new member's docs."""

    def test_adds_include(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")

        content = (workspace_root / "mkdocs.yml").read_text()
        assert "!include ./packages/my-lib/mkdocs.yml" in content
        assert "my-lib:" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_mkdocs(workspace_root, "my-lib")
        content1 = (workspace_root / "mkdocs.yml").read_text()
        patch_mkdocs(workspace_root, "my-lib")
        content2 = (workspace_root / "mkdocs.yml").read_text()
        assert content1 == content2


def _nav_after_patch(root: Path, body: str) -> dict[str, Any]:
    (root / "mkdocs.yml").write_text(body)
    assert patch_mkdocs(root, "my-lib") is True
    config: dict[str, Any] = yaml.safe_load((root / "mkdocs.yml").read_text())
    return config


def test_include_stays_in_nav_when_another_key_follows(tmp_path: Path) -> None:
    """Regression: the entry used to land under whatever key closed the file."""
    config = _nav_after_patch(
        tmp_path,
        "site_name: ws\n\nnav:\n  - Home: index.md\n\n"
        "markdown_extensions:\n  - admonition\n  - tables\n",
    )

    assert config["nav"] == [
        {"Home": "index.md"},
        {"my-lib": "!include ./packages/my-lib/mkdocs.yml"},
    ]
    assert config["markdown_extensions"] == ["admonition", "tables"]


def test_include_joins_the_existing_member_group(tmp_path: Path) -> None:
    """A new member lands after its siblings, inside their nav group."""
    config = _nav_after_patch(
        tmp_path,
        "nav:\n  - Home: index.md\n  - Packages:\n    - packages/index.md\n"
        "    - axm-dag: '!include ./packages/axm-dag/mkdocs.yml'\n"
        "  - Contributing:\n    - contributing.md\n\nplugins:\n  - monorepo\n",
    )

    assert config["nav"][1] == {
        "Packages": [
            "packages/index.md",
            {"axm-dag": "!include ./packages/axm-dag/mkdocs.yml"},
            {"my-lib": "!include ./packages/my-lib/mkdocs.yml"},
        ]
    }
    assert config["nav"][2] == {"Contributing": ["contributing.md"]}
    assert config["plugins"] == ["monorepo"]


def test_without_nav_the_file_is_left_untouched(tmp_path: Path) -> None:
    body = "site_name: ws\nmarkdown_extensions:\n  - admonition\n"
    (tmp_path / "mkdocs.yml").write_text(body)

    assert patch_mkdocs(tmp_path, "my-lib") is False
    assert (tmp_path / "mkdocs.yml").read_text() == body
