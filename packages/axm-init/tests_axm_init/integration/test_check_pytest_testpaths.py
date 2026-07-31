"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_pytest_testpaths


class TestPytestTestpaths:
    """Tests for check_pytest_testpaths."""

    @staticmethod
    def _create_member(root: Path, name: str, suite_name: str | None) -> Path:
        member = root / "packages" / name
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
        if suite_name is not None:
            (member / suite_name).mkdir()
        return member

    def test_testpaths_present(self, tmp_path: Path) -> None:
        """AC2: every existing member suite covered by testpaths passes."""
        self._create_member(tmp_path, "pkg-a", "tests_pkg_a")
        self._create_member(tmp_path, "pkg-b", "tests_pkg_b")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/pkg-a/tests_pkg_a", '
            '"packages/pkg-b/tests_pkg_b"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert result.passed

    def test_missing_member_suite_is_named(self, tmp_path: Path) -> None:
        """AC2: incomplete testpaths fail and identify each uncovered member."""
        self._create_member(tmp_path, "pkg-a", "tests_pkg_a")
        self._create_member(tmp_path, "pkg-b", "tests_pkg_b")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/pkg-a/tests_pkg_a"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        rendered = "\n".join([result.message, *result.details, result.fix])
        assert "pkg-b" in rendered
        assert "tests_pkg_b" in rendered

    def test_member_without_suite_is_ignored(self, tmp_path: Path) -> None:
        """AC2: suite-less workspace members do not create false failures."""
        self._create_member(tmp_path, "pkg-a", "tests_pkg_a")
        self._create_member(tmp_path, "pkg-b", None)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/pkg-a/tests_pkg_a"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert result.passed

    def test_testpaths_missing(self, ws_root: Path) -> None:
        """AC2: no testpaths configuration fails."""
        result = check_pytest_testpaths(ws_root)
        assert not result.passed
        assert "testpaths" in result.message.lower()


class TestPytestTestpathsEdge:
    """Edge contracts for workspace suite coverage and uniqueness."""

    @staticmethod
    def _create_member(root: Path, name: str, suite_name: str) -> None:
        member = root / "packages" / name
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
        (member / suite_name).mkdir()

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        """AC2: a workspace without pyproject cannot define coverage."""
        from axm_init.checks.workspace import check_pytest_testpaths

        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message

    def test_testpaths_without_packages_ref(self, tmp_path: Path) -> None:
        """AC2: unrelated testpaths do not cover member suites."""
        from axm_init.checks.workspace import check_pytest_testpaths

        self._create_member(tmp_path, "pkg-a", "tests_pkg_a")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests/", "integration/"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "does not cover" in result.message

    def test_duplicate_suite_names_report_both_members(self, tmp_path: Path) -> None:
        """AC3: collisions report the suite name and every owning member."""
        from axm_init.checks.workspace import check_suite_dir_uniqueness

        self._create_member(tmp_path, "pkg-a", "tests")
        self._create_member(tmp_path, "pkg-b", "tests")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_suite_dir_uniqueness(tmp_path)
        assert not result.passed
        rendered = "\n".join([result.message, *result.details, result.fix])
        assert "tests" in rendered
        assert "pkg-a" in rendered
        assert "pkg-b" in rendered

    def test_distinct_suite_names_pass(self, tmp_path: Path) -> None:
        """AC3: package-specific suite names are unique and pass."""
        from axm_init.checks.workspace import check_suite_dir_uniqueness

        self._create_member(tmp_path, "pkg-a", "tests_pkg_a")
        self._create_member(tmp_path, "pkg-b", "tests_pkg_b")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_suite_dir_uniqueness(tmp_path)
        assert result.passed
