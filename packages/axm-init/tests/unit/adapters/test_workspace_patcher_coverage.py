"""Coverage tests for adapters.workspace_patcher — uncovered paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.workspace_patcher import (
    _append_to_toml_array_lines,
    _detect_yaml_indent,
    _find_yaml_list_range,
    _insert_into_toml_array,
    _insert_into_yaml_list,
    patch_release,
)

# ── _detect_yaml_indent ─────────────────────────────────────────────────────


class TestDetectYamlIndent:
    """Cover line 148: fallback to default when no list items."""

    def test_no_list_items_returns_default(self) -> None:
        lines = ["key: value\n", "other: stuff\n"]
        result = _detect_yaml_indent(lines, default="    ")
        assert result == "    "

    def test_detects_existing_indent(self) -> None:
        lines = ["items:\n", "    - first\n", "    - second\n"]
        result = _detect_yaml_indent(lines)
        assert result == "    "


# ── _find_yaml_list_range ───────────────────────────────────────────────────


class TestFindYamlListRange:
    """Cover line 177: no list found returns None."""

    def test_no_list_returns_none(self) -> None:
        lines = ["key: value\n", "other: stuff\n"]
        result = _find_yaml_list_range(lines, None)
        assert result is None

    def test_with_marker_no_list_after(self) -> None:
        lines = ["tags:\n", "  nothing_here: true\n"]
        result = _find_yaml_list_range(lines, "tags:")
        assert result is None

    def test_finds_list_with_marker(self) -> None:
        lines = ["tags:\n", "  - v1\n", "  - v2\n", "jobs:\n"]
        result = _find_yaml_list_range(lines, "tags:")
        assert result == (1, 3)

    def test_finds_list_without_marker(self) -> None:
        lines = ["  - item1\n", "  - item2\n", "other:\n"]
        result = _find_yaml_list_range(lines, None)
        assert result == (0, 2)


# ── _insert_into_yaml_list ──────────────────────────────────────────────────


class TestInsertIntoYamlList:
    """Cover line 195: bounds is None → return original."""

    def test_no_bounds_returns_original(self) -> None:
        lines = ["key: value\n"]
        result = _insert_into_yaml_list(lines, "new-item", list_marker="tags:")
        assert result == ["key: value\n"]


# ── patch_release ───────────────────────────────────────────────────────────


class TestPatchRelease:
    """Cover lines 289-319: patch_release function."""

    @pytest.fixture()
    def release_root(self, tmp_path: Path) -> Path:
        """Workspace root with a release.yml."""
        ci_dir = tmp_path / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "release.yml").write_text(
            "name: Release\n\non:\n  push:\n    tags:\n"
            '      - "v*"\n\njobs:\n  release:\n'
            "    steps:\n"
            "      - name: detect\n"
            "        run: |\n"
            "          TAG=${GITHUB_REF#refs/tags/}\n"
            '          if [[ "$TAG" == v* ]]; then\n'
            '            echo "package=root" >> "$GITHUB_OUTPUT"\n'
            "          else\n"
            '            echo "unknown tag"\n'
            "          fi\n"
        )
        return tmp_path

    def test_adds_tag_and_detect_block(self, release_root: Path) -> None:
        """patch_release adds tag pattern and detect elif block."""
        patch_release(release_root, "my-lib")
        content = (release_root / ".github" / "workflows" / "release.yml").read_text()
        assert "my-lib/v*" in content
        assert 'elif [[ "$TAG" == my-lib/* ]]' in content
        assert "package=my-lib" in content
        assert "package-dir=packages/my-lib" in content

    def test_idempotent(self, release_root: Path) -> None:
        """Calling patch_release twice produces same content."""
        patch_release(release_root, "my-lib")
        content1 = (release_root / ".github" / "workflows" / "release.yml").read_text()
        patch_release(release_root, "my-lib")
        content2 = (release_root / ".github" / "workflows" / "release.yml").read_text()
        assert content1 == content2

    def test_missing_release_yml_raises(self, tmp_path: Path) -> None:
        """Missing release.yml raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            patch_release(tmp_path, "my-lib")

    def test_no_else_block(self, tmp_path: Path) -> None:
        """release.yml without 'else' only adds tag pattern."""
        ci_dir = tmp_path / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "release.yml").write_text(
            "name: Release\n\non:\n  push:\n    tags:\n"
            '      - "v*"\n\njobs:\n  release:\n'
            "    steps:\n      - checkout\n"
        )
        patch_release(tmp_path, "my-lib")
        content = (ci_dir / "release.yml").read_text()
        assert "my-lib/v*" in content
        assert "elif" not in content

    def test_no_tags_section(self, tmp_path: Path) -> None:
        """release.yml without 'tags:' section skips tag insertion."""
        ci_dir = tmp_path / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "release.yml").write_text(
            "name: Release\n\njobs:\n  release:\n"
            "    steps:\n"
            "          else\n"
            "            echo done\n"
        )
        patch_release(tmp_path, "my-lib")
        content = (ci_dir / "release.yml").read_text()
        assert "elif" in content


# ── pyproject patching with sources marker ──────────────────────────────────


class TestPatchPyprojectWithSources:
    """Cover line 115: deps_section split by [tool.uv.sources]."""

    def test_dep_already_in_sources_section_not_deps(self, tmp_path: Path) -> None:
        """Member name appears after sources marker → still adds to deps."""
        from axm_init.adapters.workspace_patcher import patch_pyproject

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "ws"\nversion = "0.1.0"\n\n'
            'dependencies = [\n    "existing-pkg",\n]\n\n'
            "[tool.uv.sources]\n"
            "[tool.uv.sources.existing-pkg]\nworkspace = true\n"
        )
        patch_pyproject(tmp_path, "new-lib")
        content = pyproject.read_text()
        assert '"new-lib"' in content
        assert "[tool.uv.sources.new-lib]" in content


# ── _insert_into_toml_array edge cases ──────────────────────────────────────


class TestInsertIntoTomlArray:
    """Cover lines 336, 339: section missing or key missing."""

    def test_section_missing_creates_full_block(self) -> None:
        content = '[project]\nname = "ws"\n'
        result = _insert_into_toml_array(content, "packages/new/tests")
        assert "[tool.pytest.ini_options]" in result
        assert '"packages/new/tests"' in result

    def test_section_exists_key_missing(self) -> None:
        content = (
            '[project]\nname = "ws"\n\n'
            '[tool.pytest.ini_options]\nimport_mode = "importlib"\n'
        )
        result = _insert_into_toml_array(content, "packages/new/tests")
        assert '"packages/new/tests"' in result
        assert "[tool.pytest.ini_options]" in result


class TestAppendToTomlArrayLines:
    """Cover lines 359-366: single-line array handling."""

    def test_single_line_array(self) -> None:
        content = 'testpaths = ["packages/a/tests"]\n'
        result = _append_to_toml_array_lines(content, "packages/b/tests", "testpaths")
        assert '"packages/a/tests"' in result
        assert '"packages/b/tests"' in result
        assert "]" in result

    def test_multi_line_array(self) -> None:
        content = 'testpaths = [\n    "packages/a/tests",\n]\n'
        result = _append_to_toml_array_lines(content, "packages/b/tests", "testpaths")
        assert '"packages/b/tests"' in result
