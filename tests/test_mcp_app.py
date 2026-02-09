"""Tests for FastMCP integration (TDD)."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from axm_mcp import mcp_app
from axm.runtime.errors import (
    InvalidURIError,
    SessionNotFoundError,
)


@pytest.fixture
def configured_mcp(tmp_path: Path) -> None:
    """Configure MCP with mock catalog."""
    catalog = Mock()
    
    # Mock Protocol with phases
    protocol_mock = Mock(name="test_protocol")
    protocol_mock.name = "test"
    protocol_mock.version = "1.0"
    protocol_mock.description = "Test protocol"
    protocol_mock.context = None  # No protocol-level context
    
    phase_mock = Mock(name="test_phase")
    phase_mock.tasks = ["t"]
    phase_mock.gate = None
    phase_mock.artifact = None
    
    protocol_mock.phases = {"wf": phase_mock}
    catalog.get_protocol.return_value = protocol_mock
    catalog.load_protocol.return_value = protocol_mock
    
    # Mock Task
    task_mock = Mock(name="test_task")
    task_mock.name = "t"
    task_mock.prompt = "Test prompt"
    task_mock.outputs = []
    task_mock.witnesses = []  # No witnesses for test task
    task_mock.context = None  # No knowledge context
    catalog.load_task.return_value = task_mock

    mcp_app.configure(catalog=catalog, sessions_path=tmp_path)
    yield
    # Reset global state
    mcp_app._orchestrator = None


class TestMCPInit:
    """Tests for init tool."""

    def test_init_returns_session_id(self, configured_mcp: None) -> None:
        """Init returns valid session_id."""
        result = mcp_app.init(protocol_name="test", inputs={})

        assert "session_id" in result
        assert len(result["session_id"]) > 0

    def test_init_returns_briefing(self, configured_mcp: None) -> None:
        """Init returns first task briefing."""
        result = mcp_app.init(protocol_name="test", inputs={})

        assert "briefing" in result

    def test_init_stores_inputs(self, configured_mcp: None) -> None:
        """Inputs stored in context."""
        result = mcp_app.init(
            protocol_name="test",
            inputs={"user_topic": "AI research"},
        )
        session_id = result["session_id"]

        value = mcp_app.read(session_id=session_id, uri="context:user_topic")
        assert value == "AI research"


class TestMCPCheck:
    """Tests for check tool."""

    def test_check_returns_status(self, configured_mcp: None) -> None:
        """Check returns status."""
        init_result = mcp_app.init(protocol_name="test", inputs={})
        session_id = init_result["session_id"]

        result = mcp_app.check(session_id=session_id, outputs={"done": True})

        assert "status" in result

    def test_check_invalid_session(self, configured_mcp: None) -> None:
        """Check with invalid session raises error."""
        with pytest.raises(SessionNotFoundError):
            mcp_app.check(session_id="invalid", outputs={})


class TestMCPRead:
    """Tests for read tool."""

    def test_read_context(self, configured_mcp: None) -> None:
        """Read context value."""
        init_result = mcp_app.init(
            protocol_name="test",
            inputs={"topic": "testing"},
        )
        session_id = init_result["session_id"]

        result = mcp_app.read(session_id=session_id, uri="context:topic")

        assert result == "testing"

    def test_read_invalid_uri(self, configured_mcp: None) -> None:
        """Read with invalid URI raises error."""
        init_result = mcp_app.init(protocol_name="test", inputs={})
        session_id = init_result["session_id"]

        with pytest.raises(InvalidURIError):
            mcp_app.read(session_id=session_id, uri="foo:bar")

    def test_read_invalid_session(self, configured_mcp: None) -> None:
        """Read with invalid session raises error."""
        with pytest.raises(SessionNotFoundError):
            mcp_app.read(session_id="invalid", uri="context:foo")


class TestMCPResume:
    """Tests for resume tool."""

    def test_resume_returns_session_and_briefing(self, configured_mcp: None) -> None:
        """Resume returns session_id and briefing."""
        # First init a session
        init_result = mcp_app.init(protocol_name="test", inputs={"topic": "resume_test"})
        session_id = init_result["session_id"]

        # Simulate MCP restart: clear in-memory cache but keep disk state
        orchestrator = mcp_app.get_orchestrator()
        orchestrator._sessions.pop(session_id, None)
        orchestrator._protocols.pop(session_id, None)

        # Resume should restore from disk
        result = mcp_app.resume(session_id=session_id)

        assert result["status"] == "awaiting"
        assert "session_id" in result
        assert "briefing" in result

    def test_resume_invalid_session(self, configured_mcp: None) -> None:
        """Resume with invalid session raises error."""
        with pytest.raises(SessionNotFoundError):
            mcp_app.resume(session_id="nonexistent-session-id")

    def test_resume_then_check(self, configured_mcp: None) -> None:
        """Resume session and then check continues normally."""
        # Init
        init_result = mcp_app.init(protocol_name="test", inputs={})
        session_id = init_result["session_id"]

        # Simulate MCP restart
        orchestrator = mcp_app.get_orchestrator()
        orchestrator._sessions.pop(session_id, None)
        orchestrator._protocols.pop(session_id, None)

        # Resume
        resume_result = mcp_app.resume(session_id=session_id)
        resumed_id = resume_result["session_id"]

        # Check should work on resumed session
        check_result = mcp_app.check(session_id=resumed_id, outputs={"done": True})
        assert "status" in check_result


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_unconfigured_raises(self) -> None:
        """Unconfigured orchestrator raises error."""
        mcp_app._orchestrator = None
        with pytest.raises(RuntimeError, match="not configured"):
            mcp_app.get_orchestrator()
