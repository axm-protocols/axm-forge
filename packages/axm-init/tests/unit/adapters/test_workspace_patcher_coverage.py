"""Coverage tests for adapters.workspace_patcher — uncovered paths."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from axm_init.adapters.workspace_patcher import (
    patch_ci,
    patch_publish,
    patch_release,
    patch_testpaths,
)

# ── YAML helper edge cases (covered via public patch_publish) ───────────────


class TestYamlHelperEdgeCases:
    """Edge cases in YAML list handling, exercised via patch_publish."""

    def _publish_with(self, root: Path, body: str) -> Path:
        """Write a minimal publish.yml under *root* with the given body."""
        publish_yml = root / ".github" / "workflows" / "publish.yml"
        publish_yml.parent.mkdir(parents=True, exist_ok=True)
        publish_yml.write_text(body)
        return publish_yml

    def test_marker_present_but_no_list_items(self, tmp_path: Path) -> None:
        """`tags:` marker present but no `- ` items → original is preserved."""
        body = (
            "name: Publish\n\n"
            "on:\n  push:\n    tags:\n      nothing_here: true\n\n"
            "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v6\n"
        )
        publish_yml = self._publish_with(tmp_path, body)
        patch_publish(tmp_path, "my-lib")
        content = publish_yml.read_text()
        assert "nothing_here: true" in content

    def test_no_tags_marker_creates_section(self, tmp_path: Path) -> None:
        """No `tags:` in publish.yml → push.tags trigger is created."""
        body = (
            "name: Publish\n\n"
            "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v6\n"
        )
        publish_yml = self._publish_with(tmp_path, body)
        patch_publish(tmp_path, "my-lib")
        content = publish_yml.read_text()
        assert '"my-lib/v*"' in content
        assert "push:" in content
        assert "tags:" in content

    def test_existing_tags_with_default_indent(self, tmp_path: Path) -> None:
        """Existing tags list → indent is detected from the last item."""
        body = (
            "name: Publish\n\n"
            "on:\n  push:\n    tags:\n"
            '      - "existing/v*"\n\n'
            "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v6\n"
        )
        publish_yml = self._publish_with(tmp_path, body)
        patch_publish(tmp_path, "my-lib")
        content = publish_yml.read_text()
        assert '      - "existing/v*"' in content
        assert '      - "my-lib/v*"' in content


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


# ── TOML array edge cases (covered via public patch_testpaths) ──────────────


class TestTomlArrayEdgeCases:
    """Edge cases in TOML array handling, exercised via patch_testpaths."""

    def test_section_exists_key_missing(self, tmp_path: Path) -> None:
        """Section exists without testpaths key → key is added with array."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "ws"\n\n'
            '[tool.pytest.ini_options]\nimport_mode = "importlib"\n'
        )
        patch_testpaths(tmp_path, "new-pkg")
        result = pyproject.read_text()
        assert '"packages/new-pkg/tests"' in result
        assert "[tool.pytest.ini_options]" in result
        assert 'import_mode = "importlib"' in result

    def test_single_line_array(self, tmp_path: Path) -> None:
        """Existing single-line testpaths array → entry appended in-place."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "ws"\n\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/a/tests"]\n'
        )
        patch_testpaths(tmp_path, "b")
        result = pyproject.read_text()
        assert '"packages/a/tests"' in result
        assert '"packages/b/tests"' in result


# ── YAML safety regression tests ────────────────────────────────────────────
#
# Regression coverage for a bug where `_find_yaml_list_range` captured
# `- ` items past the target list (e.g. items inside `steps:`), causing
# `patch_ci` / `patch_publish` / `patch_release` to insert the new entry
# inside the wrong block and produce unparseable YAML.


class TestYamlSafetyRegression:
    """Patchers must produce valid YAML and insert into the correct list."""

    def _make_realistic_ci(self, root: Path) -> Path:
        """Create a CI workflow that mirrors the shape of real axm workflows.

        Includes a ``matrix.package`` list *and* a subsequent ``steps:``
        block with its own ``- `` items — the exact shape that triggered
        the original regression.
        """
        ci = root / ".github" / "workflows" / "ci.yml"
        ci.parent.mkdir(parents=True, exist_ok=True)
        ci.write_text(
            "name: CI\n\n"
            "on:\n  push:\n    branches: [main]\n\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    strategy:\n"
            "      fail-fast: false\n"
            "      matrix:\n"
            "        package:\n"
            "          - existing-pkg\n"
            "          - another-pkg\n"
            '        python-version: ["3.12", "3.13"]\n'
            "    steps:\n"
            "      - uses: actions/checkout@v6\n"
            "      - uses: astral-sh/setup-uv@v7\n"
            "      - run: uv sync --all-groups\n"
            "      - name: Test ${{ matrix.package }}\n"
            "        run: uv run pytest --cov\n"
        )
        return ci

    def _make_realistic_publish(self, root: Path) -> Path:
        """Create a publish workflow mirroring real axm workflows."""
        publish = root / ".github" / "workflows" / "publish.yml"
        publish.parent.mkdir(parents=True, exist_ok=True)
        publish.write_text(
            "name: Publish to PyPI\n\n"
            "on:\n  push:\n    tags:\n"
            '      - "existing-pkg/v*"\n'
            '      - "another-pkg/v*"\n\n'
            "jobs:\n"
            "  publish:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v6\n"
            "      - uses: astral-sh/setup-uv@v7\n"
            "      - run: uv build\n"
            "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
        )
        return publish

    def _make_realistic_release(self, root: Path) -> Path:
        """Create a release workflow mirroring real axm workflows."""
        release = root / ".github" / "workflows" / "release.yml"
        release.parent.mkdir(parents=True, exist_ok=True)
        release.write_text(
            "name: Release\n\n"
            "on:\n  push:\n    tags:\n"
            '      - "existing-pkg/v*"\n\n'
            "permissions:\n  contents: write\n\n"
            "jobs:\n"
            "  release:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v6\n"
            "      - name: Detect package from tag\n"
            "        id: detect\n"
            "        run: |\n"
            "          TAG=${GITHUB_REF#refs/tags/}\n"
            '          if [[ "$TAG" == existing-pkg/* ]]; then\n'
            '            echo "package=existing-pkg" >> "$GITHUB_OUTPUT"\n'
            "          else\n"
            '            echo "::error::Unknown tag"\n'
            "            exit 1\n"
            "          fi\n"
            "      - name: Create GitHub Release\n"
            "        uses: softprops/action-gh-release@v2\n"
        )
        return release

    def test_patch_ci_keeps_yaml_parseable(self, tmp_path: Path) -> None:
        """patch_ci produces a dict with the expected CI job structure."""
        ci = self._make_realistic_ci(tmp_path)
        patch_ci(tmp_path, "my-lib")
        parsed = yaml.safe_load(ci.read_text())
        assert isinstance(parsed, dict)
        assert "jobs" in parsed
        assert "test" in parsed["jobs"]

    def test_patch_ci_inserts_into_matrix_not_steps(self, tmp_path: Path) -> None:
        """Inserted entry ends up in ``matrix.package``, never in ``steps``."""
        ci = self._make_realistic_ci(tmp_path)
        patch_ci(tmp_path, "my-lib")
        parsed = yaml.safe_load(ci.read_text())
        matrix_packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
        assert "my-lib" in matrix_packages
        assert matrix_packages == ["existing-pkg", "another-pkg", "my-lib"]
        # Steps must remain untouched — no "my-lib" string anywhere in them.
        steps = parsed["jobs"]["test"]["steps"]
        for step in steps:
            assert "my-lib" not in str(step)

    def test_patch_publish_keeps_yaml_parseable(self, tmp_path: Path) -> None:
        """patch_publish produces a dict with tag-push trigger + publish job."""
        publish = self._make_realistic_publish(tmp_path)
        patch_publish(tmp_path, "my-lib")
        parsed = yaml.safe_load(publish.read_text())
        assert isinstance(parsed, dict)
        assert True in parsed and "push" in parsed[True]
        assert "jobs" in parsed and "publish" in parsed["jobs"]

    def test_patch_publish_inserts_into_tags_not_steps(self, tmp_path: Path) -> None:
        """Tag pattern goes into ``on.push.tags``, never into ``steps``."""
        publish = self._make_realistic_publish(tmp_path)
        patch_publish(tmp_path, "my-lib")
        parsed = yaml.safe_load(publish.read_text())
        # YAML 1.1: bare `on:` parses as the boolean key True, not "on".
        tags = parsed[True]["push"]["tags"]
        assert "my-lib/v*" in tags
        steps = parsed["jobs"]["publish"]["steps"]
        for step in steps:
            assert "my-lib/v*" not in str(step)

    def test_patch_release_keeps_yaml_parseable(self, tmp_path: Path) -> None:
        """patch_release produces a dict with tag-push trigger + release job."""
        release = self._make_realistic_release(tmp_path)
        patch_release(tmp_path, "my-lib")
        parsed = yaml.safe_load(release.read_text())
        assert isinstance(parsed, dict)
        assert True in parsed and "push" in parsed[True]
        assert "jobs" in parsed and "release" in parsed["jobs"]

    def test_patch_release_inserts_into_tags_not_steps(self, tmp_path: Path) -> None:
        """Release tag goes into ``on.push.tags``, not between ``steps``."""
        release = self._make_realistic_release(tmp_path)
        patch_release(tmp_path, "my-lib")
        parsed = yaml.safe_load(release.read_text())
        # YAML 1.1: bare `on:` parses as the boolean key True, not "on".
        tags = parsed[True]["push"]["tags"]
        assert "my-lib/v*" in tags
        steps = parsed["jobs"]["release"]["steps"]
        for step in steps:
            # The tag pattern must not leak into any step.
            assert '"my-lib/v*"' not in str(step)

    @pytest.mark.parametrize("member", ["lib-one", "lib-two", "lib-three"])
    def test_patch_ci_repeated_calls_keep_yaml_valid(
        self, tmp_path: Path, member: str
    ) -> None:
        """Sequential patches for multiple members stay parseable."""
        self._make_realistic_ci(tmp_path)
        for m in ["lib-one", "lib-two", "lib-three"]:
            patch_ci(tmp_path, m)
            if m == member:
                break
        parsed = yaml.safe_load(
            (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
        )
        packages = parsed["jobs"]["test"]["strategy"]["matrix"]["package"]
        assert member in packages
