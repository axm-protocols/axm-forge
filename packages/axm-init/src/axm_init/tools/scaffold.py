"""InitScaffoldTool — project scaffolding as an AXMTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

__all__ = ["InitScaffoldTool"]


class InitScaffoldTool:
    """Initialize a new Python project with best practices.

    Registered as ``init_scaffold`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_scaffold"

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

            if workspace:
                data = {
                    "workspace_name": project_name,
                    "description": description or "A modern Python workspace",
                    "org": org,
                    "license": license_type,
                    "license_holder": org,
                    "author_name": author,
                    "author_email": email,
                }
            else:
                data = {
                    "package_name": project_name,
                    "description": description or "A modern Python package",
                    "org": org,
                    "license": license_type,
                    "license_holder": org,
                    "author_name": author,
                    "author_email": email,
                }

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
        from axm_init.checks._workspace import (
            ProjectContext,
            detect_context,
            find_workspace_root,
        )
        from axm_init.core.templates import TemplateType, get_template_path

        # 1. Detect workspace root
        workspace_root: Path
        context = detect_context(target_path)
        if context == ProjectContext.WORKSPACE:
            workspace_root = target_path
        elif context == ProjectContext.MEMBER:
            found = find_workspace_root(target_path)
            if found is None:
                return ToolResult(
                    success=False,
                    error="Not inside a UV workspace",
                )
            workspace_root = found
        else:
            return ToolResult(
                success=False,
                error="Not inside a UV workspace",
            )

        # 2. Check for duplicate
        member_dir = workspace_root / "packages" / member_name
        if member_dir.exists():
            return ToolResult(
                success=False,
                error=f"Member '{member_name}' already exists at {member_dir}",
            )

        # 3. Get workspace name
        import tomllib

        ws_name = workspace_root.name
        root_pyproject = workspace_root / "pyproject.toml"
        if root_pyproject.is_file():
            with open(root_pyproject, "rb") as f:
                root_data = tomllib.load(f)
            ws_name = str(root_data.get("project", {}).get("name", workspace_root.name))

        # 4. Scaffold
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

        # 5. Patch root files
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
