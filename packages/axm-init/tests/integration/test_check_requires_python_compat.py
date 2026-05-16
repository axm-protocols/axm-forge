"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_requires_python_compat


class TestRequiresPythonCompat:
    """Tests for check_requires_python_compat."""

    def test_compatible(self, ws_root: Path) -> None:
        """All members >=3.12 passes."""
        result = check_requires_python_compat(ws_root)
        assert result.passed

    def test_conflict(self, ws_root: Path) -> None:
        """Different requires-python values fails."""
        pkg_b = ws_root / "packages" / "pkg-b"
        pkg_b.mkdir(parents=True)
        (pkg_b / "pyproject.toml").write_text(
            '[project]\nname = "pkg-b"\nrequires-python = ">=3.11,<3.12"\n'
        )
        result = check_requires_python_compat(ws_root)
        assert not result.passed
        assert "different" in result.message

    def test_no_requires_python(self, tmp_path: Path) -> None:
        """Members with no requires-python skipped."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        pkg = tmp_path / "packages" / "pkg-a"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_requires_python_compat(tmp_path)
        assert result.passed
        assert "No requires-python" in result.message


class TestRequiresPythonNoneName:
    """Cover line 224: continue when data is None for a member."""

    def test_member_with_unreadable_toml_skipped(self, tmp_path: Path) -> None:
        """Member with invalid TOML is skipped gracefully."""
        from axm_init.checks.workspace import check_requires_python_compat

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text("NOT VALID TOML {{{")
        result = check_requires_python_compat(tmp_path)
        # Should pass since no valid specs found
        assert result.passed
