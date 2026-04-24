"""Integration: triage() output on AXM corpus matches the prototype golden.

AC10: 32 AXM packages yield 17 DELETE / 126 STRENGTHEN / 1 UNKNOWN, with the
same per-finding (pkg, file, test, rule) tuples as the v4 prototype.

AC12: axm-engine's four `test_*_is_axm_tool` tests in test_protocol_tools.py
all resolve to `step0c_contract_conformance`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


_WORKSPACES = Path.home() / "Documents" / "Code" / "python" / "axm-workspaces"
_GOLDEN_PATH = (
    Path(__file__).parent.parent / "fixtures" / "tautology_triage_corpus.json"
)
_EXPECTED_DISTRIBUTION = {"DELETE": 17, "STRENGTHEN": 126, "UNKNOWN": 1}


def _iter_axm_packages(root: Path) -> list[Path]:
    packages: list[Path] = []
    for workspace in root.iterdir():
        if not workspace.is_dir():
            continue
        pkg_root = workspace / "packages"
        if pkg_root.is_dir():
            packages.extend(p for p in pkg_root.iterdir() if p.is_dir())
        elif workspace.name == "other":
            packages.extend(p for p in workspace.iterdir() if p.is_dir())
    return packages


def _finding_tuple(finding: object) -> tuple[str, str, str, str]:
    pkg = getattr(finding, "package", "") or getattr(finding, "pkg", "")
    file = str(getattr(finding, "file", "") or getattr(finding, "path", ""))
    test = getattr(finding, "test", "") or getattr(finding, "test_name", "")
    rule = getattr(finding, "rule_id", "") or getattr(finding, "step", "")
    return str(pkg), file, str(test), str(rule)


@pytest.mark.skipif(
    not _WORKSPACES.exists() or not _GOLDEN_PATH.exists(),
    reason="requires AXM corpus checkout and golden snapshot",
)
def test_axm_all_corpus_matches_prototype() -> None:
    from axm_audit.core.rules.test_quality.tautology import TautologyRule

    rule = TautologyRule()
    findings: list[object] = []
    for pkg in _iter_axm_packages(_WORKSPACES):
        findings.extend(rule.check(pkg))

    distribution: dict[str, int] = {"DELETE": 0, "STRENGTHEN": 0, "UNKNOWN": 0}
    for f in findings:
        decision = getattr(f, "decision", None) or getattr(f, "verdict", None)
        if decision in distribution:
            distribution[decision] += 1
    assert distribution == _EXPECTED_DISTRIBUTION, (
        f"expected {_EXPECTED_DISTRIBUTION}, got {distribution}"
    )

    golden = json.loads(_GOLDEN_PATH.read_text())
    expected_tuples = sorted(tuple(row) for row in golden["findings"])
    actual_tuples = sorted(_finding_tuple(f) for f in findings)
    assert actual_tuples == expected_tuples


_ENGINE_PKG = _WORKSPACES / "axm-nexus" / "packages" / "axm-engine"
_PROTOCOL_TOOLS_TEST = _ENGINE_PKG / "tests" / "unit" / "test_protocol_tools.py"
_CONTRACT_TEST_NAMES = frozenset(
    {
        "test_protocol_init_is_axm_tool",
        "test_protocol_check_is_axm_tool",
        "test_protocol_read_is_axm_tool",
        "test_protocol_resume_is_axm_tool",
    }
)


@pytest.mark.skipif(
    not _PROTOCOL_TOOLS_TEST.exists(),
    reason="axm-engine protocol_tools test file not available",
)
def test_axm_engine_protocol_tools_contract_conformance() -> None:
    from axm_audit.core.rules.test_quality.tautology import TautologyRule

    rule = TautologyRule()
    findings = list(rule.check(_ENGINE_PKG))
    # Filter findings to the four tests named by AC12.
    matched: dict[str, str] = {}
    for f in findings:
        file_path = str(getattr(f, "file", "") or getattr(f, "path", ""))
        test_name = str(getattr(f, "test", "") or getattr(f, "test_name", ""))
        step = str(
            getattr(f, "step", "")
            or getattr(f, "rule_id", "")
            or getattr(f, "triage_step", "")
        )
        if test_name in _CONTRACT_TEST_NAMES and "test_protocol_tools.py" in file_path:
            matched[test_name] = step

    missing = _CONTRACT_TEST_NAMES - matched.keys()
    assert not missing, f"contract tests not covered by rule: {sorted(missing)}"
    for name, step in matched.items():
        assert step == "step0c_contract_conformance", (
            f"{name} routed to {step!r}, expected step0c_contract_conformance"
        )
