"""AXMTool surface over the config doctor.

:class:`ConfigDoctorTool` is the deterministic ``config_doctor`` tool: it wraps
:func:`axm_config.doctor.config_doctor_data` and shapes the result as a
:class:`~axm.tools.base.ToolResult`. All business logic lives in the central
function; this module only adds the MCP/CLI boundary (success/error shaping),
so CLI and MCP share the exact same provenance computation.
"""

from __future__ import annotations

from axm.tools.base import ToolResult

from axm_config.doctor import config_doctor_data, render_doctor_report
from axm_config.isolation import profile_isolation

__all__ = ["ConfigDoctorTool", "ProfileIsolationTool"]


class ConfigDoctorTool:
    """Report config-key provenance (``env``/``file``/``default``), read-only.

    Satisfies the :class:`~axm.tools.base.AXMTool` protocol structurally. The
    tool is diagnostic: it never mutates any config layer, it only reports
    which layer would win per key.
    """

    agent_hint = (
        "Report where each config key resolves from (env>file>default) for a "
        "namespace; read-only provenance, never mutates. Replaces manual "
        "~/.axm TOML + env inspection."
    )
    domain = "config"
    tags = frozenset({"config", "provenance", "doctor"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "config_doctor"

    def execute(self, *, namespace: str | None = None) -> ToolResult:
        """Return the provenance report for ``namespace`` (or all known).

        On success, ``data`` is the ``{"<ns>.<key>": {layer, present}}``
        mapping from :func:`config_doctor_data` and ``text`` is the shared
        one-line-per-key rendering from :func:`render_doctor_report` (so the
        MCP text and the CLI ``doctor`` output cannot drift). Any failure is
        shaped into ``ToolResult(success=False, error=...)`` at the MCP
        boundary.
        """
        try:
            report = config_doctor_data(namespace)
        except Exception as exc:  # noqa: BLE001 - MCP boundary
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, data=report, text=render_doctor_report(report))


class ProfileIsolationTool:
    """Resolve isolated state paths for an explicit or active profile."""

    agent_hint = (
        "Resolve the six isolated state paths for a profile without creating "
        "directories or mutating configuration."
    )
    domain = "config"
    tags = frozenset({"config", "profile", "isolation"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "profile_isolation"

    def execute(self, *, profile: str | None = None) -> ToolResult:
        """Return resolved profile paths and their isolation verdict."""
        try:
            isolation = profile_isolation(profile)
        except Exception as exc:  # noqa: BLE001 - AXMTool boundary
            return ToolResult(success=False, error=str(exc))

        data: dict[str, object] = {
            name: str(path) for name, path in isolation.paths.items()
        }
        data["profile"] = isolation.profile
        data["isolated"] = isolation.isolated
        text = "\n".join(f"{name}: {path}" for name, path in isolation.paths.items())
        return ToolResult(success=True, data=data, text=text)
