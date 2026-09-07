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

from collections.abc import Mapping, Sequence

from axm.tools.base import ToolResult

from axm_doctor.credentials import (
    CredentialProvenance,
    collect_credential_provenance,
)
from axm_doctor.detect import (
    detect_auth,
    detect_gh_config,
    detect_git_identity,
    detect_tool,
)
from axm_doctor.orchestrate import missing_secrets

__all__ = ["PROBED_TOOLS", "THIRD_PARTY_AUTH", "AuthStatusTool", "EnvDoctorTool"]

# External binaries probed by the doctor. ``uv`` leads: it is the workspace's
# package manager and the first thing bootstrap must guarantee.
PROBED_TOOLS: tuple[str, ...] = ("uv", "git", "gh", "node", "npm", "claude", "codex")

# Third-party binaries with a login flow whose auth state the doctor reports.
THIRD_PARTY_AUTH: tuple[str, ...] = ("gh", "claude", "codex")


def _auth_map() -> dict[str, dict[str, str | bool | None]]:
    """Build the value-free ``{tool: {state, login_cmd}}`` auth report."""
    return {
        tool: {
            "state": status.state,
            "login_cmd": status.login_cmd,
            "declaration_consulted": status.declaration_consulted,
        }
        for tool in THIRD_PARTY_AUTH
        for status in (detect_auth(tool),)
    }


def _credentials_map(
    rows: Sequence[CredentialProvenance],
) -> dict[str, dict[str, str | bool]]:
    """Serialize credential provenance without carrying credential values."""
    return {
        row.coordinate: {
            "kind": row.kind,
            "layer": row.layer,
            "present": row.present,
        }
        for row in rows
    }


def _credentials_text(
    credentials: Mapping[str, Mapping[str, object]],
) -> str:
    """Render each credential coordinate followed by its serving layer."""
    grouped: dict[str, list[tuple[str, Mapping[str, object]]]] = {}
    for coordinate, entry in credentials.items():
        kind = entry.get("kind", "credential")
        heading = kind if isinstance(kind, str) else "unknown"
        grouped.setdefault(heading, []).append((coordinate, entry))

    lines: list[str] = []
    for kind, entries in grouped.items():
        lines.append(f"{kind}:")
        lines.extend(
            f"- {coordinate}: {entry['layer']}" for coordinate, entry in entries
        )
    return "\n".join(lines) if lines else "Credentials:"


def _config_map() -> dict[str, dict[str, str]]:
    """Build the value-free ``{git|gh: {state}}`` config report.

    Reports whether a git committer identity is resolvable and whether ``gh``
    carries a base config — neither value is ever read.
    """
    return {
        "git": {"state": detect_git_identity().state},
        "gh": {"state": detect_gh_config().state},
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
            data={
                "tools": tools,
                "auth": _auth_map(),
                "secrets": secrets,
                "config": _config_map(),
            },
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
            provenance = _credentials_map(collect_credential_provenance())
            credentials = {
                coordinate: {
                    "layer": entry["layer"],
                    "present": entry["present"],
                }
                for coordinate, entry in provenance.items()
            }
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        auth_text = "\n".join(
            f"- {tool}: {entry['state']}"
            f"{' [no declaration]' if not entry['declaration_consulted'] else ''}"
            for tool, entry in auth.items()
        )
        return ToolResult(
            success=True,
            data={
                "auth": auth,
                "undetermined": [
                    tool
                    for tool, entry in auth.items()
                    if entry["state"] == "undetermined"
                ],
                "logged_out": [
                    tool
                    for tool, entry in auth.items()
                    if entry["state"] == "logged_out"
                ],
                "credentials": credentials,
            },
            text=(f"Third-party auth:\n{auth_text}\n\n{_credentials_text(provenance)}"),
        )
