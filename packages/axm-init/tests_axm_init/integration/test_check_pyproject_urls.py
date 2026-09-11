"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.pyproject import check_pyproject_urls


class TestCheckPyprojectUrls:
    @pytest.mark.parametrize(
        ("use_gold", "expected"),
        [
            pytest.param(True, True, id="pass"),
            pytest.param(False, False, id="fail_missing_section"),
        ],
    )
    def test_urls(
        self,
        gold_project: Path,
        tmp_path: Path,
        use_gold: bool,
        expected: bool,
    ) -> None:
        if use_gold:
            project = gold_project
        else:
            (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
            project = tmp_path
        r = check_pyproject_urls(project)
        assert r.passed is expected

    def test_fail_partial_urls(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[project.urls]\nHomepage = "h"\nRepository = "r"\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False
        assert "Documentation" in str(r.details) or "Issues" in str(r.details)

    @staticmethod
    def _write(tmp_path: Path, *, private: bool, homepage: str) -> Path:
        classifiers = '"Private :: Do Not Upload"' if private else ""
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "x"\nclassifiers = [{classifiers}]\n'
            f"[project.urls]\n"
            f'Homepage = "{homepage}"\n'
            f'Documentation = "https://example.invalid/docs"\n'
            f'Repository = "https://example.invalid/repo"\n'
            f'Issues = "https://example.invalid/issues"\n'
        )
        return tmp_path

    def test_private_package_rejects_pypi_url(self, tmp_path: Path) -> None:
        """A private package advertises a distribution that will never exist."""
        project = self._write(
            tmp_path,
            private=True,
            homepage="https://pypi.org/project/x/",
        )
        r = check_pyproject_urls(project)
        assert r.passed is False
        assert "Homepage" in str(r.details)

    @pytest.mark.parametrize(
        ("private", "homepage"),
        [
            pytest.param(
                False,
                "https://pypi.org/project/x/",
                id="published_package_may_link_pypi",
            ),
            pytest.param(
                True,
                "https://example.invalid/repo",
                id="private_package_without_pypi_url",
            ),
        ],
    )
    def test_private_url_rule_stays_narrow(
        self,
        tmp_path: Path,
        private: bool,
        homepage: str,
    ) -> None:
        """Only the private+PyPI combination is a contradiction."""
        project = self._write(tmp_path, private=private, homepage=homepage)
        assert check_pyproject_urls(project).passed is True
