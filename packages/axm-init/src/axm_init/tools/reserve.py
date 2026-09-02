"""InitReserveTool — reserve a PyPI package name as an AXMTool."""

from __future__ import annotations

import subprocess
from dataclasses import replace

from axm.tools.base import ToolResult

__all__ = ["InitReserveTool"]

_PLACEHOLDERS = {"john doe", "john.doe@example.com"}


def _render_reserve_text(package_name: str, version: str, message: str) -> str:
    """Render a reservation result as a single compact header line.

    LLM-facing companion to the structured ToolResult data: carries the
    reserved name, the placeholder version and the full status message
    verbatim. Nothing is dropped — the data dict remains the source of truth.
    """
    return f"init_reserve | ✓ | {package_name} | v{version} | {message}"


def _git_config_get(key: str) -> str:
    """Read a git identity value, returning an empty string when unavailable."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _validate_identity(author: str, email: str) -> ToolResult | None:
    """Check author/email are non-empty and not placeholder values."""
    if not author or author.lower() in _PLACEHOLDERS:
        return ToolResult(
            success=False,
            error="'author' is required (placeholder values are not accepted)",
        )
    if not email or email.lower() in _PLACEHOLDERS:
        return ToolResult(
            success=False,
            error="'email' is required (placeholder values are not accepted)",
        )
    return None


def _apply_json_output(result: ToolResult, enabled: bool) -> ToolResult:
    """Select structured CLI rendering for a reservation result."""
    if not enabled:
        return result
    data = result.data
    if not result.success and not data:
        data = {"error": result.error or "Reservation failed"}
    return replace(result, text=None, data=data)


class InitReserveTool:
    """Reserve a package name on PyPI.

    Registered as ``init_reserve`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_reserve"

    def execute(
        self,
        name: str = "",
        *,
        author: str = "",
        email: str = "",
        dry_run: bool = False,
        json_output: bool = False,
    ) -> ToolResult:
        """Reserve a package name on PyPI.

        Args:
            **kwargs: Keyword arguments.
                name: Package name to reserve.
                author: Author name for the placeholder package.
                email: Author email for the placeholder package.
                dry_run: If True, skip the actual publish step.

        Returns:
            ToolResult with reservation status.
        """
        if not name:
            return _apply_json_output(
                ToolResult(success=False, error="'name' is required"), json_output
            )
        if not isinstance(dry_run, bool):
            return _apply_json_output(
                ToolResult(
                    success=False,
                    error=f"'dry_run' must be a boolean, got {type(dry_run).__name__}",
                ),
                json_output,
            )
        if not author and not email:
            author = _git_config_get("user.name")
            email = _git_config_get("user.email")

        error = _validate_identity(author, email)
        if error:
            return _apply_json_output(error, json_output)

        try:
            from axm_init.adapters.credentials import CredentialManager
            from axm_init.adapters.pypi import PyPIAdapter
            from axm_init.core.reserver import reserve_pypi

            creds = CredentialManager()

            if not dry_run:
                token = creds.get_pypi_token()
                if not token:
                    return _apply_json_output(
                        ToolResult(
                            success=False,
                            error=(
                                "No PyPI token found. Set PYPI_TOKEN or configure "
                                "keyring."
                            ),
                        ),
                        json_output,
                    )
            else:
                token = creds.get_pypi_token() or ""

            result = reserve_pypi(
                name=name,
                author=author,
                email=email,
                token=token or "",
                dry_run=dry_run,
                checker=PyPIAdapter(),
            )

            return _apply_json_output(
                ToolResult(
                    success=result.success,
                    data={
                        "package_name": result.package_name,
                        "version": result.version,
                        "message": result.message,
                    },
                    text=(
                        _render_reserve_text(
                            result.package_name, result.version, result.message
                        )
                        if result.success
                        else None
                    ),
                    error=None if result.success else result.message,
                ),
                json_output,
            )
        except Exception as exc:
            return _apply_json_output(
                ToolResult(success=False, error=str(exc)), json_output
            )
