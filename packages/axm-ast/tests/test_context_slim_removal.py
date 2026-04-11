from __future__ import annotations

from pathlib import Path

import yaml

from axm_ast.tools.context import ContextTool

REPO = Path(__file__).resolve().parents[1]


class TestContextToolDepth:
    """Unit tests for ContextTool depth behavior after slim removal."""

    def test_context_tool_depth0(self) -> None:
        """depth=0 produces compact output with top_modules, no modules key."""
        tool = ContextTool()
        result = tool.execute(path=str(REPO), depth=0)
        assert result.success
        assert "top_modules" in result.data
        assert "modules" not in result.data

    def test_context_tool_default_depth(self) -> None:
        """Default depth (1) produces output with packages key."""
        tool = ContextTool()
        result = tool.execute(path=str(REPO))
        assert result.success
        assert "packages" in result.data


class TestPlanTicketHook:
    """Functional test: protocol.yaml uses depth: 0, not slim."""

    def test_plan_ticket_hook_uses_depth0(self) -> None:
        """plan-ticket protocol should use depth: 0, not slim: true."""
        protocol_path = (
            Path.home() / "axm" / "protocols" / "plan-ticket" / "protocol.yaml"
        )
        assert protocol_path.exists(), f"Protocol file not found: {protocol_path}"
        raw = protocol_path.read_text()
        data = yaml.safe_load(raw)

        # Recursively find all dicts that reference ast_context
        found = _find_ast_context_params(data)
        assert found, "No ast_context hook found in plan-ticket protocol.yaml"

        for params in found:
            assert "slim" not in params, (
                f"slim param should be removed from ast_context params: {params}"
            )
            assert params.get("depth") == 0, (
                f"depth should be 0 in ast_context params: {params}"
            )


def _find_ast_context_params(obj: object) -> list[dict[str, object]]:
    """Walk YAML tree and collect params dicts for ast_context hooks."""
    results: list[dict[str, object]] = []
    if isinstance(obj, dict):
        if obj.get("action") == "ast:context":
            results.append(obj.get("params", {}))
        for v in obj.values():
            results.extend(_find_ast_context_params(v))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_ast_context_params(item))
    return results


class TestSlimParamRemoved:
    """Edge case: slim param no longer in explicit signature."""

    def test_slim_not_in_execute_signature(self) -> None:
        """slim is not an explicit parameter of ContextTool.execute."""
        import inspect

        sig = inspect.signature(ContextTool.execute)
        assert "slim" not in sig.parameters, (
            "slim should be removed from execute() signature"
        )
