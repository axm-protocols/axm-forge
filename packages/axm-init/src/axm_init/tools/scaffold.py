"""InitScaffoldTool — project scaffolding as an AXMTool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

__all__ = ["InitScaffoldTool"]


@dataclass(frozen=True, slots=True)
class _ProjectMeta:
    org: str
    license_type: str
    author_name: str
    author_email: str


class InitScaffoldTool:
    """Initialize a new Python project with best practices.

    Registered as ``init_scaffold`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_scaffold"

    def _validate_inputs(
        self,
        kwargs: dict[str, Any],
    ) -> tuple[str, str | None, str, str, str, str, str, bool, str | None] | ToolResult:
        """Extract and validate inputs from kwargs.

        Returns a tuple of validated values or a ToolResult on error.
        """
        path: str = kwargs.get("path", ".")
        name: str | None = kwargs.get("name")
        org: str = kwargs.get("org", "")
        author: str = kwargs.get("author", "")
        email: str = kwargs.get("email", "")
        license_type: str = kwargs.get("license", "Apache-2.0")
        description: str = kwargs.get("description", "")
        workspace: bool = kwargs.get("workspace", False)
        member: str | None = kwargs.get("member")

        if not org or not author or not email:
            return ToolResult(
                success=False,
                error="org, author, and email are required",
            )

        return (
            path,
            name,
            org,
            author,
            email,
            license_type,
            description,
            workspace,
            member,
        )

    def _build_template_data(
        self,
        *,
        project_name: str,
        workspace: bool,
        description: str,
        meta: _ProjectMeta,
    ) -> dict[str, str]:
        """Build template data dict for workspace or standalone scaffold."""
        name_key = "workspace_name" if workspace else "package_name"
        default_desc = (
            "A modern Python workspace" if workspace else "A modern Python package"
        )
        return {
            name_key: project_name,
            "description": description or default_desc,
            "org": meta.org,
            "license": meta.license_type,
            "license_holder": meta.org,
            "author_name": meta.author_name,
            "author_email": meta.author_email,
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Initialize a new Python project.

        Args:
            **kwargs: Keyword arguments.
                path: Path to initialize project.
                name: Project name (defaults to directory name).
                org: GitHub org or username.
                author: Author name.
                email: Author email.
                license: License type.
                description: Project description.
                workspace: If True, scaffold a UV workspace.
                member: Member package name to scaffold inside a workspace.

        Returns:
            ToolResult with created files list.
        """
        validated = self._validate_inputs(kwargs)
        if isinstance(validated, ToolResult):
            return validated

        path, name, org, author, email, license_type, description, workspace, member = (
            validated
        )

        try:
            target_path = Path(path).resolve()

            if member:
                return self._scaffold_member(
                    target_path,
                    member,
                    scaffold_data={
                        "org": org,
                        "author_name": author,
                        "author_email": email,
                        "license": license_type,
                        "description": description,
                    },
                )

            project_name = name or target_path.name

            from axm_init.adapters.copier import CopierAdapter, CopierConfig
            from axm_init.core.templates import TemplateType, get_template_path

            template_type = (
                TemplateType.WORKSPACE if workspace else TemplateType.STANDALONE
            )
            meta = _ProjectMeta(
                org=org,
                license_type=license_type,
                author_name=author,
                author_email=email,
            )
            data = self._build_template_data(
                project_name=project_name,
                workspace=workspace,
                description=description,
                meta=meta,
            )

            copier_adapter = CopierAdapter()
            copier_config = CopierConfig(
                template_path=get_template_path(template_type),
                destination=target_path,
                data=data,
                trust_template=True,
            )
            result = copier_adapter.copy(copier_config)

            return ToolResult(
                success=result.success,
                data={
                    "project_name": project_name,
                    "template": template_type.value,
                    "files": [str(f) for f in result.files_created],
                },
                error=None if result.success else result.message,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    @staticmethod
    def _resolve_workspace_root(target_path: Path) -> Path | None:
        """Resolve workspace root from target path, or None if not in a workspace."""
        from axm_init.checks._workspace import (
            ProjectContext,
            detect_context,
            find_workspace_root,
        )

        context = detect_context(target_path)
        if context == ProjectContext.WORKSPACE:
            return target_path
        if context == ProjectContext.MEMBER:
            return find_workspace_root(target_path)
        return None

    @staticmethod
    def _read_workspace_name(workspace_root: Path) -> str:
        """Read workspace name from pyproject.toml or fall back to dir name."""
        import tomllib

        root_pyproject = workspace_root / "pyproject.toml"
        if root_pyproject.is_file():
            with open(root_pyproject, "rb") as f:
                root_data = tomllib.load(f)
            return str(root_data.get("project", {}).get("name", workspace_root.name))
        return workspace_root.name

    def _scaffold_member(
        self,
        target_path: Path,
        member_name: str,
        *,
        scaffold_data: dict[str, str],
    ) -> ToolResult:
        """Scaffold a member sub-package inside an existing workspace.

        Args:
            target_path: Current directory (must be inside a workspace).
            member_name: Name of the new member package.
            scaffold_data: Template variables (org, author, email, etc.).

        Returns:
            ToolResult with member scaffold results.
        """
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        from axm_init.adapters.workspace_patcher import patch_all
        from axm_init.core.templates import TemplateType, get_template_path

        workspace_root = self._resolve_workspace_root(target_path)
        if workspace_root is None:
            return ToolResult(success=False, error="Not inside a UV workspace")

        member_dir = workspace_root / "packages" / member_name
        if member_dir.exists():
            return ToolResult(
                success=False,
                error=f"Member '{member_name}' already exists at {member_dir}",
            )

        ws_name = self._read_workspace_name(workspace_root)
        data = {
            "member_name": member_name,
            "workspace_name": ws_name,
            **scaffold_data,
        }
        if "description" not in data or not data["description"]:
            data["description"] = "A workspace member package"

        copier_adapter = CopierAdapter()
        copier_config = CopierConfig(
            template_path=get_template_path(TemplateType.MEMBER),
            destination=member_dir,
            data=data,
            trust_template=True,
        )
        result = copier_adapter.copy(copier_config)

        if not result.success:
            return ToolResult(
                success=False,
                error=result.message or "Member scaffold failed",
            )

        patched = patch_all(workspace_root, member_name)

        return ToolResult(
            success=True,
            data={
                "member": member_name,
                "path": str(member_dir),
                "files": [str(f) for f in result.files_created],
                "patched_root_files": patched,
            },
        )
