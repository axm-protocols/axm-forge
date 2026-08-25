"""AXM-19 — ``check_standalone_api_ref`` + workspace-member scaffold build.

The ``workspace-member`` Copier template used to ship a nav that declared
``reference/api/`` without the local ``gen_ref_pages.py`` + gen-files /
literate-nav / mkdocstrings plugins to resolve it, so ``mkdocs build
--strict`` aborted standalone (green only under the monorepo-root
aggregation). ``init_check`` missed it because check_plugins /
check_gen_ref_pages fall back to the workspace-root mkdocs.yml. This module:

- AC1: renders the real member template and runs a REAL ``mkdocs build
  --strict`` standalone;
- AC2: pins the un-masked failure path of ``check_standalone_api_ref`` (a
  broken member under ``packages/`` with a correct root still fails).

All tests do real filesystem I/O (tmp dirs, template render, subprocess), so
they are integration-level.
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

_FULL_MKDOCS = (
    "site_name: pkg\n"
    "docs_dir: docs\n"
    "nav:\n"
    "  - Reference:\n"
    "    - Python API: reference/api/\n"
    "plugins:\n"
    "  - search\n"
    "  - gen-files\n"
    "  - literate-nav\n"
    "  - mkdocstrings\n"
)

_NAV_ONLY_MKDOCS = (
    "site_name: pkg\n"
    "docs_dir: docs\n"
    "nav:\n"
    "  - Reference:\n"
    "    - Python API: reference/api/\n"
)


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


def _write_member(root: Path, *, mkdocs: str, gen_ref: bool) -> Path:
    """Create a scaffolded-member layout under ``root/packages/pkg``."""
    member = root / "packages" / "pkg"
    (member / "docs").mkdir(parents=True)
    (member / "mkdocs.yml").write_text(mkdocs)
    if gen_ref:
        (member / "docs" / "gen_ref_pages.py").write_text("# gen\n")
    return member


def _write_good_root(root: Path) -> None:
    """Give the workspace root a correct mkdocs + gen_ref_pages (aggregation)."""
    (root / "docs").mkdir()
    (root / "docs" / "gen_ref_pages.py").write_text("# root gen\n")
    (root / "mkdocs.yml").write_text(
        "plugins:\n  - gen-files\n  - literate-nav\n  - mkdocstrings\n"
    )


# --- AC2: un-masked failure path of the check -------------------------------


def test_broken_member_not_masked_by_root(tmp_path: Path) -> None:
    """A member promising reference/api/ but missing local wiring FAILS.

    Even when the workspace root carries the plugins + gen_ref_pages.py, the
    local standalone build cannot resolve the nav entry, so the check must
    fail (no root fallback). This is the exact defect AXM-19 fixed.
    """
    member = _write_member(tmp_path, mkdocs=_NAV_ONLY_MKDOCS, gen_ref=False)
    _write_good_root(tmp_path)

    result = check_standalone_api_ref(member)

    assert result.passed is False
    assert result.name == "docs.standalone_api_ref"
    joined = " ".join(result.details)
    assert "gen-files" in joined
    assert "literate-nav" in joined
    assert "mkdocstrings" in joined
    assert "docs/gen_ref_pages.py" in joined


def test_wired_member_passes_standalone(tmp_path: Path) -> None:
    """A member with its own plugins + gen_ref_pages.py builds standalone."""
    member = _write_member(tmp_path, mkdocs=_FULL_MKDOCS, gen_ref=True)

    result = check_standalone_api_ref(member)

    assert result.passed is True


@pytest.mark.parametrize(
    "mkdocs",
    [
        pytest.param("site_name: x\nnav:\n  - Home: index.md\n", id="no_api_promise"),
        pytest.param(None, id="no_local_mkdocs"),
    ],
)
def test_trivial_pass_when_no_api_promise(tmp_path: Path, mkdocs: str | None) -> None:
    """No ``reference/api/`` nav promise (or no mkdocs) → passes trivially."""
    if mkdocs is not None:
        (tmp_path / "mkdocs.yml").write_text(mkdocs)

    result = check_standalone_api_ref(tmp_path)

    assert result.passed is True


# --- AC1: real member scaffold builds --strict standalone -------------------


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
