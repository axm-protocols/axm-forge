"""Cross-cutting test: every failed check must have a non-empty fix."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import pytest

from axm_init.checks.changelog import check_gitcliff_config, check_no_manual_changelog
from axm_init.checks.ci import (
    check_ci_coverage_upload,
    check_ci_lint_job,
    check_ci_security_job,
    check_ci_test_job,
    check_ci_workflow_exists,
    check_dependabot,
    check_trusted_publishing,
)
from axm_init.checks.deps import check_dev_deps, check_docs_deps
from axm_init.checks.docs import (
    check_diataxis_nav,
    check_docs_gen_ref_pages,
    check_docs_plugins,
    check_mkdocs_exists,
    check_readme,
)
from axm_init.checks.pyproject import (
    check_pyproject_classifiers,
    check_pyproject_coverage,
    check_pyproject_dynamic_version,
    check_pyproject_exists,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
    check_pyproject_urls,
)
from axm_init.checks.structure import (
    check_contributing,
    check_license_file,
    check_py_typed,
    check_python_version,
    check_src_layout,
    check_tests_dir,
    check_uv_lock,
)
from axm_init.checks.tooling import (
    check_makefile,
    check_precommit_basic,
    check_precommit_conventional,
    check_precommit_exists,
    check_precommit_mypy,
    check_precommit_ruff,
)
from axm_init.models.check import CheckResult


class TestAllFailuresHaveFix:
    """Every check function, when failing, must provide a non-empty fix."""

    ALL_CHECKS: ClassVar[list[Callable[[Path], CheckResult]]] = [
        check_pyproject_exists,
        check_pyproject_urls,
        check_pyproject_dynamic_version,
        check_pyproject_mypy,
        check_pyproject_ruff,
        check_pyproject_pytest,
        check_pyproject_coverage,
        check_pyproject_classifiers,
        check_pyproject_ruff_rules,
        check_ci_workflow_exists,
        check_ci_lint_job,
        check_ci_test_job,
        check_ci_security_job,
        check_ci_coverage_upload,
        check_trusted_publishing,
        check_dependabot,
        check_precommit_exists,
        check_precommit_ruff,
        check_precommit_mypy,
        check_precommit_conventional,
        check_precommit_basic,
        check_makefile,
        check_mkdocs_exists,
        check_diataxis_nav,
        check_docs_plugins,
        check_docs_gen_ref_pages,
        check_readme,
        check_src_layout,
        check_py_typed,
        check_tests_dir,
        check_contributing,
        check_license_file,
        check_uv_lock,
        check_python_version,
        check_dev_deps,
        check_docs_deps,
        check_gitcliff_config,
        check_no_manual_changelog,
    ]

    @pytest.mark.parametrize(
        "check_fn",
        ALL_CHECKS,
        ids=[fn.__name__ for fn in ALL_CHECKS],
    )
    def test_failed_check_has_fix(
        self, check_fn: Callable[[Path], CheckResult], empty_project: Path
    ) -> None:
        # Some checks pass on empty projects (e.g. no_manual_changelog)
        r: CheckResult = check_fn(empty_project)
        if not r.passed:
            assert r.fix != "", f"{r.name} failed but has no fix instruction"
