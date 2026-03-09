"""PyPI Reserver — reserve package names on PyPI.

Publishes a minimal placeholder package (0.0.1.dev0) to secure
the package name before full implementation.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter
from axm_init.models.results import ReserveResult

logger = logging.getLogger(__name__)

# Placeholder version for reservation
RESERVE_VERSION = "0.0.1.dev0"

# Minimal pyproject.toml template
PYPROJECT_TEMPLATE = """[project]
name = "{name}"
version = "{version}"
description = "Package name reserved — implementation coming soon"
readme = "README.md"
license = {{ text = "MIT" }}
requires-python = ">=3.12"
authors = [{{ name = "{author}", email = "{email}" }}]
classifiers = [
    "Development Status :: 1 - Planning",
    "Programming Language :: Python :: 3.12",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

README_TEMPLATE = "# {name}\n\nPackage name reserved. Implementation coming soon.\n"


def create_minimal_package(
    name: str,
    author: str,
    email: str,
    target_path: Path,
    version: str = RESERVE_VERSION,
) -> None:
    """Create minimal package structure for PyPI reservation.

    Args:
        name: Package name (with hyphens).
        author: Author name.
        email: Author email.
        target_path: Directory to create package in.
        version: Version string.
    """
    module_name = name.replace("-", "_")

    # pyproject.toml
    pyproject = target_path / "pyproject.toml"
    pyproject.write_text(
        PYPROJECT_TEMPLATE.format(
            name=name,
            version=version,
            author=author,
            email=email,
        )
    )

    # README.md
    readme = target_path / "README.md"
    readme.write_text(README_TEMPLATE.format(name=name))

    # src/module/__init__.py
    src_dir = target_path / "src" / module_name
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (src_dir / "py.typed").touch()


def build_package(path: Path) -> tuple[bool, str]:
    """Build package using uv build.

    Returns:
        (success, error_message)
    """
    result = subprocess.run(
        ["uv", "build"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, ""


def publish_package(path: Path, token: str) -> tuple[bool, str]:
    """Publish package to PyPI using uv publish.

    The token is passed via the ``UV_PUBLISH_TOKEN`` environment variable
    instead of ``--token`` CLI argument to avoid exposure via ``ps`` or
    ``/proc/<pid>/cmdline``.

    Returns:
        (success, error_message)
    """
    import os

    env = {**os.environ, "UV_PUBLISH_TOKEN": token}
    result = subprocess.run(
        ["uv", "publish"],
        cwd=path,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        return False, result.stderr
    return True, ""


def reserve_pypi(
    name: str,
    author: str,
    email: str,
    token: str,
    dry_run: bool = False,
) -> ReserveResult:
    """Reserve a package name on PyPI.

    Args:
        name: Package name to reserve.
        author: Author name.
        email: Author email.
        token: PyPI API token.
        dry_run: If True, skip actual publish.

    Returns:
        ReserveResult with success status.
    """
    # Check availability first
    adapter = PyPIAdapter()
    status = adapter.check_availability(name)

    if status == AvailabilityStatus.TAKEN:
        return ReserveResult(
            success=False,
            package_name=name,
            version=RESERVE_VERSION,
            message=f"Package '{name}' is already taken on PyPI",
        )

    if status == AvailabilityStatus.ERROR:
        return ReserveResult(
            success=False,
            package_name=name,
            version=RESERVE_VERSION,
            message="Failed to check PyPI availability",
        )

    # Dry run mode
    if dry_run:
        return ReserveResult(
            success=True,
            package_name=name,
            version=RESERVE_VERSION,
            message=f"Dry run — would reserve '{name}' on PyPI",
        )

    # Create and publish
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        create_minimal_package(name, author, email, temp_path)

        # Build
        success, error = build_package(temp_path)
        if not success:
            return ReserveResult(
                success=False,
                package_name=name,
                version=RESERVE_VERSION,
                message=f"Build failed: {error}",
            )

        # Publish
        success, error = publish_package(temp_path, token)
        if not success:
            if "already exists" in error.lower():
                # Re-check to distinguish idempotent re-run from race condition.
                # If we reach here, initial check was AVAILABLE. Re-check now:
                # - TAKEN  → someone else published between check and publish
                # - AVAILABLE/ERROR → our own prior reservation (idempotent)
                recheck = adapter.check_availability(name)
                if recheck == AvailabilityStatus.TAKEN:
                    logger.warning(
                        "Race condition: '%s' was taken between availability "
                        "check and publish",
                        name,
                    )
                    return ReserveResult(
                        success=False,
                        package_name=name,
                        version=RESERVE_VERSION,
                        message=(
                            f"Package '{name}' was taken by another user "
                            "between availability check and publish"
                        ),
                    )
                return ReserveResult(
                    success=True,
                    package_name=name,
                    version=RESERVE_VERSION,
                    message=f"Package '{name}' already reserved",
                )
            return ReserveResult(
                success=False,
                package_name=name,
                version=RESERVE_VERSION,
                message=f"Publish failed: {error}",
            )

    return ReserveResult(
        success=True,
        package_name=name,
        version=RESERVE_VERSION,
        message=f"Reserved '{name}' on PyPI (version {RESERVE_VERSION})",
    )
