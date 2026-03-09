"""Tests for checks.ci — CI workflow checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.ci import (
    check_ci_coverage_upload,
    check_ci_lint_job,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
    check_dependabot,
    check_trusted_publishing,
)


class TestCheckCiWorkflowExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_workflow_exists(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_ci_workflow_exists(empty_project)
        assert r.passed is False


class TestCheckCiLintJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_lint_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_lint_job(empty_project)
        assert r.passed is False


class TestCheckCiTestJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_test_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_test_job(empty_project)
        assert r.passed is False


class TestCheckCiSecurityJob:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_security_job(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_security_job(empty_project)
        assert r.passed is False


class TestCheckCiCoverageUpload:
    def test_pass(self, gold_project: Path) -> None:
        r = check_ci_coverage_upload(gold_project)
        assert r.passed is True

    def test_fail_no_ci(self, empty_project: Path) -> None:
        r = check_ci_coverage_upload(empty_project)
        assert r.passed is False


class TestCheckTrustedPublishing:
    def test_pass_oidc(self, gold_project: Path) -> None:
        r = check_trusted_publishing(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_no_publish(self, empty_project: Path) -> None:
        r = check_trusted_publishing(empty_project)
        assert r.passed is False

    def test_fail_no_oidc(self, tmp_path: Path) -> None:
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "publish.yml").write_text("name: Publish\njobs:\n  build:\n")
        r = check_trusted_publishing(tmp_path)
        assert r.passed is False

    def test_fail_hybrid_token_and_oidc(self, tmp_path: Path) -> None:
        """id-token present but still using PYPI_API_TOKEN → not true OIDC."""
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "publish.yml").write_text(
            "name: Publish\npermissions:\n  id-token: write\n"
            "jobs:\n  publish:\n    steps:\n"
            "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
            "        with:\n"
            "          password: ${{ secrets.PYPI_API_TOKEN }}\n"
        )
        r = check_trusted_publishing(tmp_path)
        assert r.passed is False
        assert "PYPI_API_TOKEN" in r.fix


class TestCheckDependabot:
    def test_pass(self, gold_project: Path) -> None:
        r = check_dependabot(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_dependabot(empty_project)
        assert r.passed is False
