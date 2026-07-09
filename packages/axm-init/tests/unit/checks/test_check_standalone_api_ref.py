"""Unit tests for ``check_standalone_api_ref`` (AXM-19 failure path).

The rule guards ``mkdocs build --strict`` **standalone** integrity: a
package whose *local* nav declares an auto-generated ``reference/api/``
section must carry its own ``docs/gen_ref_pages.py`` + the gen-files /
literate-nav / mkdocstrings plugins — with NO workspace-root fallback.
The root fallback (correct for monorepo aggregation) previously masked
broken members, so ``init_check`` was green while the standalone build
was red. This test pins the un-masked failure path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.docs import check_standalone_api_ref

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


def test_broken_member_not_masked_by_root(tmp_path: Path) -> None:
    """A member promising reference/api/ but missing local wiring FAILS.

    Even when the workspace root carries the plugins + gen_ref_pages.py,
    the local standalone build cannot resolve the nav entry, so the check
    must fail (no root fallback). This is the exact defect AXM-19 fixed.
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
