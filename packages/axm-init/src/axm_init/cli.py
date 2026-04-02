"""AXM-Init CLI entry point — Project scaffolding tool.

Usage::

    axm-init scaffold my-project
    axm-init reserve my-package --dry-run
    axm-init version
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import cyclopts

if TYPE_CHECKING:
    from axm_init.adapters.credentials import CredentialManager
    from axm_init.models.results import ReserveResult

__all__ = ["app"]

logger = logging.getLogger(__name__)

app = cyclopts.App(
    name="axm-init",
    help="AXM Init — Python project scaffolding with Copier templates.",
)


def _git_config_get(key: str) -> str:
    """Read a value from git config, return empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _require_identity(author: str, email: str, json_output: bool) -> None:
    """Fail early if author or email are empty after fallback."""
    if author and email:
        return
    missing = []
    if not author:
        missing.append("--author")
    if not email:
        missing.append("--email")
    msg = f"Missing {', '.join(missing)} (not set and git config unavailable)"
    if json_output:
        print(json.dumps({"error": msg}))  # noqa: T201
    else:
        print(f"❌ {msg}", file=sys.stderr)  # noqa: T201
    raise SystemExit(1)


def _resolve_token(
    creds: CredentialManager,
    *,
    dry_run: bool,
    json_output: bool,
) -> str:
    """Resolve PyPI token, handling dry-run and error cases."""
    if dry_run:
        return creds.get_pypi_token() or ""
    try:
        return str(creds.resolve_pypi_token(interactive=not json_output))
    except SystemExit as e:
        if json_output:
            print('{"error": "No PyPI token found"}')  # noqa: T201
        logger.debug("PyPI token resolution failed", exc_info=True)
        raise SystemExit(1) from e


def _print_reserve_result(
    result: ReserveResult, *, name: str, json_output: bool
) -> None:
    """Print reserve result in JSON or human-readable format."""
    if json_output:
        print(  # noqa: T201
            json.dumps(
                {
                    "success": result.success,
                    "package_name": result.package_name,
                    "version": result.version,
                    "message": result.message,
                },
                indent=2,
            )
        )
    elif result.success:
        print(f"\u2705 {result.message}")  # noqa: T201
        print(f"   View at: https://pypi.org/project/{name}/")  # noqa: T201
    else:
        print(f"\u274c {result.message}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)


def _check_pypi_availability(project_name: str, *, json_output: bool) -> None:
    """Check PyPI availability and exit(1) if name is taken."""
    from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

    adapter = PyPIAdapter()
    status = adapter.check_availability(project_name)

    if status == AvailabilityStatus.TAKEN:
        if json_output:
            print(  # noqa: T201
                json.dumps({"error": f"Package name '{project_name}' is taken on PyPI"})
            )
        else:
            print(  # noqa: T201
                f"❌ Package name '{project_name}' is already taken on PyPI",
                file=sys.stderr,
            )
        raise SystemExit(1)

    if status == AvailabilityStatus.ERROR and not json_output:
        print(  # noqa: T201
            "⚠️  Could not verify PyPI availability",
            file=sys.stderr,
        )


def _print_scaffold_result(
    result: Any,
    project_name: str,
    target_path: Path,
    *,
    json_output: bool,
) -> None:
    """Print scaffold result as JSON or human-readable output."""
    if json_output:
        print(  # noqa: T201
            json.dumps(
                {
                    "success": result.success,
                    "files": [str(f) for f in result.files_created],
                }
            )
        )
    elif result.success:
        print(f"✅ Project '{project_name}' created at {target_path}")  # noqa: T201
        for f in result.files_created:
            print(f"   📄 {f}")  # noqa: T201
    else:
        print(f"❌ {result.message}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)


@app.command()
def scaffold(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to initialize project"),
    ] = ".",
    *,
    name: Annotated[
        str | None,
        cyclopts.Parameter(name=["--name", "-n"], help="Project name"),
    ] = None,
    org: Annotated[
        str,
        cyclopts.Parameter(name=["--org", "-o"], help="GitHub org or username"),
    ],
    author: Annotated[
        str,
        cyclopts.Parameter(name=["--author", "-a"], help="Author name"),
    ],
    email: Annotated[
        str,
        cyclopts.Parameter(name=["--email", "-e"], help="Author email"),
    ],
    license: Annotated[
        str,
        cyclopts.Parameter(name=["--license", "-l"], help="License type"),
    ] = "Apache-2.0",
    license_holder: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--license-holder"],
            help="License holder (defaults to --org)",
        ),
    ] = None,
    description: Annotated[
        str,
        cyclopts.Parameter(name=["--description", "-d"], help="Description"),
    ] = "",
    workspace: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--workspace", "-w"],
            help="Scaffold a UV workspace instead of a standalone package",
        ),
    ] = False,
    member: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--member", "-m"],
            help="Scaffold a member sub-package with this name",
        ),
    ] = None,
    check_pypi: Annotated[
        bool,
        cyclopts.Parameter(name=["--check-pypi"], help="Check PyPI availability"),
    ] = False,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Scaffold a new Python project with best practices."""
    from axm_init.adapters.copier import CopierAdapter, CopierConfig
    from axm_init.core.templates import TemplateType, get_template_path

    if workspace and member is not None:
        msg = "--workspace and --member are mutually exclusive"
        if json_output:
            print(json.dumps({"error": msg}))  # noqa: T201
        else:
            print(f"❌ {msg}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    target_path = Path(path).resolve()
    project_name = name or target_path.name

    if check_pypi:
        _check_pypi_availability(project_name, json_output=json_output)

    if member is not None:
        _scaffold_member(
            target_path,
            member,
            org=org,
            author=author,
            email=email,
            license_type=license,
            description=description,
            json_output=json_output,
        )
        return

    template_type = TemplateType.WORKSPACE if workspace else TemplateType.STANDALONE

    data = _build_scaffold_data(
        workspace=workspace,
        project_name=project_name,
        description=description,
        org=org,
        license_type=license,
        license_holder=license_holder or org,
        author=author,
        email=email,
    )

    copier_adapter = CopierAdapter()
    copier_config = CopierConfig(
        template_path=get_template_path(template_type),
        destination=target_path,
        data=data,
        trust_template=True,  # Internal AXM template is trusted
    )
    result = copier_adapter.copy(copier_config)

    _print_scaffold_result(result, project_name, target_path, json_output=json_output)


def _build_scaffold_data(
    *,
    workspace: bool,
    project_name: str,
    description: str,
    org: str,
    license_type: str,
    license_holder: str,
    author: str,
    email: str,
) -> dict[str, str]:
    """Build data dict for copier template."""
    if workspace:
        return {
            "workspace_name": project_name,
            "description": description or "A modern Python workspace",
            "org": org,
            "license": license_type,
            "license_holder": license_holder or org,
            "author_name": author,
            "author_email": email,
        }
    return {
        "package_name": project_name,
        "description": description or "A modern Python package",
        "org": org,
        "license": license_type,
        "license_holder": license_holder or org,
        "author_name": author,
        "author_email": email,
    }


def _fail(msg: str, *, json_output: bool) -> NoReturn:
    """Print error and exit."""
    if json_output:
        print(json.dumps({"error": msg}))  # noqa: T201
    else:
        print(f"❌ {msg}", file=sys.stderr)  # noqa: T201
    raise SystemExit(1)


def _resolve_workspace_root(target_path: Path) -> Path | None:
    """Resolve workspace root from *target_path*, or return ``None``."""
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


def _read_workspace_name(workspace_root: Path) -> str:
    """Read project name from workspace root pyproject.toml."""
    import tomllib

    root_pyproject = workspace_root / "pyproject.toml"
    if root_pyproject.is_file():
        with open(root_pyproject, "rb") as f:
            data = tomllib.load(f)
        name: str = data.get("project", {}).get("name", workspace_root.name)
        return name
    return workspace_root.name


def _scaffold_member(
    target_path: Path,
    member_name: str,
    *,
    org: str,
    author: str,
    email: str,
    license_type: str,
    description: str,
    json_output: bool,
) -> None:
    """Scaffold a member sub-package inside an existing UV workspace.

    Args:
        target_path: Current working directory (must be inside a workspace).
        member_name: Name of the new member package.
        org: GitHub org or username.
        author: Author name.
        email: Author email.
        license_type: License type.
        description: Package description.
        json_output: Whether to output JSON.
    """
    from axm_init.adapters.copier import CopierAdapter, CopierConfig
    from axm_init.adapters.workspace_patcher import patch_all
    from axm_init.core.templates import TemplateType, get_template_path

    # 1. Detect workspace root
    workspace_root = _resolve_workspace_root(target_path)
    if workspace_root is None:
        _fail(
            "Not inside a UV workspace — use --member from a workspace directory",
            json_output=json_output,
        )

    # 2. Check for duplicate
    member_dir = workspace_root / "packages" / member_name
    if member_dir.exists():
        _fail(
            f"Member '{member_name}' already exists at {member_dir}",
            json_output=json_output,
        )

    # 3. Scaffold member
    data = {
        "member_name": member_name,
        "description": description or "A workspace member package",
        "org": org,
        "license": license_type,
        "author_name": author,
        "author_email": email,
        "workspace_name": _read_workspace_name(workspace_root),
    }

    copier_adapter = CopierAdapter()
    copier_config = CopierConfig(
        template_path=get_template_path(TemplateType.MEMBER),
        destination=member_dir,
        data=data,
        trust_template=True,
    )
    result = copier_adapter.copy(copier_config)

    if not result.success:
        _print_scaffold_result(result, member_name, member_dir, json_output=json_output)
        return

    # 4. Patch root files
    patched = patch_all(workspace_root, member_name)

    if json_output:
        print(  # noqa: T201
            json.dumps(
                {
                    "success": True,
                    "member": member_name,
                    "path": str(member_dir),
                    "files": [str(f) for f in result.files_created],
                    "patched_root_files": patched,
                }
            )
        )
    else:
        print(f"✅ Member '{member_name}' created at {member_dir}")  # noqa: T201
        for f in result.files_created:
            print(f"   📄 {f}")  # noqa: T201
        if patched:
            print(  # noqa: T201
                f"   🔧 Patched root files: {', '.join(patched)}"
            )


@app.command()
def reserve(
    name: Annotated[
        str,
        cyclopts.Parameter(help="Package name to reserve"),
    ],
    *,
    author: Annotated[
        str,
        cyclopts.Parameter(name=["--author", "-a"], help="Author name"),
    ] = "",
    email: Annotated[
        str,
        cyclopts.Parameter(name=["--email", "-e"], help="Author email"),
    ] = "",
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(name=["--dry-run"], help="Skip actual publish"),
    ] = False,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Reserve a package name on PyPI."""
    from axm_init.adapters.credentials import CredentialManager
    from axm_init.core.reserver import reserve_pypi

    author = author or _git_config_get("user.name")
    email = email or _git_config_get("user.email")
    _require_identity(author, email, json_output)

    token = _resolve_token(
        CredentialManager(), dry_run=dry_run, json_output=json_output
    )

    result = reserve_pypi(
        name=name,
        author=author,
        email=email,
        token=token or "",
        dry_run=dry_run,
    )

    _print_reserve_result(result, name=name, json_output=json_output)


@app.command()
def check(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to check"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    agent: Annotated[
        bool,
        cyclopts.Parameter(name=["--agent"], help="Compact agent-friendly output"),
    ] = False,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--verbose", "-v"], help="Show all checks including passed"
        ),
    ] = False,
    category: Annotated[
        str | None,
        cyclopts.Parameter(name=["--category", "-c"], help="Filter to one category"),
    ] = None,
) -> None:
    """Check a project against the AXM gold standard."""
    from axm_init.core.checker import (
        CheckEngine,
        format_agent,
        format_json,
        format_report,
    )

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    try:
        engine = CheckEngine(project_path, category=category)
        result = engine.run()
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from e

    if agent:
        print(json.dumps(format_agent(result), indent=2))  # noqa: T201
    elif json_output:
        print(json.dumps(format_json(result), indent=2))  # noqa: T201
    else:
        print(format_report(result, verbose=verbose))  # noqa: T201

    if result.score < 100:
        raise SystemExit(1)


@app.command()
def version() -> None:
    """Show axm-init version."""
    from axm_init import __version__

    print(f"axm-init {__version__}")  # noqa: T201


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
