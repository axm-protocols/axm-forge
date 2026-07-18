"""Unit tests for workspace_patcher pure helpers (in-memory, no I/O)."""

from __future__ import annotations

from axm_init.adapters.workspace_patcher import _insert_into_yaml_list


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
