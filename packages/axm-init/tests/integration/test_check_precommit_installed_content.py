"""Integration: content checks are runner-agnostic on a prek-based repo."""

from pathlib import Path

import pytest

from axm_init.checks.tooling import (
    check_precommit_basic,
    check_precommit_conventional,
    check_precommit_exists,
    check_precommit_installed,
    check_precommit_mypy,
    check_precommit_ruff,
)


@pytest.mark.integration
class TestPrecommitContentChecksPrekRepo:
    def test_content_checks_unchanged_for_prek_repo(self, gold_project: Path) -> None:
        """AC5: the 6 precommit content checks still pass on a prek repo.

        The gold-standard fixture pins prek in its dev group while keeping the
        runner-agnostic ``.pre-commit-config.yaml`` (and activated hooks). All
        six ``check_precommit_*`` checks must remain green because the config
        filename is unchanged by the prek migration.
        """
        checks = (
            check_precommit_exists,
            check_precommit_ruff,
            check_precommit_mypy,
            check_precommit_conventional,
            check_precommit_basic,
            check_precommit_installed,
        )
        results = {fn.__name__: fn(gold_project) for fn in checks}
        failed = [name for name, r in results.items() if not r.passed]
        assert not failed, f"content checks unexpectedly failed: {failed}"
