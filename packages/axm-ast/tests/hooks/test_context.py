"""Unit tests for ContextHook."""

from pathlib import Path
from typing import Any

from axm_ast.hooks.context import ContextHook


def test_context_hook_returns_project_context(tmp_path: Path) -> None:
    """AC1: ast:context hook returns project context dict."""
    # Setup: a simple fixture package
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

    # We expect 'name' and 'patterns' to be in the project context
    project_context = result.metadata["project_context"]
    assert "name" in project_context
    assert project_context["name"] == "dummy_pkg"


def test_context_hook_slim_limits_depth(tmp_path: Path) -> None:
    """slim param is ignored after migration to depth — returns full context."""
    pkg_dir = tmp_path / "src" / "dummy_pkg"
    pkg_dir.mkdir(parents=True)

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "dummy_pkg"')
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "module1.py").write_text("def my_func(): pass")

    hook = ContextHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    # Call without depth
    full_result = hook.execute(ctx)
    assert full_result.success is True

    # Call with slim (ignored after migration — returns full context)
    slim_result = hook.execute(ctx, slim=True)
    assert slim_result.success is True

    # slim is silently ignored; output matches full context
    assert (
        slim_result.metadata["project_context"]
        == full_result.metadata["project_context"]
    )


def test_context_hook_missing_path_fails(tmp_path: Path) -> None:
    """AC1 (failure mode): No valid path param causes failure."""
    hook = ContextHook()
    ctx: dict[str, Any] = {"working_dir": str(tmp_path / "does_not_exist")}

    result = hook.execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "not a directory" in result.error
