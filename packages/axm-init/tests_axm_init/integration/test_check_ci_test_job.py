"""Integration tests for ``check_ci_test_job`` against real CI YAML on disk."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks.ci import check_ci_test_job


def _write_ci(project: Path, content: str) -> None:
    ci_dir = project / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    (ci_dir / "ci.yml").write_text(content)


@pytest.mark.integration
def test_ci_test_job_requires_real_matrix(tmp_path: Path) -> None:
    """AC2: a CI mentioning 'pytest' only in a comment, with no
    python-version matrix test job, must FAIL the check."""
    _write_ci(
        tmp_path,
        dedent("""\
            name: CI
            # this workflow will eventually run pytest as a test
            on:
              push:
                branches: [main]
            jobs:
              lint:
                name: Lint
                runs-on: ubuntu-latest
                steps:
                  - run: make lint
        """),
    )
    result = check_ci_test_job(tmp_path)
    assert result.passed is False


@pytest.mark.integration
def test_ci_test_job_passes_with_matrix(tmp_path: Path) -> None:
    """AC2: a CI with a real test job carrying a python-version matrix
    and a test step must PASS the check."""
    _write_ci(
        tmp_path,
        dedent("""\
            name: CI
            on:
              push:
                branches: [main]
            jobs:
              test:
                name: Test
                strategy:
                  matrix:
                    python-version: ["3.12", "3.13"]
                steps:
                  - run: uv run pytest
        """),
    )
    result = check_ci_test_job(tmp_path)
    assert result.passed is True
