"""Split from ``test_nodes.py``."""

from pathlib import Path

from axm_ast.models.nodes import WorkspaceInfo


class TestWorkspaceInfo:
    """Tests for WorkspaceInfo model."""

    def test_create_empty(self) -> None:
        ws = WorkspaceInfo(name="my-ws", root=Path("/ws"))
        assert ws.name == "my-ws"
        assert len(ws.packages) == 0
        assert len(ws.package_edges) == 0
