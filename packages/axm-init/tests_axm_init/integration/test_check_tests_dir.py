"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

import pytest

from axm_init.checks.structure import check_tests_dir


class TestCheckTestsDir:
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
        """AC1: legacy suites still report their missing pyramid level."""
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
        """AC1: legacy suites still report every absent pyramid level."""
        (tmp_path / "tests").mkdir()
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        details_text = "\n".join(r.details)
        assert "tests/unit/" in details_text
        assert "tests/integration/" in details_text
        assert "tests/e2e/" in details_text

    def test_check_tests_dir_fails_when_tests_dir_missing(self, tmp_path: Path) -> None:
        """AC1: missing suites name the package-specific canonical directory."""
        project = tmp_path / "demo-pkg"
        project.mkdir()
        r = check_tests_dir(project)
        assert r.passed is False
        assert r.message == "tests_demo_pkg/ directory not found"

    def test_check_tests_dir_passes_with_full_pyramid(self, tmp_path: Path) -> None:
        """AC1: the legacy tests/ layout remains supported."""
        tests = tmp_path / "tests"
        (tests / "unit").mkdir(parents=True)
        (tests / "integration").mkdir()
        (tests / "e2e").mkdir()
        (tests / "unit" / "test_example.py").write_text("def test_x() -> None: pass\n")
        r = check_tests_dir(tmp_path)
        assert r.passed is True
        assert r.weight == 3

    def test_check_tests_dir_passes_with_namespaced_suite(self, tmp_path: Path) -> None:
        """AC1: a migrated namespaced suite is resolved end to end."""
        project = tmp_path / "demo-pkg"
        tests = project / "tests_demo_pkg"
        for level in ("unit", "integration", "e2e"):
            (tests / level).mkdir(parents=True)
        (tests / "unit" / "test_example.py").write_text("def test_x() -> None: pass\n")
        result = check_tests_dir(project)
        assert result.passed is True
        assert result.weight == 3

    def test_check_tests_dir_fails_when_no_test_files(self, tmp_path: Path) -> None:
        """AC1: an empty legacy pyramid remains invalid."""
        tests = tmp_path / "tests"
        (tests / "unit").mkdir(parents=True)
        (tests / "integration").mkdir()
        (tests / "e2e").mkdir()
        r = check_tests_dir(tmp_path)
        assert r.passed is False
        assert "No test files found" in r.message

    def test_real_axm_init_migrated_suite_passes(self) -> None:
        """AC4: the real migrated axm-init package has no tests_dir failure."""
        package_root = Path(__file__).parents[2]
        result = check_tests_dir(package_root)
        assert result.passed is True

    def test_real_axm_forge_init_check_has_no_tests_dir_failure(self) -> None:
        """AC4: init_check emits no tests_dir failure for real axm-forge."""
        from axm_init.tools.check import InitCheckTool

        workspace_root = Path(__file__).parents[4]
        result = InitCheckTool().execute(
            path=str(workspace_root),
            category="structure",
        )
        assert result.success is True
        assert result.data is not None
        failures = result.data["failures"]
        assert all(failure["name"] != "structure.tests_dir" for failure in failures)
