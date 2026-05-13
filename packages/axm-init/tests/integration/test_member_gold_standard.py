"""Unit tests for workspace-member Copier template — gold standard compliance.

These tests read the raw Jinja template files and verify they contain
the expected Diátaxis configurations and monorepo compatibility constraints.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Template root = src/axm_init/templates/workspace-member/
TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "axm_init"
    / "templates"
    / "workspace-member"
)

DOCS_DIR = TEMPLATE_ROOT / "docs"


# ─────────────────────────────────────────────────────────────────────────────
# Docs Diátaxis structure tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMemberDocsStructure:
    """Docs must have Diátaxis directory structure."""

    def test_no_flat_getting_started(self) -> None:
        """Old flat getting-started.md should NOT exist."""
        assert not (DOCS_DIR / "getting-started.md.jinja").exists()

    @pytest.mark.parametrize(
        "subdir",
        [
            pytest.param("tutorials", id="tutorials"),
            pytest.param("howto", id="howto"),
            pytest.param("reference", id="reference"),
            pytest.param("explanation", id="explanation"),
        ],
    )
    def test_diataxis_dir_exists(self, subdir: str) -> None:
        assert (DOCS_DIR / subdir).is_dir()

    @pytest.mark.parametrize(
        "relpath",
        [
            pytest.param(
                "tutorials/getting-started.md.jinja", id="tutorials_getting_started"
            ),
            pytest.param("howto/index.md", id="howto_index"),
            pytest.param("reference/cli.md.jinja", id="reference_cli"),
            pytest.param(
                "explanation/architecture.md.jinja", id="explanation_architecture"
            ),
        ],
    )
    def test_diataxis_file_exists(self, relpath: str) -> None:
        assert (DOCS_DIR / relpath).exists()

    def test_no_gen_ref_pages(self) -> None:
        """gen_ref_pages is dead code in nav-only members.

        Standalone python-project members handle this themselves.
        """
        assert not (DOCS_DIR / "gen_ref_pages.py.jinja").exists()
