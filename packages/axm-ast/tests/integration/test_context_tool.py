"""Split from ``test_coverage_gaps.py``."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.context import ContextHook
from axm_ast.tools.context import ContextTool
from tests.integration._helpers import _assert_tool_result


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestContextToolWorkspace:
    """Cover tools/context.py workspace branch (lines 56, 58-59)."""

    def test_workspace_context(self, tmp_path: Path, mocker: MagicMock) -> None:

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_context",
            return_value={"workspace": True, "packages": []},
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = ContextTool().execute(path=str(pkg))
        assert result.success is True
        assert result.data["workspace"] is True


class TestContextToolIntegration:
    """Tests for ast_context tool."""

    def test_execute_returns_tool_result(self, sample_project: Path) -> None:

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True

    def test_execute_has_name_key(self, sample_project: Path) -> None:

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert "name" in result.data

    # --- Depth 0 compact output ---

    def test_context_tool_depth0(self, sample_project: Path) -> None:
        """depth=0 returns compact data with top_modules."""

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), depth=0)
        assert result.success is True
        assert "top_modules" in result.data
        assert "modules" not in result.data

    def test_context_tool_default_unchanged(self, sample_project: Path) -> None:
        """AC4: default behavior unchanged (regression)."""

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # depth=1 (default) returns 'packages' grouping, not raw 'modules'
        assert "packages" in result.data
        assert "patterns" in result.data


class TestContextToolException:
    """ContextTool — exception handling."""

    def test_exception(self, simple_pkg: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.context import ContextTool

        mocker.patch(
            "axm_ast.core.context.build_context",
            side_effect=RuntimeError("ctx boom"),
        )
        result = ContextTool().execute(path=str(simple_pkg))
        assert result.success is False
        assert "ctx boom" in (result.error or "")


# ─── ContextTool ────────────────────────────────────────────────────────────


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def context_hook():
    return ContextHook()


def test_tool_returns_text_and_data() -> None:
    """ContextTool returns both structured data and text rendering."""
    tool = ContextTool()
    result = tool.execute(path=str(REPO), depth=1)
    assert result.success
    assert "name" in result.data
    assert "packages" in result.data
    assert result.text is not None
    assert "axm" in result.text.lower()


def test_text_token_count_lower() -> None:
    """Text rendering is more compact than JSON."""
    tool = ContextTool()
    result = tool.execute(path=str(REPO), depth=1)
    assert result.success
    json_str = json.dumps(result.data)
    assert result.text is not None
    text_tokens = len(result.text.split())
    json_tokens = len(json_str.split())
    assert text_tokens < json_tokens


def test_workspace() -> None:
    """ContextTool works on workspace root."""
    ws_path = Path(__file__).resolve().parent.parent.parent.parent
    tool = ContextTool()
    result = tool.execute(path=str(ws_path), depth=1)
    if not result.success:
        pytest.skip("workspace detection not available in test environment")
    assert result.text is not None
    assert "axm" in result.text.lower()


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_depth_none(tmp_path):
    """depth=None triggers full context with modules and dependency_graph."""
    result = ContextTool().execute(path=str(tmp_path), depth=None)
    assert result.success
    assert "modules" in result.data
    assert "dependency_graph" in result.data


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_explicit_depth_1_matches_default(tmp_path):
    """Explicit depth=1 produces the same output as omitting depth."""
    default_result = ContextTool().execute(path=str(tmp_path))
    explicit_result = ContextTool().execute(path=str(tmp_path), depth=1)
    assert default_result.data == explicit_result.data


def test_slim_param_ignored() -> None:
    """Calling ContextTool with slim=True produces same output as without."""
    tool = ContextTool()
    normal = tool.execute(path=str(REPO), depth=1)
    with_slim = tool.execute(path=str(REPO), depth=1, slim=True)
    assert normal.data == with_slim.data


@pytest.mark.usefixtures("_patch_context")
class TestContextHookDepth:
    """Verify depth parameter controls output granularity."""

    def test_hook_depth_zero_compact(self, context_hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = context_hook.execute(ctx, depth=0)

        assert result.success
        meta = result.metadata["project_context"]
        assert "top_modules" in meta
        assert "modules" not in meta

    def test_hook_depth_none_full(self, context_hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = context_hook.execute(ctx)

        assert result.success
        meta = result.metadata["project_context"]
        assert "modules" in meta
        assert "dependency_graph" in meta

    def test_hook_depth_one_packages(self, context_hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = context_hook.execute(ctx, depth=1)

        assert result.success
        meta = result.metadata["project_context"]
        assert "packages" in meta


@pytest.fixture()
def _mock_context(tmp_path):
    """Patch build_context and format_context_json."""
    sentinel_ctx = MagicMock(name="built_context")

    def _format(ctx, *, depth=1):
        if depth is None:
            return {
                "modules": ["mod_a", "mod_b"],
                "dependency_graph": {"mod_a": ["mod_b"]},
            }
        if depth == 0:
            return {"top_modules": ["mod_a"]}
        if depth == 1:
            return {"packages": ["pkg_a"]}
        return {"symbols": ["sym_a"]}

    with (
        patch("axm_ast.core.context.build_context", return_value=sentinel_ctx),
        patch("axm_ast.core.context.format_context_json", side_effect=_format),
    ):
        yield


@pytest.fixture()
def _no_workspace(tmp_path):
    """Patch detect_workspace to return None (single-package mode)."""
    with patch("axm_ast.core.workspace.detect_workspace", return_value=None) as mock:
        yield mock


@pytest.fixture()
def _patch_context(monkeypatch, tmp_path):
    """Patch lazy-loaded context functions so no real AST parsing runs."""
    import axm_ast.hooks.context as mod

    monkeypatch.setattr(mod, "detect_workspace", lambda _: None)
    monkeypatch.setattr(mod, "build_context", lambda _: {"dummy": True})
    monkeypatch.setattr(mod, "build_workspace_context", lambda _: {})

    def fake_format(ctx, *, depth=None):
        if depth == 0:
            return {"top_modules": ["mod_a", "mod_b"]}
        if depth == 1:
            return {"packages": ["pkg_a"]}
        return {"modules": {"mod_a": {}}, "dependency_graph": {"mod_a": []}}

    monkeypatch.setattr(mod, "format_context_json", fake_format)
    return tmp_path
