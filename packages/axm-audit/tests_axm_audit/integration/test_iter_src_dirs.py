from __future__ import annotations

from pathlib import Path

import pytest

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
    (tmp_path / "src" / "mod.py").write_text("x = 1\n")
    assert _rule().check_src(tmp_path) is None


def test_check_src_multi_package_returns_none(tmp_path: Path) -> None:
    (tmp_path / "packages" / "a" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "b" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "a" / "src" / "mod.py").write_text("x = 1\n")
    (tmp_path / "packages" / "b" / "src" / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "src" / "mod.py").write_text("x = 1\n")
    (tmp_path / "packages" / "a" / "src").mkdir(parents=True)
    assert _rule().check_src(tmp_path) is None
    targets = iter_src_dirs(tmp_path)
    assert targets == [tmp_path / "src"]


@pytest.mark.parametrize(
    ("dirs_to_make", "expected_relative"),
    [
        pytest.param(
            ("src",),
            ("src",),
            id="single_package",
        ),
        pytest.param(
            ("packages/c/src", "packages/a/src", "packages/b/src"),
            ("packages/a/src", "packages/b/src", "packages/c/src"),
            id="multi_package_sorted",
        ),
        pytest.param(
            ("packages/a", "packages/b/src"),
            ("packages/b/src",),
            id="packages_dir_with_no_src_subdir_is_skipped",
        ),
        pytest.param(
            (),
            (),
            id="empty_when_no_layout",
        ),
    ],
)
def test_iter_src_dirs(
    tmp_path: Path,
    dirs_to_make: tuple[str, ...],
    expected_relative: tuple[str, ...],
) -> None:
    for rel in dirs_to_make:
        made = tmp_path / rel
        made.mkdir(parents=True)
        if made.name == "src":
            (made / "mod.py").write_text("x = 1\n")
    expected = [tmp_path / rel for rel in expected_relative]
    assert iter_src_dirs(tmp_path) == expected


def test_iter_src_dirs_skips_python_less_src(tmp_path: Path) -> None:
    """AC1: a src/ that exists but holds no .py/.pyi (TS/Svelte-only) is not a
    Python source root — early-passed as an empty layout."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export const x = 1;\n")
    (src / "Component.svelte").write_text("<div>hi</div>\n")
    assert iter_src_dirs(tmp_path) == []


def test_iter_src_dirs_pyi_only_src_is_a_root(tmp_path: Path) -> None:
    """A src/ containing only stub files (.pyi) still counts as a Python root."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "types.pyi").write_text("x: int\n")
    assert iter_src_dirs(tmp_path) == [src]


def test_iter_src_dirs_workspace_drops_python_less_package(tmp_path: Path) -> None:
    """AC1: in a workspace, a package whose src/ has no .py is dropped while a
    sibling Python package is kept."""
    (tmp_path / "packages" / "ts" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "ts" / "src" / "app.ts").write_text("const x = 1;\n")
    (tmp_path / "packages" / "py" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "py" / "src" / "mod.py").write_text("x = 1\n")
    assert iter_src_dirs(tmp_path) == [tmp_path / "packages" / "py" / "src"]


def test_check_src_python_less_src_returns_passing_stub(tmp_path: Path) -> None:
    """AC1: check_src early-passes a Python-less src/ (no mypy invocation)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export const x = 1;\n")
    result = _rule().check_src(tmp_path)
    assert result is not None
    assert result.passed is True
    assert result.score == 100
