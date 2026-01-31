"""Copier adapter for template-based scaffolding."""

from pathlib import Path
from typing import Any

from copier import run_copy
from pydantic import BaseModel

from axm_init.models.results import ScaffoldResult


class CopierConfig(BaseModel):
    """Configuration for Copier execution."""

    template_path: Path
    destination: Path
    data: dict[str, Any]
    defaults: bool = True
    overwrite: bool = False

    model_config = {"extra": "forbid"}


class CopierAdapter:
    """Adapter for Copier template operations.

    Wraps Copier's run_copy function with a Pydantic-based interface
    and returns structured ScaffoldResult.
    """

    def copy(self, config: CopierConfig) -> ScaffoldResult:
        """Execute Copier copy operation.

        Args:
            config: Copier configuration with template path, destination, and data.

        Returns:
            ScaffoldResult with success status and path.
        """
        try:
            run_copy(
                src_path=str(config.template_path),
                dst_path=config.destination,
                data=config.data,
                defaults=config.defaults,
                overwrite=config.overwrite,
                unsafe=True,  # Skip interactive prompts for tasks
            )
            return ScaffoldResult(
                success=True,
                path=str(config.destination),
                message="Project scaffolded via Copier",
            )
        except Exception as e:
            return ScaffoldResult(
                success=False,
                path=str(config.destination),
                message=f"Copier failed: {e}",
            )
