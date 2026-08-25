"""Unit tests for the node docs checks (MkDocs prose + TypeDoc API)."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.docs import check_api_reference, check_mkdocs_exists


def test_mkdocs_present_passes(tmp_path: Path) -> None:
    """An mkdocs.yml (reused from the Python standard) passes."""
    (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
    assert check_mkdocs_exists(tmp_path).passed is True


def test_mkdocs_absent_fails(tmp_path: Path) -> None:
    """No mkdocs.yml fails."""
    assert check_mkdocs_exists(tmp_path).passed is False


def test_typedoc_config_file_passes(tmp_path: Path) -> None:
    """A typedoc.json passes the API-reference check."""
    (tmp_path / "typedoc.json").write_text("{}")
    assert check_api_reference(tmp_path).passed is True


def test_typedoc_devdep_passes(tmp_path: Path) -> None:
    """A typedoc devDependency passes."""
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"typedoc": "^0.27"}})
    )
    assert check_api_reference(tmp_path).passed is True


def test_no_typedoc_fails(tmp_path: Path) -> None:
    """No TypeDoc config fails."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}))
    assert check_api_reference(tmp_path).passed is False
