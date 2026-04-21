"""Functional tests for project context via Tool, Hook, and CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.context import ContextHook
from axm_ast.tools.context import ContextTool

pytestmark = pytest.mark.functional


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_pyproject(path: Path, deps: list[str], *, build: str = "hatchling") -> None:
    """Write a minimal pyproject.toml."""
    dep_lines = ", ".join(f'"{d}"' for d in deps)
    (path / "pyproject.toml").write_text(
        f"[project]\n"
        f'name = "testpkg"\n'
        f"dependencies = [{dep_lines}]\n"
        f"[build-system]\n"
        f'requires = ["{build}"]\n'
        f'build-backend = "{build}.build"\n'
    )


def _make_pkg(path: Path, *, modules: dict[str, str] | None = None) -> Path:
    """Create a minimal Python package."""
    pkg = path / "testpkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Test package."""\n')
    if modules:
        for name, content in modules.items():
            (pkg / name).write_text(content)
    return pkg


# ─── ContextTool ────────────────────────────────────────────────────────────


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def _no_workspace(tmp_path):
    """Patch detect_workspace to return None (single-package mode)."""
    with patch("axm_ast.core.workspace.detect_workspace", return_value=None) as mock:
        yield mock


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


# ─── ContextHook ────────────────────────────────────────────────────────────


@pytest.fixture()
def context_hook():
    return ContextHook()


@pytest.fixture()
def _patch_context(monkeypatch, tmp_path):
    """Patch lazy-loaded context functions so no real AST parsing runs."""
    import axm_ast.hooks.context as mod

    monkeypatch.setattr(mod, "detect_workspace", lambda _: None)
    monkeypatch.setattr(mod, "build_context", lambda _: {"dummy": True})

    def fake_format(ctx, *, depth=None):
        if depth == 0:
            return {"top_modules": ["mod_a", "mod_b"]}
        if depth == 1:
            return {"packages": ["pkg_a"]}
        return {"modules": {"mod_a": {}}, "dependency_graph": {"mod_a": []}}

    monkeypatch.setattr(mod, "format_context_json", fake_format)
    return tmp_path


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


def test_context_hook_returns_project_context(tmp_path: Path) -> None:
    """ContextHook returns project context with correct name."""
    pkg_dir = tmp_path / "src" / "dummy_pkg"
    pkg_dir.mkdir(parents=True)

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "dummy_pkg"')
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "module1.py").write_text("def my_func(): pass")
    (pkg_dir / "module2.py").write_text("class MyClass: pass")

    hook = ContextHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}
    result = hook.execute(ctx)

    assert result.success is True
    assert "project_context" in result.metadata
    project_context = result.metadata["project_context"]
    assert "name" in project_context
    assert project_context["name"] == "dummy_pkg"


def test_context_hook_slim_ignored(tmp_path: Path) -> None:
    """slim param is silently ignored — output matches full context."""
    pkg_dir = tmp_path / "src" / "dummy_pkg"
    pkg_dir.mkdir(parents=True)

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "dummy_pkg"')
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "module1.py").write_text("def my_func(): pass")

    hook = ContextHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    full_result = hook.execute(ctx)
    assert full_result.success is True

    slim_result = hook.execute(ctx, slim=True)
    assert slim_result.success is True

    assert (
        slim_result.metadata["project_context"]
        == full_result.metadata["project_context"]
    )


def test_context_hook_missing_path_fails(tmp_path: Path) -> None:
    """No valid path causes failure with descriptive error."""
    hook = ContextHook()
    ctx: dict[str, Any] = {"working_dir": str(tmp_path / "does_not_exist")}

    result = hook.execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "not a directory" in result.error


# ─── CLI ────────────────────────────────────────────────────────────────────


def test_context_cli_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI context command produces text output with package name."""
    from axm_ast.cli import app

    pkg = _make_pkg(tmp_path)
    _make_pyproject(tmp_path, ["cyclopts>=3.0"])
    with pytest.raises(SystemExit):
        app(["context", str(pkg)])
    captured = capsys.readouterr()
    assert "testpkg" in captured.out


def test_context_cli_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --json produces valid JSON with expected keys."""
    from axm_ast.cli import app

    pkg = _make_pkg(tmp_path)
    _make_pyproject(tmp_path, ["pydantic>=2.0"])
    with pytest.raises(SystemExit):
        app(["context", str(pkg), "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "name" in data
    assert "stack" in data
    assert "modules" in data
