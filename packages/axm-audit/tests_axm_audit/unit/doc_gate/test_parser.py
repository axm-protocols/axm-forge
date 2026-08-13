from __future__ import annotations

from axm_audit.doc_gate.findings import FindingKind
from axm_audit.doc_gate.parser import parse_mkdocs_output


def test_dead_link_warning_parses_to_dead_link_finding() -> None:
    output = (
        "WARNING -  Doc file 'index.md' contains a link 'missing-page.md' "
        "which is not found among the documentation files."
    )
    result = parse_mkdocs_output(output)
    assert result[0].kind == FindingKind.dead_link
    assert result[0].target == "missing-page.md"
    assert result[0].source_page == "index.md"


def test_missing_anchor_line_maps_to_missing_anchor() -> None:
    output = (
        "WARNING -  Doc file 'guide.md' contains a link 'other.md#missing' "
        "but the page does not contain an anchor '#missing'."
    )
    result = parse_mkdocs_output(output)
    assert result[0].kind == FindingKind.missing_anchor


def test_unknown_extension_line_maps_to_unknown_extension() -> None:
    output = (
        "WARNING -  Doc file 'page.md' links to 'asset.xyz' with an "
        "unknown extension '.xyz'."
    )
    result = parse_mkdocs_output(output)
    assert result[0].kind == FindingKind.unknown_extension


def test_bad_reference_line_maps_to_bad_reference() -> None:
    output = (
        "WARNING -  Doc file 'api.md' contains a bad reference 'sym.func' "
        "that could not be resolved."
    )
    result = parse_mkdocs_output(output)
    assert result[0].kind == FindingKind.bad_reference


def test_empty_output_returns_empty_list() -> None:
    assert parse_mkdocs_output("") == []


def test_clean_output_with_no_warning_returns_empty_list() -> None:
    output = (
        "INFO    -  Building documentation...\n"
        "INFO    -  Cleaning site directory\n"
        "INFO    -  Documentation built in 0.42 seconds"
    )
    assert parse_mkdocs_output(output) == []


def test_mixed_log_keeps_only_canonical_diagnostics() -> None:
    """AC2: mixed output retains only canonical mkdocs diagnostic records."""
    output = "\n".join(
        [
            (
                "WARNING -  Doc file 'index.md' contains a link 'missing.md' "
                "which is not found among the documentation files."
            ),
            (
                "WARNING -  Sponsor banner contains a link 'support.md' "
                "which is not found among the documentation files."
            ),
            (
                "WARNING -  Doc file 'guide.md' contains a link "
                "'other.md#missing' but the page does not contain an anchor "
                "'#missing'."
            ),
            "ERROR -  Theme link preview mentions an unrecognized anchor.",
            (
                "WARNING -  Doc file 'api.md' contains a bad reference "
                "'sym.func' that could not be resolved."
            ),
            "WARNING -  Sponsor reference could not be resolved.",
        ]
    )

    result = parse_mkdocs_output(output)

    assert [finding.kind for finding in result] == [
        FindingKind.dead_link,
        FindingKind.missing_anchor,
        FindingKind.bad_reference,
    ]


def test_noncanonical_warning_and_error_lines_are_ignored() -> None:
    """AC3: diagnostic vocabulary alone does not constitute a finding."""
    output = "\n".join(
        [
            (
                "WARNING -  Sponsor banner contains a link 'support.md' "
                "which is not found among the documentation files."
            ),
            "ERROR -  Theme link preview mentions an unrecognized anchor.",
            "WARNING -  Sponsor reference could not be resolved.",
        ]
    )

    assert parse_mkdocs_output(output) == []
