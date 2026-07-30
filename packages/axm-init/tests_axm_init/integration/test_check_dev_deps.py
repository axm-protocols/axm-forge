"""Integration: ``check_dev_deps`` against real pyproject.toml files on disk.

These cases write a ``pyproject.toml`` to ``tmp_path`` (real filesystem I/O)
and run the dev-deps check against it — covering the prek/pre-commit runner
migration acceptance criteria (AXM-2056). The pure in-memory pass/fail cases
live in ``tests/unit/checks/test_check_dev_deps.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.deps import check_dev_deps

pytestmark = pytest.mark.integration


class TestCheckDevDeps:
    def test_prek_satisfies_dev_group(self, tmp_path: Path) -> None:
        """AC1: dev group pinning prek (no pre-commit) passes clean.

        prek is the gold-standard runner: the check passes and carries no
        migration warning in its details.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "prek>=0.4.4"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is True
        assert not any("migrat" in d.lower() for d in r.details)

    def test_pre_commit_only_passes_with_warning(self, tmp_path: Path) -> None:
        """AC2: dev group with pre-commit (no prek) passes with soft warning.

        A project still pinning the legacy pre-commit runner is tolerated:
        the check stays green (does not dent the score) but surfaces a soft
        deprecation note inviting migration to prek.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy", "pre-commit>=4.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is True
        assert any("migrat" in d.lower() for d in r.details)

    def test_no_runner_fails(self, tmp_path: Path) -> None:
        """AC3: dev group with neither prek nor pre-commit fails.

        With no hook runner at all the check fails and the message names the
        missing runner.
        """
        toml = (
            '[project]\nname="x"\n[dependency-groups]\n'
            'dev = ["pytest", "ruff", "mypy"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is False
        assert "prek" in r.details[0]
