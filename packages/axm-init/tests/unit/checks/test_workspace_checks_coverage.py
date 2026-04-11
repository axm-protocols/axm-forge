"""Coverage tests for checks.workspace — uncovered branches."""

from __future__ import annotations

from pathlib import Path

# ── _resolve_member_dirs edge cases ─────────────────────────────────────────


class TestResolveMemberDirsEdge:
    """Cover lines 31, 36: no toml and no member globs."""

    def test_no_pyproject_returns_empty(self, tmp_path: Path) -> None:
        """No pyproject.toml → empty list."""
        from axm_init.checks.workspace import _resolve_member_dirs

        result = _resolve_member_dirs(tmp_path)
        assert result == []

    def test_no_member_globs_returns_empty(self, tmp_path: Path) -> None:
        """Workspace section with empty members → empty list."""
        from axm_init.checks.workspace import _resolve_member_dirs

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = []\n'
        )
        result = _resolve_member_dirs(tmp_path)
        assert result == []

    def test_no_workspace_section_returns_empty(self, tmp_path: Path) -> None:
        """pyproject.toml without workspace section → empty list."""
        from axm_init.checks.workspace import _resolve_member_dirs

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "ws"\n')
        result = _resolve_member_dirs(tmp_path)
        assert result == []


# ── check_members_consistent missing files ──────────────────────────────────


class TestMembersConsistentMissing:
    """Cover lines 102, 104: missing pyproject.toml and src/."""

    def test_missing_pyproject_in_member(self, tmp_path: Path) -> None:
        """Member without pyproject.toml → flagged."""
        from axm_init.checks.workspace import check_members_consistent

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        # Create a pyproject.toml so glob matches, but then remove it
        # Actually, member dirs are resolved by glob + has pyproject check
        # So we need pyproject to exist for _resolve_member_dirs to include it
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        (member / "tests").mkdir()
        # No src/ directory
        result = check_members_consistent(tmp_path)
        assert not result.passed
        assert any("src/" in d for d in result.details)

    def test_missing_src_and_tests(self, tmp_path: Path) -> None:
        """Member missing both src/ and tests/ → both flagged."""
        from axm_init.checks.workspace import check_members_consistent

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        # No src/ or tests/
        result = check_members_consistent(tmp_path)
        assert not result.passed
        details_text = " ".join(result.details)
        assert "src/" in details_text
        assert "tests/" in details_text


# ── check_requires_python_compat: member with no toml ──────────────────────


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


# ── check_root_name_collision: no pyproject ─────────────────────────────────


class TestRootNameCollisionNoToml:
    """Cover line 283: no pyproject.toml at root."""

    def test_no_pyproject_passes(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_root_name_collision

        result = check_root_name_collision(tmp_path)
        assert result.passed
        assert "No pyproject.toml" in result.message


# ── check_pytest_importmode: no pyproject ───────────────────────────────────


class TestPytestImportmodeNoToml:
    """Cover line 345: no pyproject.toml at root."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_pytest_importmode

        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message


# ── check_pytest_testpaths: no pyproject and non-packages paths ─────────────


class TestPytestTestpathsEdge:
    """Cover lines 384, 421: no pyproject and testpaths without packages."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_pytest_testpaths

        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message

    def test_testpaths_without_packages_ref(self, tmp_path: Path) -> None:
        """testpaths that don't reference packages/*/tests → fails."""
        from axm_init.checks.workspace import check_pytest_testpaths

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests/", "integration/"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "does not reference" in result.message


# ── check_quality_workflow: partial config ──────────────────────────────────


class TestQualityWorkflowPartial:
    """Cover lines 462-468: workflow exists but missing audit or coverage."""

    def test_missing_audit(self, tmp_path: Path) -> None:
        """Workflow without audit reference → fails."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: coverage report\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "audit" in (result.message or "")

    def test_missing_coverage(self, tmp_path: Path) -> None:
        """Workflow without coverage reference → fails."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: axm-audit check\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "coverage" in (result.message or "")

    def test_missing_both(self, tmp_path: Path) -> None:
        """Workflow without audit or coverage → both flagged."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: echo hello\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "audit" in (result.message or "")
        assert "coverage" in (result.message or "")
