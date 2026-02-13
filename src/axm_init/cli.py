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
from typing import Annotated, Any

import cyclopts

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.adapters.credentials import CredentialManager
from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter
from axm_init.core.reserver import reserve_pypi
from axm_init.core.templates import get_template_path

__all__ = ["app"]

app = cyclopts.App(
    name="axm-init",
    help="AXM Init — Python project scaffolding with Copier templates.",
)


def _check_pypi_availability(project_name: str, *, json_output: bool) -> None:
    """Check PyPI availability and exit(1) if name is taken."""
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

    if status == AvailabilityStatus.ERROR and not json_output:
        print(  # noqa: T201
            "⚠️  Could not verify PyPI availability",
            file=sys.stderr,
        )


def _print_init_result(
    result: Any,
    project_name: str,
    target_path: Path,
    *,
    json_output: bool,
) -> None:
    """Print init result as JSON or human-readable output."""
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
    ] = "MIT",
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
    project_name = name or target_path.name

    if check_pypi:
        _check_pypi_availability(project_name, json_output=json_output)

    copier_adapter = CopierAdapter()
    copier_config = CopierConfig(
        template_path=get_template_path(),
        destination=target_path,
        data={
            "package_name": project_name,
            "description": description or "A modern Python package",
            "org": org,
            "license": license,
            "license_holder": license_holder or org,
            "author_name": author,
            "author_email": email,
        },
    )
    result = copier_adapter.copy(copier_config)

    _print_init_result(result, project_name, target_path, json_output=json_output)


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
    ] = "John Doe",
    email: Annotated[
        str,
        cyclopts.Parameter(name=["--email", "-e"], help="Author email"),
    ] = "john.doe@example.com",
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
