from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "docs" / "test_quality.md"
README_PATH = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def doc_content() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_file_exists() -> None:
    assert DOC_PATH.is_file(), f"missing doc: {DOC_PATH}"


def test_doc_has_four_h2_sections(doc_content: str) -> None:
    headers = {
        h.strip() for h in re.findall(r"^##\s+(.+?)\s*$", doc_content, re.MULTILINE)
    }
    required = {"Private Imports", "Pyramid v6", "Duplicates", "Tautology Triage v4"}
    missing = required - headers
    assert not missing, f"missing H2 sections: {missing}"


def test_private_imports_anchor_resolvable(doc_content: str) -> None:
    assert re.search(r"^##\s+Private Imports\s*$", doc_content, re.MULTILINE), (
        "`## Private Imports` header not found — anchor #private-imports won't resolve"
    )


def test_pyramid_section_mentions_5_rules(doc_content: str) -> None:
    for label in ("R1", "R2", "R3", "R4", "R5"):
        assert re.search(rf"\b{label}\b", doc_content), (
            f"{label} missing from pyramid section"
        )


def test_duplicates_section_mentions_7_tags(doc_content: str) -> None:
    for label in ("S1", "S2", "S3", "P1", "P2", "P3", "P4"):
        assert re.search(rf"\b{label}\b", doc_content), (
            f"{label} missing from duplicates section"
        )


def test_triage_section_mentions_22_steps(doc_content: str) -> None:
    step_tokens = re.findall(r"step_[A-Za-z0-9_]+", doc_content)
    assert len(step_tokens) >= 22, (
        f"expected >=22 step_* tokens, found {len(step_tokens)}"
    )


def test_validation_section_metrics(doc_content: str) -> None:
    for metric in ("17", "126", "1", "169"):
        assert re.search(rf"(?<!\d){metric}(?!\d)", doc_content), (
            f"validation metric {metric!r} missing from doc"
        )


def test_readme_links_doc() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    assert "docs/test_quality.md" in content, (
        "README missing link to docs/test_quality.md"
    )
