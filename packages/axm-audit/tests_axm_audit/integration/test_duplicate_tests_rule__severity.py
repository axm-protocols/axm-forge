"""Split from ``test_duplicate_test_clustering.py``."""

import textwrap
from pathlib import Path

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule
from axm_audit.models.results import Severity


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def test_severity_warning_and_scoring(project: Path) -> None:
    for i in range(3):
        _write(
            project / "tests" / f"test_clu_{i}.py",
            f"""
            def test_c{i}_1():
                result = sut_{i}(1)
                assert result == {i}
                assert result >= 0

            def test_c{i}_2():
                result = sut_{i}(2)
                assert result == {i}
                assert result >= 0
            """,
        )
    for j in range(2):
        _write(
            project / "tests" / f"test_amb_{j}.py",
            f"""
            def test_a{j}_1():
                result = sut_amb_{j}("foo")
                assert result == "alpha"

            def test_a{j}_2():
                result = sut_amb_{j}("bar")
                assert result == "beta"
            """,
        )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    assert result.severity == Severity.WARNING
    assert result.score == 85
