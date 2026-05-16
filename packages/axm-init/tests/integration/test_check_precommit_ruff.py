"""Tests for checks.tooling — developer tooling checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.tooling import (
    check_precommit_ruff,
)


class TestCheckPrecommitRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_precommit_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_file(self, empty_project: Path) -> None:
        r = check_precommit_ruff(empty_project)
        assert r.passed is False
