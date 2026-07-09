"""AC1: a freshly scaffolded workspace member builds ``--strict`` standalone.

AXM-19 — the ``workspace-member`` Copier template used to ship a nav that
declared ``reference/api/`` without the local ``gen_ref_pages.py`` + gen-files
/ literate-nav / mkdocstrings plugins to resolve it, so ``mkdocs build
--strict`` aborted standalone (green only under the monorepo-root aggregation).
This renders the real template and asserts a clean standalone strict build,
plus that :func:`check_standalone_api_ref` is green on the rendered output.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib.util import find_spec
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.checks.docs import check_standalone_api_ref
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

# The four mkdocs plugins the standalone strict build needs. Their pip names
# differ from their import names, so probe the import modules directly.
_DOCS_IMPORTS = ("material", "mkdocstrings", "mkdocs_gen_files", "mkdocs")
_LITERATE_NAV_DIST = "mkdocs-literate-nav"

_MEMBER_DATA = {
    "member_name": "my-pkg",
    "description": "A workspace member package",
    "author_name": "Test Author",
    "author_email": "test@example.com",
    "org": "TestOrg",
    "license": "Apache-2.0",
    "workspace_name": "my-ws",
}


def _docs_toolchain_available() -> bool:
    """True when mkdocs + all four strict-build plugins are importable."""
    if any(find_spec(mod) is None for mod in _DOCS_IMPORTS):
        return False
    from importlib.metadata import PackageNotFoundError, version

    try:
        version(_LITERATE_NAV_DIST)
    except PackageNotFoundError:
        return False
    return shutil.which("mkdocs") is not None or find_spec("mkdocs") is not None


_TOOLCHAIN = _docs_toolchain_available()


@pytest.fixture(scope="module")
def scaffolded_member(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the workspace-member template once via real Copier."""
    dest = tmp_path_factory.mktemp("member_scaffold") / "my-pkg"
    config = CopierConfig(
        template_path=get_template_path(TemplateType.MEMBER),
        destination=dest,
        data=_MEMBER_DATA,
        trust_template=True,
    )
    result = CopierAdapter().copy(config)
    assert result.success, result.message
    return dest


def test_member_ships_gen_ref_pages(scaffolded_member: Path) -> None:
    """The rendered member carries its own API-reference generator."""
    assert (scaffolded_member / "docs" / "gen_ref_pages.py").is_file()
    mkdocs = (scaffolded_member / "mkdocs.yml").read_text()
    for plugin in ("gen-files", "literate-nav", "mkdocstrings"):
        assert plugin in mkdocs


def test_member_check_standalone_api_ref_passes(scaffolded_member: Path) -> None:
    """``check_standalone_api_ref`` is green on the rendered member."""
    result = check_standalone_api_ref(scaffolded_member)
    assert result.passed is True, result.details


@pytest.mark.skipif(
    not _TOOLCHAIN,
    reason="mkdocs docs toolchain (material/mkdocstrings/gen-files/literate-nav) "
    "not installed in this environment",
)
def test_member_builds_strict_standalone(scaffolded_member: Path) -> None:
    """``mkdocs build --strict`` succeeds standalone on the rendered member."""
    proc = subprocess.run(
        ["mkdocs", "build", "--strict"],
        cwd=scaffolded_member,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    # gen-files + literate-nav must have materialized the API reference tree.
    assert (scaffolded_member / "site" / "reference" / "api").is_dir()
