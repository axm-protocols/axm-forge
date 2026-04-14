from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices import TestMirrorRule


class TestTestMirrorRule:
    """Tests for TestMirrorRule.check text= rendering."""

    @pytest.fixture()
    def rule(self) -> TestMirrorRule:
        return TestMirrorRule()

    @staticmethod
    def _make_project(
        tmp_path: Path,
        src_modules: list[str],
        test_files: list[str],
    ) -> Path:
        """Create a minimal project with src/<pkg>/ modules and tests/ files."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        for m in src_modules:
            (pkg / m).touch()
        tests = tmp_path / "tests"
        tests.mkdir()
        for t in test_files:
            (tests / t).touch()
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        return tmp_path

    # --- Unit tests ---

    def test_fail_missing_tests_has_text(
        self, rule: TestMirrorRule, tmp_path: Path
    ) -> None:
        """Failed result text starts with bullet and contains missing module."""
        project = self._make_project(
            tmp_path,
            src_modules=["a.py", "b.py"],
            test_files=["test_a.py"],
        )
        result = rule.check(project)
        assert result.text is not None
        assert result.text.startswith("\u2022 untested:")
        assert "b.py" in result.text

    def test_text_truncation_above_five(
        self, rule: TestMirrorRule, tmp_path: Path
    ) -> None:
        """Text truncates at 5 filenames with (+N more) suffix."""
        project = self._make_project(
            tmp_path,
            src_modules=[f"mod{i}.py" for i in range(7)],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "(+2 more)" in result.text
        # Exactly 5 filenames listed before the suffix
        text_before_suffix = result.text.split("(+")[0]
        assert text_before_suffix.count(".py") == 5

    def test_passed_no_text(self, rule: TestMirrorRule, tmp_path: Path) -> None:
        """Passed result (all modules tested) has text=None."""
        project = self._make_project(
            tmp_path,
            src_modules=["a.py", "b.py"],
            test_files=["test_a.py", "test_b.py"],
        )
        result = rule.check(project)
        assert result.text is None

    # --- Edge cases ---

    def test_exactly_five_missing_no_suffix(
        self, rule: TestMirrorRule, tmp_path: Path
    ) -> None:
        """Exactly 5 missing modules lists all without (+N more)."""
        project = self._make_project(
            tmp_path,
            src_modules=[f"mod{i}.py" for i in range(5)],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "(+" not in result.text
        assert result.text.count(".py") == 5

    def test_single_missing_no_truncation(
        self, rule: TestMirrorRule, tmp_path: Path
    ) -> None:
        """Single missing module: no truncation, just the filename."""
        project = self._make_project(
            tmp_path,
            src_modules=["utils.py"],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "\u2022 untested: utils.py" in result.text
        assert "(+" not in result.text

    def test_private_module_listed(self, rule: TestMirrorRule, tmp_path: Path) -> None:
        """Private module _facade.py appears in text."""
        project = self._make_project(
            tmp_path,
            src_modules=["_facade.py"],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "_facade.py" in result.text
