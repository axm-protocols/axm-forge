"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

import pytest

from axm_init.checks.structure import check_tests_dir


class TestCheckTestsDir:
    def test_pass(self, gold_project: Path) -> None:
        r = check_tests_dir(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_tests_dir(empty_project)
        assert r.passed is False

    @pytest.mark.parametrize(
        ("present", "missing"),
        [
            pytest.param(("integration", "e2e"), "unit", id="unit_missing"),
            pytest.param(("unit", "e2e"), "integration", id="integration_missing"),
            pytest.param(("unit", "integration"), "e2e", id="e2e_missing"),
        ],
    )
    def test_check_tests_dir_fails_when_subdir_missing(
        self, tmp_path: Path, present: tuple[str, str], missing: str
    ) -> None:
        tests = tmp_path / "tests"
        tests.mkdir()
        for sub in present:
            (tests / sub).mkdir()
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        assert f"tests/{missing}/" in r.fix

    def test_check_tests_dir_fails_when_all_subdirs_missing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "tests").mkdir()
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        details_text = "\n".join(r.details)
        assert "tests/unit/" in details_text
        assert "tests/integration/" in details_text
        assert "tests/e2e/" in details_text

    def test_check_tests_dir_fails_when_tests_dir_missing(self, tmp_path: Path) -> None:
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        assert r.message == "tests/ directory not found"

    def test_check_tests_dir_passes_with_full_pyramid(self, tmp_path: Path) -> None:
        tests = tmp_path / "tests"
        (tests / "unit").mkdir(parents=True)
        (tests / "integration").mkdir()
        (tests / "e2e").mkdir()
        (tests / "unit" / "test_example.py").write_text("def test_x() -> None: pass\n")
        r = check_tests_dir(tmp_path)
        assert r.passed is True
        assert r.weight == 3

    def test_check_tests_dir_fails_when_no_test_files(self, tmp_path: Path) -> None:
        tests = tmp_path / "tests"
        (tests / "unit").mkdir(parents=True)
        (tests / "integration").mkdir()
        (tests / "e2e").mkdir()
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        assert "No test files found" in r.message
