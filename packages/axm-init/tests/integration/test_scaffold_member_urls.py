"""Integration test: scaffolded member [project.urls] coherence (AXM-1841)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "axm_init"
    / "templates"
    / "workspace-member"
)


@pytest.mark.integration
def test_member_documentation_url_uses_workspace_base(tmp_path: Path) -> None:
    """AC1: Documentation URL is built on the workspace base, not a member-only host.

    A scaffolded member has no standalone GitHub Pages site: its docs are
    merged into the workspace site via the mkdocs ``monorepo`` plugin, served
    at ``github.io/{workspace_name}``. The Documentation URL must therefore
    resolve on the workspace base (``workspace_name``), never on a host keyed
    only by ``member_name``.
    """
    from axm_init.adapters.copier import CopierAdapter, CopierConfig

    org = "acme-org"
    workspace_name = "acme-workspace"
    member_name = "my-member"
    dest = tmp_path / "member"

    config = CopierConfig(
        template_path=TEMPLATE,
        destination=dest,
        data={
            "member_name": member_name,
            "description": "A workspace member package",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "org": org,
            "license": "Apache-2.0",
            "workspace_name": workspace_name,
        },
        defaults=True,
        overwrite=True,
        trust_template=True,
    )

    result = CopierAdapter().copy(config)
    assert result.success, result.message

    pyproject = dest / "pyproject.toml"
    assert pyproject.exists()
    parsed = tomllib.loads(pyproject.read_text())
    documentation = parsed["project"]["urls"]["Documentation"]

    # Built on the workspace base, not a member-only host.
    assert workspace_name in documentation, documentation
    assert documentation != f"https://{org}.github.io/{member_name}/"
    assert f"{org}.github.io/{member_name}/" not in documentation, documentation

    # Consistent with the other member URLs (all share the workspace_name base).
    urls = parsed["project"]["urls"]
    for key in ("Homepage", "Repository", "Issues"):
        assert workspace_name in urls[key], (key, urls[key])
