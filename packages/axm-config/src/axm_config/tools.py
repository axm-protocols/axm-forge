"""AXMTool surface over the config doctor.

:class:`ConfigDoctorTool` is the deterministic ``config_doctor`` tool: it wraps
:func:`axm_config.doctor.config_doctor_data` and shapes the result as a
:class:`~axm.tools.base.ToolResult`. All business logic lives in the central
function; this module only adds the MCP/CLI boundary (success/error shaping),
so CLI and MCP share the exact same provenance computation.
"""

from __future__ import annotations

from axm.tools.base import ToolResult

from axm_config.doctor import config_doctor_data

__all__ = ["ConfigDoctorTool"]


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
        mapping from :func:`config_doctor_data`. Any failure is shaped into
        ``ToolResult(success=False, error=...)`` at the MCP boundary.
        """
        try:
            report = config_doctor_data(namespace)
        except Exception as exc:  # noqa: BLE001 - MCP boundary
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, data=report)
