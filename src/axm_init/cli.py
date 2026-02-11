"""AXM-Init CLI entry point — Project scaffolding tool.

Usage::

    axm-init init my-project
    axm-init reserve my-package --dry-run
    axm-init version
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import cyclopts

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.adapters.credentials import CredentialManager
from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter
from axm_init.core.reserver import reserve_pypi
from axm_init.core.templates import resolve_template

__all__ = ["app"]

app = cyclopts.App(
    name="axm-init",
    help="AXM Init — Python project scaffolding with Copier templates.",
)


@app.command()
def init(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to initialize project"),
    ] = ".",
    *,
    name: Annotated[
        str | None,
        cyclopts.Parameter(name=["--name", "-n"], help="Project name"),
    ] = None,
    template: Annotated[
        str,
        cyclopts.Parameter(name=["--template", "-t"], help="Template: python, minimal"),
    ] = "minimal",
    description: Annotated[
        str,
        cyclopts.Parameter(name=["--description", "-d"], help="Description"),
    ] = "",
    check_pypi: Annotated[
        bool,
        cyclopts.Parameter(name=["--check-pypi"], help="Check PyPI availability"),
    ] = False,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
) -> None:
    """Initialize a new Python project with best practices."""
    target_path = Path(path).resolve()

    # Default name to directory name if not provided
    project_name = name or target_path.name

    # Check PyPI availability if requested
    if check_pypi:
        adapter = PyPIAdapter()
        status = adapter.check_availability(project_name)
        if status == AvailabilityStatus.TAKEN:
            if json_output:
                print(  # noqa: T201
                    f'{{"error": "Package name \'{project_name}\' is taken on PyPI"}}'
                )
            else:
                print(  # noqa: T201
                    f"❌ Package name '{project_name}' is already taken on PyPI",
                    file=sys.stderr,
                )
            raise SystemExit(1)
        if status == AvailabilityStatus.ERROR:
            if not json_output:
                print(  # noqa: T201
                    "⚠️  Could not verify PyPI availability", file=sys.stderr
                )

    # Resolve template and scaffold with Copier
    try:
        template_info = resolve_template(template)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from e

    copier_adapter = CopierAdapter()
    copier_config = CopierConfig(
        template_path=template_info.path,
        destination=target_path,
        data={
            "package_name": project_name,
            "description": description or "A modern Python package",
            "org": "JarryGabriel",
            "license": "MIT",
            "author_name": "Gabriel Jarry",
            "author_email": "jarry.gabriel@gmail.com",
        },
    )
    result = copier_adapter.copy(copier_config)

    if json_output:
        print(  # noqa: T201
            json.dumps(
                {
                    "success": result.success,
                    "files": [str(f) for f in result.files_created],
                }
            )
        )
    else:
        if result.success:
            print(f"✅ Project '{project_name}' created at {target_path}")  # noqa: T201
            for f in result.files_created:
                print(f"   📄 {f}")  # noqa: T201
        else:
            print(f"❌ {result.message}", file=sys.stderr)  # noqa: T201
            raise SystemExit(1)


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
    ] = "Gabriel Jarry",
    email: Annotated[
        str,
        cyclopts.Parameter(name=["--email", "-e"], help="Author email"),
    ] = "jarry.gabriel@gmail.com",
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
    creds = CredentialManager()

    if not dry_run:
        try:
            token = creds.resolve_pypi_token(interactive=not json_output)
        except SystemExit:
            if json_output:
                print('{"error": "No PyPI token found"}')  # noqa: T201
            raise SystemExit(1) from None
    else:
        token = creds.get_pypi_token() or ""

    result = reserve_pypi(
        name=name,
        author=author,
        email=email,
        token=token or "",
        dry_run=dry_run,
    )

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
    else:
        if result.success:
            print(f"✅ {result.message}")  # noqa: T201
            print(f"   View at: https://pypi.org/project/{name}/")  # noqa: T201
        else:
            print(f"❌ {result.message}", file=sys.stderr)  # noqa: T201
            raise SystemExit(1)


@app.command()
def audit(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to audit"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    category: Annotated[
        str | None,
        cyclopts.Parameter(name=["--category", "-c"], help="Filter to one category"),
    ] = None,
) -> None:
    """Audit a project against the AXM gold standard."""
    from axm_init.core.auditor import AuditEngine, format_json, format_report

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    try:
        engine = AuditEngine(project_path, category=category)
        result = engine.run()
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from e

    if json_output:
        print(json.dumps(format_json(result), indent=2))  # noqa: T201
    else:
        print(format_report(result))  # noqa: T201

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
