"""Split from ``test_audit_category_test_quality.py``."""

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.models.results import AuditResult
from tests.integration._helpers import _tools_available


@pytest.mark.integration
def test_audit_project_category_test_quality_empty_returns_valid_result(
    tmp_path: Path,
) -> None:
    """audit_project accepts category='test_quality' and returns an AuditResult."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")

    result = audit_project(tmp_path, category="test_quality")

    assert result is not None
    assert result.project_path == str(tmp_path)


def test_audit_project_invalid_category_raises_error(tmp_path):
    """Test that audit_project raises ValueError for invalid category."""
    from axm_audit import audit_project

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")

    with pytest.raises(ValueError, match="Invalid category"):
        audit_project(tmp_path, category="invalid_category")


@pytest.mark.parametrize(
    "category",
    [
        "lint",
        "type",
        "complexity",
        "security",
        "deps",
        "testing",
        "architecture",
        "practices",
        "structure",
        "tooling",
    ],
)
def test_audit_project_category_filtering(tmp_path, category):
    """Category filter must restrict result.checks to the requested category."""
    from axm_audit import audit_project

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    result = audit_project(tmp_path, category=category)
    assert result.checks, f"category={category} produced no checks"
    leaked = {c.category or "" for c in result.checks}
    assert all(c.category == category for c in result.checks), (
        f"category={category} leaked checks: {sorted(leaked)}"
    )


def test_audit_project_quick_mode(tmp_path):
    """Test that quick mode runs only lint and type checks."""
    from axm_audit import audit_project

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    result = audit_project(tmp_path, quick=True)
    # Quick mode should run fewer checks
    assert result.total <= 2  # Only lint and type checks


def test_audit_uses_thread_pool(tmp_path, mocker):
    """Verify rules execute via ThreadPoolExecutor."""
    import concurrent.futures

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    spy = mocker.spy(concurrent.futures, "ThreadPoolExecutor")

    from axm_audit import audit_project

    audit_project(tmp_path, quick=True)
    spy.assert_called_once()


def test_audit_project_test_quality_returns_test_quality_rules(
    minimal_pkg: Path,
) -> None:
    result = audit_project(minimal_pkg, category="test_quality")
    rule_ids = {c.rule_id for c in result.checks}
    expected = {
        "TEST_QUALITY_DUPLICATE_TESTS",
        "TEST_QUALITY_PRIVATE_IMPORTS",
        "TEST_QUALITY_PYRAMID_LEVEL",
        "TEST_QUALITY_TAUTOLOGY",
    }
    assert expected <= rule_ids, f"missing test_quality rules: {expected - rule_ids}"


def test_audit_project_rejects_unknown_category(minimal_pkg: Path) -> None:
    with pytest.raises((ValueError, KeyError)):
        audit_project(minimal_pkg, category="bogus")


def test_audit_project_invalid_category_lists_test_quality(minimal_pkg: Path) -> None:
    with pytest.raises(ValueError) as exc_info:
        audit_project(minimal_pkg, category="bogus")
    msg = str(exc_info.value)
    assert "test_quality" in msg
    assert "testing" in msg


class TestFormattingRuleIntegration:
    """Functional tests for FormattingRule via audit_project."""

    def test_audit_includes_format_rule(self, tmp_path: Path) -> None:
        """audit_project with quality category includes QUALITY_FORMAT."""
        from axm_audit.core.auditor import audit_project

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package."""\n')
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )

        result = audit_project(tmp_path, category="lint")
        rule_ids = [c.rule_id for c in result.checks]
        assert "QUALITY_FORMAT" in rule_ids


@pytest.fixture()
def broken_project(tmp_path: Path) -> Path:
    """Create a project with deliberate lint errors.

    The source file contains unused imports and missing docstrings,
    which should cause lint rules to flag issues and lower the score.
    """
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "broken"
            version = "0.1.0"
            requires-python = ">=3.12"

            [tool.ruff]
            line-length = 88
            select = ["E", "F", "I"]
        """)
    )

    src = tmp_path / "src" / "broken"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text(
        textwrap.dedent("""\
            import os
            import sys
            import json

            x=1
            y =2
            def foo():
                pass
        """)
    )

    return tmp_path


@pytest.fixture()
def no_tests_project(tmp_path: Path) -> Path:
    """Create a minimal project without a ``tests/`` directory."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "notests"
            version = "0.1.0"
            requires-python = ">=3.12"
        """)
    )

    src = tmp_path / "src" / "notests"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""No tests package."""\n')
    (src / "core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Core module.\"\"\"

            from __future__ import annotations


            def add(a: int, b: int) -> int:
                \"\"\"Add two numbers.\"\"\"
                return a + b
        """)
    )

    return tmp_path


def test_failed_rules_produce_text(tmp_path: Path) -> None:
    """audit_project(category='lint') on a dirty project fills text on failures."""
    from axm_audit.core.auditor import audit_project

    # Create a minimal Python project with a lint violation
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text("import os\nimport sys\n")  # unused imports
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1.0"\n[tool.ruff]\nselect = ["F"]\n'
    )

    result = audit_project(tmp_path, category="lint")

    failed = [c for c in result.checks if not c.passed]
    assert failed, "Expected at least one failed check for lint violations"
    for c in failed:
        assert c.text is not None, f"{c.rule_id} failed but text is None"


_skip_no_tools = pytest.mark.skipif(
    not _tools_available(),
    reason="ruff and/or mypy not available on PATH",
)


@_skip_no_tools
class TestEdgeCases:
    """Edge-case scenarios the pipeline must survive."""

    def test_broken_project_lower_score(self, broken_project: Path) -> None:
        """A project with lint errors should still audit without crashing.

        The score should be measurably lower than a clean project.
        """
        result = audit_project(broken_project)
        # Must complete — no crash
        assert isinstance(result.quality_score, float)
        # Lint errors should lower the lint score
        lint_checks = [c for c in result.checks if c.rule_id.startswith("QUALITY_LINT")]
        if lint_checks:
            score = lint_checks[0].score
            if score is not None:
                assert score < 100

    def test_no_tests_directory(self, no_tests_project: Path) -> None:
        """Audit passes on a project without a tests/ directory.

        Coverage score should be 0 (or very low) since there are no tests
        to run.
        """
        result = audit_project(no_tests_project)
        assert isinstance(result.quality_score, float)
        # Coverage check should show low/zero coverage
        coverage_checks = [c for c in result.checks if c.rule_id == "QUALITY_COVERAGE"]
        if coverage_checks:
            cov_score = coverage_checks[0].score or 0
            assert cov_score <= 10  # No tests → ~0% coverage

    def test_syntax_error_does_not_crash(self, tmp_path: Path) -> None:
        """A project with a syntax error should audit without crashing."""
        # Minimal project with invalid Python
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [build-system]
                requires = ["hatchling"]
                build-backend = "hatchling.build"

                [project]
                name = "syntaxerr"
                version = "0.1.0"
                requires-python = ">=3.12"
            """)
        )
        src = tmp_path / "src" / "syntaxerr"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "broken.py").write_text("def foo(\n")  # syntax error

        result = audit_project(tmp_path)
        # Pipeline must not crash — returns results
        assert isinstance(result.quality_score, float)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_pkg"
    src = project / "src" / "sample_pkg"
    src.mkdir(parents=True)
    tests = project / "tests"
    tests.mkdir()

    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text(
        "import time\n"
        "\n"
        "def public_no_doc(x):\n"
        "    return x\n"
        "\n"
        "def safe():\n"
        "    try:\n"
        "        return 1\n"
        "    except:\n"
        "        return 0\n"
        "\n"
        "async def slow():\n"
        "    time.sleep(1)\n"
    )
    return project


def test_full_audit_practices_findings(sample_project: Path) -> None:
    from axm_audit.core.auditor import audit_project

    result = audit_project(sample_project)
    by_id = {c.rule_id: c for c in result.checks}

    expected = {
        "PRACTICE_DOCSTRING",
        "PRACTICE_BARE_EXCEPT",
        "PRACTICE_BLOCKING_IO",
        "PRACTICE_TEST_MIRROR",
    }
    assert expected <= set(by_id.keys()), (
        f"missing practice rules: {expected - set(by_id.keys())}"
    )


def _make_minimal_pkg(root: Path) -> Path:
    pkg = root / "sample_pkg"
    (pkg / "src" / "sample_pkg").mkdir(parents=True)
    (pkg / "tests").mkdir()
    (pkg / "src" / "sample_pkg" / "__init__.py").write_text(
        '"""sample."""\nfrom __future__ import annotations\n\n__all__: list[str] = []\n'
    )
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.0.1"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )
    (pkg / "README.md").write_text("# sample\n")
    return pkg


def test_full_audit_score_consistency(tmp_path: Path) -> None:
    pkg = _make_minimal_pkg(tmp_path)
    report1 = audit_project(pkg)
    report2 = audit_project(pkg)
    assert report1.quality_score == report2.quality_score


# ---------------------------------------------------------------------------
# Workspace parallelization (AXM-1817)
# ---------------------------------------------------------------------------


def _make_ws_member(root: Path, name: str, body: str) -> None:
    mod = name.replace("-", "_")
    pkg_src = root / "packages" / name / "src" / mod
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    (pkg_src / "mod.py").write_text(textwrap.dedent(body))
    (root / "packages" / name / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )


def _make_uv_workspace(root: Path) -> None:
    _make_ws_member(root, "pkg-alpha", "def f() -> int:\n    return 0\n")
    _make_ws_member(root, "pkg-bravo", "def g():\n    x = 1\n    return 0\n")
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "ws"
            version = "0.0.0"
            requires-python = ">=3.12"

            [tool.uv.workspace]
            members = ["packages/*"]
            """
        )
    )


def _ws_signature(
    result: AuditResult,
) -> list[tuple[str, bool, int | None, str | None]]:
    return [(c.rule_id, c.passed, c.score, c.text) for c in result.checks]


def test_audit_project_workspace_parallel_matches_serial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1/AC2/AC3: parallel workspace audit == serial reference.

    Builds a temp uv workspace of two real mini-packages and audits it
    through the public ``audit_project`` entry (which dispatches to the
    parallel workspace path). The reference is the *same* public audit run
    with the workspace executor forced to a single worker (serial), patched
    via the stdlib ``ThreadPoolExecutor`` so the merge/aggregation policy is
    unchanged. The aggregated per-package checks, scores, prefixed text and
    ordering must be identical under parallel vs serial execution — proving
    the result is deterministic and independent of completion order, while
    each package still runs under its own isolated ``ASTCache`` (set inside
    ``audit_project`` per worker).
    """
    import concurrent.futures
    import functools

    _make_uv_workspace(tmp_path)

    # Parallel path (production dispatch over discovered workspace members).
    parallel = audit_project(tmp_path, category="lint")
    assert len(parallel.checks) >= 1

    # Serial reference: force the (outer) executor to a single worker.
    real_pool = concurrent.futures.ThreadPoolExecutor
    monkeypatch.setattr(
        concurrent.futures,
        "ThreadPoolExecutor",
        functools.partial(real_pool, max_workers=1),
    )
    serial = audit_project(tmp_path, category="lint")

    assert _ws_signature(parallel) == _ws_signature(serial)
    # Both workspace members are surfaced in the aggregated output.
    blob = " ".join(c.text or "" for c in parallel.checks)
    assert "pkg-alpha" in blob
    assert "pkg-bravo" in blob
