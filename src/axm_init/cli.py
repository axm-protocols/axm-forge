"""AXM-Init CLI entry point — Project scaffolding tool."""

import json
from pathlib import Path

import typer

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.adapters.credentials import CredentialManager
from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter
from axm_init.core.reserver import reserve_pypi
from axm_init.core.templates import resolve_template

app = typer.Typer(
    name="axm-init",
    help="AXM Init — Python project scaffolding with Copier templates.",
    no_args_is_help=True,
)


@app.command()
def init(
    path: str = typer.Argument(".", help="Path to initialize project"),
    name: str | None = typer.Option(None, "--name", "-n", help="Project name"),
    template: str = typer.Option(
        "minimal", "--template", "-t", help="Template: python, minimal"
    ),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    check_pypi: bool = typer.Option(
        False, "--check-pypi", help="Check PyPI availability"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
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
                typer.echo(
                    f'{{"error": "Package name \'{project_name}\' is taken on PyPI"}}'
                )
            else:
                typer.echo(
                    f"❌ Package name '{project_name}' is already taken on PyPI",
                    err=True,
                )
            raise typer.Exit(1)
        if status == AvailabilityStatus.ERROR:
            if not json_output:
                typer.echo("⚠️  Could not verify PyPI availability", err=True)

    # Resolve template and scaffold with Copier
    try:
        template_info = resolve_template(template)
    except ValueError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1) from e

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
        typer.echo(
            json.dumps(
                {
                    "success": result.success,
                    "files": [str(f) for f in result.files_created],
                }
            )
        )
    else:
        if result.success:
            typer.echo(f"✅ Project '{project_name}' created at {target_path}")
            for f in result.files_created:
                typer.echo(f"   📄 {f}")
        else:
            typer.echo(f"❌ {result.message}", err=True)
            raise typer.Exit(1)


@app.command()
def reserve(
    name: str = typer.Argument(..., help="Package name to reserve"),
    author: str = typer.Option("Gabriel Jarry", "--author", "-a", help="Author name"),
    email: str = typer.Option(
        "jarry.gabriel@gmail.com", "--email", "-e", help="Author email"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip actual publish"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Reserve a package name on PyPI."""
    # Get token
    creds = CredentialManager()
    token = creds.get_pypi_token()

    if not token and not dry_run:
        if json_output:
            typer.echo('{"error": "No PyPI token found"}')
            raise typer.Exit(1)

        typer.echo("🔑 No PyPI token found in PYPI_API_TOKEN or ~/.pypirc")
        token_input = typer.prompt("Enter PyPI API token", hide_input=True)

        if not creds.validate_token(token_input):
            typer.echo("❌ Invalid token format (must start with 'pypi-')", err=True)
            raise typer.Exit(1)

        if typer.confirm("Save token to ~/.pypirc?"):
            creds.save_pypi_token(token_input)
            typer.echo("✅ Token saved")

        token = token_input

    result = reserve_pypi(
        name=name,
        author=author,
        email=email,
        token=token or "",
        dry_run=dry_run,
    )

    if json_output:
        typer.echo(
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
            typer.echo(f"✅ {result.message}")
            typer.echo(f"   View at: https://pypi.org/project/{name}/")
        else:
            typer.echo(f"❌ {result.message}", err=True)
            raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show axm-init version."""
    from axm_init import __version__

    typer.echo(f"axm-init {__version__}")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
