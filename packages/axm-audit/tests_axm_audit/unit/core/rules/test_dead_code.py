"""Dead-code rule uses the AST library and preserves its audit evidence."""

from pathlib import Path

import pytest
from axm_ast.core.dead_code import DeadSymbol
from pytest_mock import MockerFixture

from axm_audit.core.rules.dead_code import DeadCodeRule
from axm_audit.models.results import Severity

# Unit-level library adapter contracts.


def test_dead_code_rule_id_format() -> None:
    assert DeadCodeRule().rule_id == "QUALITY_DEAD_CODE"


def test_the_library_builder_receives_the_measured_package(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    package = mocker.sentinel.package
    builder = mocker.patch(
        "axm_audit.core.rules.dead_code.get_package", return_value=package
    )
    analyzer = mocker.patch(
        "axm_audit.core.rules.dead_code.find_dead_code", return_value=[]
    )
    result = DeadCodeRule().check(tmp_path)

    builder.assert_called_once_with(tmp_path)
    analyzer.assert_called_once_with(package)
    assert result.passed
    assert result.score == 100
    assert result.severity == Severity.INFO
    assert result.details == {"dead_count": 0, "symbols": []}
    assert result.text is None


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (2, (90, 2, None)),
        (10, (50, 10, None)),
        (11, (45, 11, "+1 more")),
        (12, (40, 11, "+2 more")),
        (21, (0, 11, "+11 more")),
    ],
)
def test_dead_symbols_keep_scores_details_and_bounded_text(
    tmp_path: Path,
    mocker: MockerFixture,
    count: int,
    expected: tuple[int, int, str | None],
) -> None:
    score, lines, overflow = expected
    mocker.patch("axm_audit.core.rules.dead_code.get_package")
    mocker.patch(
        "axm_audit.core.rules.dead_code.find_dead_code",
        return_value=[
            DeadSymbol(
                name=f"sym_{i}",
                module_path=f"src/pkg/mod{i}.py",
                line=i + 1,
                kind="function",
            )
            for i in range(count)
        ],
    )
    result = DeadCodeRule().check(tmp_path)

    assert not result.passed
    assert result.score == score
    assert result.severity == Severity.WARNING
    assert result.details is not None
    assert result.details["dead_count"] == count
    assert len(result.details["symbols"]) == count
    assert len(result.details["top_offenders"]) == min(count, 10)
    assert result.details["symbols"][0] == {
        "name": "sym_0",
        "module_path": "src/pkg/mod0.py",
        "line": 1,
        "kind": "function",
    }
    assert result.text is not None
    assert len(result.text.splitlines()) == lines
    assert "• sym_0 pkg/mod0.py:1" in result.text
    assert "src/" not in result.text
    if overflow is not None:
        assert result.text.splitlines()[-1] == f"• {overflow}"
    else:
        assert "more" not in result.text


@pytest.mark.parametrize(
    "error",
    [
        OSError("unreadable"),
        ValueError("invalid package"),
        RuntimeError("analysis failed"),
    ],
)
def test_library_analysis_errors_are_failed_instruments(
    tmp_path: Path, mocker: MockerFixture, error: Exception
) -> None:
    mocker.patch("axm_audit.core.rules.dead_code.get_package", side_effect=error)
    analyzer = mocker.patch("axm_audit.core.rules.dead_code.find_dead_code")

    result = DeadCodeRule().check(tmp_path)

    analyzer.assert_not_called()
    assert not result.passed
    assert result.score == 0
    assert result.severity == Severity.ERROR
    assert result.details == {"error": str(error)}
