"""Tests for checks.ci — CI workflow checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.ci import (
    check_trusted_publishing,
)


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
