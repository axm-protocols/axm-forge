"""Unit tests for the Node security rules (npm audit + gitleaks)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.node import _base as base_module
from axm_audit.core.rules.node.security import NodeSecretsRule, NodeVulnerabilityRule


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess for an on-PATH tool invocation."""
    return subprocess.CompletedProcess(
        args=["tool"], returncode=returncode, stdout=stdout, stderr=""
    )


def _path_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Wire a node project with an on-PATH tool available and a canned result."""
    (tmp_path / "package.json").write_text('{"name":"n"}')
    monkeypatch.setattr(base_module, "path_tool_available", lambda _b: True)
    monkeypatch.setattr(base_module, "run_node_tool", lambda *_a, **_k: result)


class TestVulnerabilityRule:
    """``NodeVulnerabilityRule`` scores npm-audit high/critical counts."""

    def test_rule_id(self) -> None:
        """Shares the Python dependency-audit rule_id."""
        assert NodeVulnerabilityRule().rule_id == "DEPS_AUDIT"

    def test_no_vulns_scores_100(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clean audit (rc=0) scores 100."""
        payload = {"metadata": {"vulnerabilities": {"high": 0, "critical": 0}}}
        _path_project(tmp_path, monkeypatch, _completed(json.dumps(payload), 0))
        assert NodeVulnerabilityRule().check(tmp_path).score == 100

    def test_high_and_critical_deduct_fifteen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """npm audit exits 1 with vulns; each high/critical deducts 15."""
        payload = {"metadata": {"vulnerabilities": {"high": 1, "critical": 1}}}
        # rc=1 must be treated as a finding, not an env-failure.
        _path_project(tmp_path, monkeypatch, _completed(json.dumps(payload), 1))
        result = NodeVulnerabilityRule().check(tmp_path)
        assert result.score == 70
        assert result.passed is False


class TestSecretsRule:
    """``NodeSecretsRule`` scores gitleaks findings."""

    def test_rule_id(self) -> None:
        """Shares the Python secret-scan rule_id."""
        assert NodeSecretsRule().rule_id == "PRACTICE_SECURITY"

    def test_secrets_deduct_twenty_five(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each gitleaks finding deducts 25; rc=1 is a finding."""
        findings = [{"RuleID": "aws-key"}, {"RuleID": "generic"}]
        _path_project(tmp_path, monkeypatch, _completed(json.dumps(findings), 1))
        result = NodeSecretsRule().check(tmp_path)
        assert result.details["secret_count"] == 2
        assert result.score == 50
        assert result.passed is False
