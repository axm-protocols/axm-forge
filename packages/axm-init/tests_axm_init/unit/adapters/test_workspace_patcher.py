"""Unit tests for workspace_patcher pure helpers (in-memory, no I/O)."""

from __future__ import annotations

from axm_init.adapters.workspace_patcher import (
    _append_to_toml_array_lines,
    _find_top_level_key_index,
    _find_yaml_list_range,
    _insert_into_yaml_list,
)


class TestInsertIntoYamlListChangeReporting:
    """_insert_into_yaml_list reports whether it changed the buffer (AC1)."""

    def test_marker_absent_reports_no_change_and_leaves_lines_intact(self) -> None:
        lines = ["nav:\n", "  - Home: index.md\n"]

        result, changed = _insert_into_yaml_list(
            lines, "my-lib", list_marker="nonexistent:"
        )

        assert changed is False
        assert result == lines

    def test_marker_present_reports_change_and_inserts_item(self) -> None:
        lines = ["package:\n", "          - existing\n"]

        result, changed = _insert_into_yaml_list(
            lines, "my-lib", list_marker="package:"
        )

        assert changed is True
        assert any("my-lib" in line for line in result)


class TestAppendTomlArrayExactKey:
    """_append_to_toml_array_lines matches the exact key token (AC2)."""

    def test_testpaths_extra_not_matched_for_testpaths(self) -> None:
        content = (
            "[tool.pytest.ini_options]\n"
            'testpaths_extra = ["packages/decoy/tests"]\n'
            'testpaths = [\n    "packages/a/tests",\n]\n'
        )

        result = _append_to_toml_array_lines(content, "packages/new/tests", "testpaths")

        # testpaths_extra decoy is untouched; new entry lands in testpaths.
        assert 'testpaths_extra = ["packages/decoy/tests"]\n' in result
        assert '    "packages/new/tests",\n' in result

    def test_single_line_exact_key_ignores_prefix_collision(self) -> None:
        content = 'testpaths = ["a"]\ntestpaths_extra = ["b"]\n'

        result = _append_to_toml_array_lines(content, "c", "testpaths")

        assert '"c"' in result
        assert 'testpaths_extra = ["b"]\n' in result


class TestFindTopLevelKeyIndex:
    """_find_top_level_key_index anchors on the real top-level key (AC1)."""

    def test_skips_comment_and_indented_lines(self) -> None:
        lines = [
            "# jobs: decoy comment\n",
            "on:\n",
            "  jobs: indented not top level\n",
            "jobs:\n",
            "  build:\n",
        ]

        assert _find_top_level_key_index(lines, "jobs") == 3

    def test_returns_none_when_absent(self) -> None:
        lines = ["# jobs: only a decoy\n", "steps:\n", "  - run: echo hi\n"]

        assert _find_top_level_key_index(lines, "jobs") is None


class TestInlineYamlList:
    """Inline YAML matrix sequences are resolved and updated in place."""

    def test_marker_line_is_the_target_instead_of_later_steps(self) -> None:
        """AC1: an inline marker resolves itself, never a later steps list."""
        lines = [
            "jobs:\n",
            "  test:\n",
            "    strategy:\n",
            "      matrix:\n",
            "        package: [axm-a, axm-b]\n",
            "    steps:\n",
            "      - uses: actions/checkout@v6\n",
        ]
        marker_index = 4

        bounds = _find_yaml_list_range(lines, "package:")

        assert bounds == (marker_index, marker_index + 1)
        assert bounds[1] <= lines.index("    steps:\n")

    def test_insertion_changes_only_inline_marker_line(self) -> None:
        """AC2: insertion extends the inline sequence and preserves all else."""
        lines = [
            "jobs:\n",
            "  test:\n",
            "    strategy:\n",
            "      matrix:\n",
            "        package: [axm-a, axm-b]\n",
            "    steps:\n",
            "      - uses: actions/checkout@v6\n",
        ]
        marker_index = 4

        result, changed = _insert_into_yaml_list(lines, "axm-c", list_marker="package:")

        assert changed is True
        assert result[marker_index] == "        package: [axm-a, axm-b, axm-c]\n"
        assert result[:marker_index] == lines[:marker_index]
        assert result[marker_index + 1 :] == lines[marker_index + 1 :]
