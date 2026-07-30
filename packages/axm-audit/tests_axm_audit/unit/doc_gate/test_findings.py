from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_audit.doc_gate import DocGateFinding, FindingKind


def test_finding_kind_has_exactly_four_members() -> None:
    assert {k.value for k in FindingKind} == {
        "dead_link",
        "missing_anchor",
        "unknown_extension",
        "bad_reference",
    }


def test_finding_kind_is_strenum_with_value_equal_to_name() -> None:
    assert FindingKind.dead_link == "dead_link"
    assert isinstance(FindingKind.dead_link, str)


def test_doc_gate_finding_constructs_from_valid_data() -> None:
    finding = DocGateFinding(
        kind=FindingKind.dead_link,
        target="docs/page.md",
        source_page="index.md",
    )
    assert finding.kind == FindingKind.dead_link
    assert finding.target == "docs/page.md"
    assert finding.source_page == "index.md"


def test_doc_gate_finding_rejects_unknown_extra_field() -> None:
    with pytest.raises(ValidationError):
        DocGateFinding(
            kind=FindingKind.dead_link,
            target="docs/page.md",
            source_page="index.md",
            bogus="x",  # type: ignore[call-arg]
        )


def test_doc_gate_finding_rejects_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        DocGateFinding(kind=FindingKind.dead_link, target="docs/page.md")  # type: ignore[call-arg]


def test_subpackage_re_exports_both_symbols() -> None:
    from axm_audit import doc_gate

    assert "FindingKind" in doc_gate.__all__
    assert "DocGateFinding" in doc_gate.__all__
    assert doc_gate.FindingKind is FindingKind
    assert doc_gate.DocGateFinding is DocGateFinding
