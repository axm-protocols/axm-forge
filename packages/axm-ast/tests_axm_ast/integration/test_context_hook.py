"""Split from ``test_project_context.py``."""

from pathlib import Path
from typing import Any

from axm_ast.hooks.context import ContextHook


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
