"""Makefile adapter — detect and use Makefile targets."""

import re
from pathlib import Path


def detect_makefile_targets(project_path: Path) -> set[str]:
    """Detect available targets in a project's Makefile.

    Args:
        project_path: Root directory of the project.

    Returns:
        Set of target names found in the Makefile.
    """
    makefile = project_path / "Makefile"
    if not makefile.exists():
        return set()

    try:
        content = makefile.read_text()
    except (OSError, UnicodeDecodeError):
        return set()

    # Match target definitions: "target_name:" at start of line
    target_pattern = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):", re.MULTILINE)
    targets = set(target_pattern.findall(content))

    return targets


def get_tool_command(
    project_path: Path,
    makefile_target: str,
    fallback_cmd: list[str],
) -> list[str]:
    """Get the command to run a tool, preferring Makefile targets.

    If the project has a Makefile with the specified target, uses `make <target>`.
    Otherwise, returns the fallback command.

    Args:
        project_path: Root directory of the project.
        makefile_target: Target name to look for in Makefile.
        fallback_cmd: Command to use if target not found.

    Returns:
        Command list to execute.
    """
    targets = detect_makefile_targets(project_path)

    if makefile_target in targets:
        return ["make", makefile_target]

    return fallback_cmd
