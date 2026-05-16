"""Tests for checks.deps — dependency hygiene checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.deps import check_docs_group


class TestCheckDocsDeps:
    def test_pass(self, gold_project: Path) -> None:
        r = check_docs_group(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[dependency-groups]\ndocs = ["mkdocs"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_docs_group(tmp_path)
        assert r.passed is False
