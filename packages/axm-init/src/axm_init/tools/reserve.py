"""InitReserveTool — reserve a PyPI package name as an AXMTool."""

from __future__ import annotations

from axm.tools.base import ToolResult

__all__ = ["InitReserveTool"]

_PLACEHOLDERS = {"john doe", "john.doe@example.com"}


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


class InitReserveTool:
    """Reserve a package name on PyPI.

    Registered as ``init_reserve`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_reserve"

    def execute(self, **kwargs: object) -> ToolResult:
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
        name_raw = kwargs.get("name")
        if not isinstance(name_raw, str) or not name_raw:
            return ToolResult(success=False, error="'name' is required")
        name: str = name_raw
        author_raw = kwargs.get("author", "")
        email_raw = kwargs.get("email", "")
        dry_run_raw = kwargs.get("dry_run", False)
        author: str = author_raw if isinstance(author_raw, str) else ""
        email: str = email_raw if isinstance(email_raw, str) else ""
        dry_run: bool = bool(dry_run_raw) if isinstance(dry_run_raw, bool) else False

        error = _validate_identity(author, email)
        if error:
            return error

        try:
            from axm_init.adapters.credentials import CredentialManager
            from axm_init.adapters.pypi import PyPIAdapter
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
                checker=PyPIAdapter(),
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
