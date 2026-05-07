from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules._helpers import iter_src_dirs
from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


class _DummyRule(ProjectRule):
    @property
    def rule_id(self) -> str:
        return "DUMMY"

    def check(self, project_path: Path) -> CheckResult:  # pragma: no cover - unused
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="ok",
            severity=Severity.INFO,
            score=100,
        )


def _rule() -> _DummyRule:
    return _DummyRule()


def test_check_src_single_package_returns_none(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert _rule().check_src(tmp_path) is None


def test_check_src_multi_package_returns_none(tmp_path: Path) -> None:
    (tmp_path / "packages" / "a" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "b" / "src").mkdir(parents=True)
    assert _rule().check_src(tmp_path) is None


def test_check_src_no_layout_returns_passing_stub(tmp_path: Path) -> None:
    result = _rule().check_src(tmp_path)
    assert result is not None
    assert result.passed is True
    assert result.message == "src/ directory not found"
    assert result.score == 100
    assert result.details is None


def test_check_src_prefers_single_when_both_present(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "packages" / "a" / "src").mkdir(parents=True)
    assert _rule().check_src(tmp_path) is None
    targets = iter_src_dirs(tmp_path)
    assert targets == [tmp_path / "src"]


def test_iter_src_dirs_single_package(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert iter_src_dirs(tmp_path) == [tmp_path / "src"]


def test_iter_src_dirs_multi_package_sorted(tmp_path: Path) -> None:
    for name in ("c", "a", "b"):
        (tmp_path / "packages" / name / "src").mkdir(parents=True)
    assert iter_src_dirs(tmp_path) == [
        tmp_path / "packages" / "a" / "src",
        tmp_path / "packages" / "b" / "src",
        tmp_path / "packages" / "c" / "src",
    ]


def test_iter_src_dirs_packages_dir_with_no_src_subdir_is_skipped(
    tmp_path: Path,
) -> None:
    (tmp_path / "packages" / "a").mkdir(parents=True)
    (tmp_path / "packages" / "b" / "src").mkdir(parents=True)
    assert iter_src_dirs(tmp_path) == [tmp_path / "packages" / "b" / "src"]


def test_iter_src_dirs_empty_when_no_layout(tmp_path: Path) -> None:
    assert iter_src_dirs(tmp_path) == []
