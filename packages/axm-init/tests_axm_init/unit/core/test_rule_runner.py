"""Explicit domain rules stay independent from project scoring."""

from pathlib import Path

import pytest

from axm_init.rules import run_rules


def test_rules_preserve_domain_findings_and_order(tmp_path: Path) -> None:
    findings = [{"status": "draft"}, {"status": "needs-evidence"}]
    paths = []

    def first(path: Path) -> dict[str, str]:
        paths.append(path)
        return findings[0]

    def second(path: Path) -> dict[str, str]:
        paths.append(path)
        return findings[1]

    results = run_rules(tmp_path, [first, second])

    assert results == findings
    assert results[0] is findings[0]
    assert paths == [tmp_path, tmp_path]
    assert run_rules(tmp_path, []) == []


def test_rule_errors_are_not_reported_as_quality_results(tmp_path: Path) -> None:
    def broken(path: Path) -> str:
        raise ValueError(f"Invalid domain manifest at {path}")

    with pytest.raises(ValueError, match="Invalid domain manifest"):
        run_rules(tmp_path, [broken])
