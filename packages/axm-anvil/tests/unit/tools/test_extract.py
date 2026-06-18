from __future__ import annotations

from axm_anvil.core.plan import MovePlan, SharedHelperDetection
from axm_anvil.tools.extract import ExtractTool


def test_name_is_anvil_extract() -> None:
    """AC2: the tool exposes the ``anvil_extract`` registry name."""
    assert ExtractTool().name == "anvil_extract"


def test_execute_invalid_rename_json_returns_failure() -> None:
    """A malformed --rename JSON string yields ToolResult(success=False)
    before any extraction is attempted (path args are resolved in memory)."""
    result = ExtractTool().execute(
        path="/tmp/ws",
        symbols="Foo",
        from_file="src.py",
        to_file="dst.py",
        rename="{not json",
    )

    assert result.success is False
    assert result.error is not None
    assert "invalid JSON in rename" in result.error


def test_format_text_renders_shared_helpers_section() -> None:
    """A plan with detected shared helpers renders the Shared Helpers block."""
    plan = MovePlan(
        source_text_new="",
        target_text_new="",
        moved_names=["Foo"],
        shared_helpers_detected=[
            SharedHelperDetection(
                name="_h",
                used_by_moved=["Foo"],
                used_by_remaining=["Bar", "Baz"],
            )
        ],
    )

    text = ExtractTool()._format_text(plan, from_file="a.py", to_file="b.py")

    assert "Shared Helpers:" in text
    assert "_h (also used by: Bar, Baz)" in text


def test_format_text_renders_warnings_section() -> None:
    """A plan carrying warnings renders a dedicated Warnings section."""
    plan = MovePlan(
        source_text_new="",
        target_text_new="",
        moved_names=["Foo"],
        warnings=["ruff post-processing skipped"],
    )

    text = ExtractTool()._format_text(plan, from_file="a.py", to_file="b.py")

    assert "Warnings:" in text
    assert "  - ruff post-processing skipped" in text
