from __future__ import annotations

import pytest

from axm_ast.hooks.context import ContextHook


@pytest.fixture()
def hook():
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

    def test_hook_depth_zero_compact(self, hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = hook.execute(ctx, depth=0)

        assert result.success
        meta = result.metadata["project_context"]
        assert "top_modules" in meta
        assert "modules" not in meta

    def test_hook_depth_none_full(self, hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = hook.execute(ctx)

        assert result.success
        meta = result.metadata["project_context"]
        assert "modules" in meta
        assert "dependency_graph" in meta

    def test_hook_depth_one_packages(self, hook, _patch_context):
        ctx = {"working_dir": str(_patch_context)}
        result = hook.execute(ctx, depth=1)

        assert result.success
        meta = result.metadata["project_context"]
        assert "packages" in meta


@pytest.mark.usefixtures("_patch_context")
class TestContextHookEdgeCases:
    """Edge cases for backward compatibility."""

    def test_no_depth_defaults_to_full(self, hook, _patch_context):
        """No depth param defaults to None (full context) — backward compatible."""
        ctx = {"working_dir": str(_patch_context)}
        result = hook.execute(ctx)

        assert result.success
        meta = result.metadata["project_context"]
        assert "modules" in meta
        assert "dependency_graph" in meta

    def test_slim_param_ignored(self, hook, _patch_context):
        """Old slim param is silently ignored — no crash, no effect."""
        ctx = {"working_dir": str(_patch_context)}
        result = hook.execute(ctx, slim=True)

        assert result.success
        # After migration slim has no effect; depth defaults to None (full)
        meta = result.metadata["project_context"]
        assert "modules" in meta
        assert "dependency_graph" in meta
