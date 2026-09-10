"""Coverage tests for tools.check — error and success paths in execute."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_init.core.checker import CheckEngine
from axm_init.core.protocol_planner import plan_protocol_scaffold
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl
from axm_init.tools.check import InitCheckTool

__all__: list[str] = []


@pytest.mark.integration
def test_exposer_etat_brouillon_dans_les_donnees(tmp_path: Path) -> None:
    """AC5: expose declared state independently of registration compliance.

    The dedicated protocols inventory associates graph_name with state,
    validated and executable, including a ready but unregistered protocol.
    """
    declaration = ProtocolScaffoldDecl(
        domain="demo", unit="work", action="exec", contracts=[], nodes=[]
    )
    plan = plan_protocol_scaffold(
        declaration,
        '[project]\nname = "protocols-demo"\nversion = "0.1.0"\n',
        {},
    )
    inventories = {}
    for state in ("draft", "ready"):
        project = tmp_path / state
        project.mkdir()
        (project / "pyproject.toml").write_text(
            plan.metadata.replace('state = "draft"', f'state = "{state}"'),
            encoding="utf-8",
        )
        for operation in plan.operations:
            assert operation.content is not None
            target = project / operation.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                operation.content.replace("# axm-init: incomplete-skeleton\n", ""),
                encoding="utf-8",
            )
        (project / "src/protocols_demo/work/exec/protocol.py").write_text(
            "from __future__ import annotations\n"
            "from axm_loom import protocol\n"
            "__all__ = ['build_protocol']\n"
            "GRAPH_NAME = 'demo.work.exec'\n"
            "def build_protocol():\n"
            "    return protocol('demo.work.exec', [])\n",
            encoding="utf-8",
        )
        result = InitCheckTool().execute(
            path=str(project), category="protocols", agent=True
        )
        assert result.data is not None
        assert "protocols" in result.data, result.data
        inventory = result.data["protocols"]
        assert isinstance(inventory, list)
        assert len(inventory) == 1
        entry = inventory[0]
        assert entry["graph_name"] == "demo.work.exec"
        assert entry["state"] == state
        assert entry["validated"] is False
        assert entry["executable"] is False
        inventories[state] = entry
        checks = CheckEngine(project, category="protocols").run().checks
        draft_check = next(c for c in checks if c.name == "protocols.protocol_draft")
        assert draft_check.passed
        if state == "draft":
            assert draft_check.weight == 0
            assert draft_check.earned == 0
        else:
            registration = next(
                c for c in checks if c.name == "protocols.protocol_registration"
            )
            assert not registration.passed
    assert inventories["draft"]["state"] != inventories["ready"]["state"]


class TestCheckExecuteErrorPath:
    """Cover lines 40, 49-50: not-a-directory and exception handling."""

    def test_nonexistent_path_returns_error(self, tmp_path: Path) -> None:
        """Path that does not exist → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        fake = tmp_path / "does-not-exist"
        result = tool.execute(path=str(fake))
        assert result.success is False
        assert "Not a directory" in (result.error or "")

    def test_file_path_returns_error(self, tmp_path: Path) -> None:
        """Path pointing to a file (not dir) → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        f = tmp_path / "file.txt"
        f.write_text("content")
        tool = InitCheckTool()
        result = tool.execute(path=str(f))
        assert result.success is False
        assert "Not a directory" in (result.error or "")

    def test_check_engine_exception_caught(self, tmp_path: Path) -> None:
        """Exception from CheckEngine → ToolResult(success=False)."""
        from axm_init.tools.check import InitCheckTool

        tool = InitCheckTool()
        with patch(
            "axm_init.core.checker.CheckEngine",
            side_effect=RuntimeError("engine failure"),
        ):
            result = tool.execute(path=str(tmp_path))
        assert result.success is False
        assert "engine failure" in (result.error or "")
