"""Fixture-backed integration tests for mkdocs output handling."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_audit.doc_gate.findings import FindingKind
from axm_audit.doc_gate.parser import parse_mkdocs_output
from axm_audit.doc_gate.tool import DocGateTool

_MATERIAL_SPONSOR_SUCCESS = """\
INFO    -  Building documentation...
WARNING -  Material sponsor banner contains a link 'support.md' \
which is not found among the documentation files.
INFO    -  Sponsor reference and anchor details are available online.
INFO    -  Documentation built in 0.42 seconds
"""

_FAILURE_LOGS = {
    "link": (
        "WARNING -  Doc file 'index.md' contains a link 'missing-page.md' "
        "which is not found among the documentation files.\n"
        "WARNING -  Sponsor banner contains a link 'support.md' "
        "which is not found among the documentation files."
    ),
    "anchor": (
        "WARNING -  Doc file 'guide.md' contains a link "
        "'other.md#missing' but the page does not contain an anchor "
        "'#missing'.\n"
        "ERROR -  Theme link preview mentions an unrecognized anchor."
    ),
    "reference": (
        "WARNING -  Doc file 'api.md' contains a bad reference 'sym.func' "
        "that could not be resolved.\n"
        "WARNING -  Sponsor reference could not be resolved."
    ),
}


@pytest.fixture
def doc_gate_logs(tmp_path: Path) -> dict[str, Path]:
    logs = {"material": _MATERIAL_SPONSOR_SUCCESS, **_FAILURE_LOGS}
    paths: dict[str, Path] = {}
    for name, content in logs.items():
        path = tmp_path / f"{name}.log"
        path.write_text(content)
        paths[name] = path
    return paths


@pytest.mark.integration
def test_material_sponsor_success_log_produces_no_findings(
    doc_gate_logs: dict[str, Path],
    mocker: MockerFixture,
) -> None:
    """AC4: the representative Material sponsor success log yields no findings."""
    output = doc_gate_logs["material"].read_text()
    completed = subprocess.CompletedProcess(
        args=["mkdocs"], returncode=0, stdout=output, stderr=""
    )
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        return_value=completed,
    )

    result = DocGateTool().execute(path=".")

    assert result.success is True
    assert result.data["findings"] == []
    assert result.data["count"] == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("fixture_name", "expected_kind"),
    [
        ("link", FindingKind.dead_link),
        ("anchor", FindingKind.missing_anchor),
        ("reference", FindingKind.bad_reference),
    ],
)
def test_failure_logs_reject_noncanonical_lookalikes(
    doc_gate_logs: dict[str, Path],
    fixture_name: str,
    expected_kind: FindingKind,
) -> None:
    """AC4: each failure log exposes its canonical record and no lookalike."""
    output = doc_gate_logs[fixture_name].read_text()

    result = parse_mkdocs_output(output)

    assert [finding.kind for finding in result] == [expected_kind]
