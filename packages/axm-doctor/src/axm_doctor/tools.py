"""AXM tools for the doctor — ``env_doctor`` and ``auth_status``.

Both are deterministic :class:`~axm.tools.base.AXMTool` implementations, so
they are reachable over MCP, the ``axm`` CLI and as DAG nodes from a single
``axm.tools`` entry-point declaration. They are strictly **read-only**: they
wrap the central detect/orchestrate functions and never install anything.

They uphold the doctor's security invariant — mirror of ``vault_doctor`` —
**no tool ever serializes a token value**. ``auth_status`` reports only the
state and the recovery command (``login_cmd``); the credential value itself
never transits axm_doctor.
"""

from __future__ import annotations

from axm.tools.base import ToolResult

from axm_doctor.detect import detect_auth, detect_tool
from axm_doctor.orchestrate import missing_secrets

__all__ = ["PROBED_TOOLS", "THIRD_PARTY_AUTH", "AuthStatusTool", "EnvDoctorTool"]

# External binaries probed by the doctor. ``uv`` leads: it is the workspace's
# package manager and the first thing bootstrap must guarantee.
PROBED_TOOLS: tuple[str, ...] = ("uv", "gh", "node", "npm", "claude", "codex")

# Third-party binaries with a login flow whose auth state the doctor reports.
THIRD_PARTY_AUTH: tuple[str, ...] = ("gh", "claude", "codex")


def _auth_map() -> dict[str, dict[str, str | None]]:
    """Build the value-free ``{tool: {state, login_cmd}}`` auth report."""
    return {
        tool: {"state": status.state, "login_cmd": status.login_cmd}
        for tool in THIRD_PARTY_AUTH
        for status in (detect_auth(tool),)
    }


class EnvDoctorTool:
    """Read-only env report: tool presence/version + auth + missing secrets."""

    agent_hint = (
        "Read-only env doctor: report each external tool's presence/version, "
        "third-party auth state, and missing (value-free) secrets. Never installs."
    )
    domain = "doctor"
    tags = frozenset({"doctor", "env", "bootstrap", "detect"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "env_doctor"

    def execute(self) -> ToolResult:
        """Return the full env report; any error becomes a failure ToolResult."""
        try:
            tools = {
                name: {"state": status.state, "version": status.version}
                for name in PROBED_TOOLS
                for status in (detect_tool(name),)
            }
            secrets = [secret.model_dump() for secret in missing_secrets()]
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        return ToolResult(
            success=True,
            data={"tools": tools, "auth": _auth_map(), "secrets": secrets},
        )


class AuthStatusTool:
    """Report third-party auth state — never a token value (mirror of vault)."""

    agent_hint = (
        "Report third-party binary auth state as {tool: {state, login_cmd}}; "
        "the token value is NEVER returned."
    )
    domain = "doctor"
    tags = frozenset({"doctor", "auth", "login"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "auth_status"

    def execute(self) -> ToolResult:
        """Return value-free auth state; any error becomes a failure ToolResult."""
        try:
            auth = _auth_map()
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, data={"auth": auth})
