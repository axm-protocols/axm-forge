"""InitReserveTool — reserve a PyPI package name as an AXMTool."""

from __future__ import annotations

from typing import Any

from axm.tools.base import ToolResult

__all__ = ["InitReserveTool"]


class InitReserveTool:
    """Reserve a package name on PyPI.

    Registered as ``init_reserve`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_reserve"

    def execute(self, **kwargs: Any) -> ToolResult:
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
        name: str = kwargs["name"]
        author: str = kwargs.get("author", "John Doe")
        email: str = kwargs.get("email", "john.doe@example.com")
        dry_run: bool = kwargs.get("dry_run", False)
        try:
            from axm_init.adapters.credentials import CredentialManager
            from axm_init.core.reserver import reserve_pypi

            creds = CredentialManager()

            if not dry_run:
                token = creds.get_pypi_token()
                if not token:
                    return ToolResult(
                        success=False,
                        error=(
                            "No PyPI token found. Set PYPI_TOKEN or configure keyring."
                        ),
                    )
            else:
                token = creds.get_pypi_token() or ""

            result = reserve_pypi(
                name=name,
                author=author,
                email=email,
                token=token or "",
                dry_run=dry_run,
            )

            return ToolResult(
                success=result.success,
                data={
                    "package_name": result.package_name,
                    "version": result.version,
                    "message": result.message,
                },
                error=None if result.success else result.message,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
