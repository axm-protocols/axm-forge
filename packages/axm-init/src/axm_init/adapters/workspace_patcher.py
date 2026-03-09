"""Workspace patcher — patch root files after member scaffold.

Provides idempotent patching functions for workspace root files
(Makefile, mkdocs.yml, pyproject.toml, ci.yml, publish.yml, release.yml)
when a new member sub-package is added via ``scaffold --member``.
"""

from __future__ import annotations

__all__ = [
    "patch_all",
    "patch_ci",
    "patch_makefile",
    "patch_mkdocs",
    "patch_publish",
    "patch_pyproject",
    "patch_release",
    "patch_testpaths",
]

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def patch_makefile(root: Path, member_name: str) -> None:
    """Append per-package test/lint targets for *member_name*.

    Adds ``test-<name>`` and ``lint-<name>`` Makefile targets.
    Idempotent — skips if targets already exist.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``Makefile`` is missing.
    """
    makefile = root / "Makefile"
    content = makefile.read_text()

    target = f"test-{member_name}"
    if target in content:
        logger.info("Makefile already contains target %s — skipping", target)
        return

    module_name = member_name.replace("-", "_")
    block = (
        f"\n## Test {member_name}\n"
        f"{target}:\n"
        f"\tuv run pytest --package {member_name} -q\n"
        f"\n## Lint {member_name}\n"
        f"lint-{member_name}:\n"
        f"\tuv run ruff check packages/{member_name}/src/{module_name}/\n"
    )
    makefile.write_text(content + block)
    logger.info("Patched Makefile with targets for %s", member_name)


def patch_mkdocs(root: Path, member_name: str) -> None:
    """Add ``!include`` nav entry for *member_name*.

    Appends a nav entry referencing the member's ``mkdocs.yml``
    so the monorepo plugin picks it up.
    Idempotent — skips if entry already exists.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``mkdocs.yml`` is missing.
    """
    mkdocs = root / "mkdocs.yml"
    content = mkdocs.read_text()

    include = f"!include ./packages/{member_name}/mkdocs.yml"
    if include in content:
        logger.info("mkdocs.yml already includes %s — skipping", member_name)
        return

    # Append nav entry at the end of the nav section
    entry = f"  - {member_name}: '{include}'\n"
    content = content.rstrip("\n") + "\n" + entry
    mkdocs.write_text(content)
    logger.info("Patched mkdocs.yml with !include for %s", member_name)


def patch_pyproject(root: Path, member_name: str) -> None:
    """Add *member_name* to workspace dependencies and UV sources.

    Adds the package to ``[project.dependencies]`` and adds a
    ``[tool.uv.sources.<member_name>]`` entry with ``workspace = true``.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is missing.
    """
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()

    modified = False

    # 1. Add to dependencies array if not present
    dep_pattern = re.compile(r"^dependencies\s*=\s*\[", re.MULTILINE)
    # Check if member_name appears in the deps section (before sources)
    sources_marker = "[tool.uv.sources]"
    if sources_marker in content:
        deps_section = content.split(sources_marker)[0]
    else:
        deps_section = content
    if f'"{member_name}"' not in deps_section:
        match = dep_pattern.search(content)
        if match:
            # Find the closing bracket of dependencies
            start = match.end()
            bracket_pos = content.index("]", start)
            new_dep = f'    "{member_name}",\n'
            content = content[:bracket_pos] + new_dep + content[bracket_pos:]
            modified = True

    # 2. Add to [tool.uv.sources] if not present
    source_key = f"[tool.uv.sources.{member_name}]"
    if source_key not in content:
        # Append source entry
        source_block = f"\n{source_key}\nworkspace = true\n"
        content += source_block
        modified = True

    if modified:
        pyproject.write_text(content)
        logger.info("Patched pyproject.toml with %s dependency + source", member_name)
    else:
        logger.info("pyproject.toml already contains %s — skipping", member_name)


def _insert_into_yaml_list(
    lines: list[str],
    item_to_insert: str,
    list_marker: str | None = None,
    default_indent: str = "          ",
) -> list[str]:
    """Insert an item into a YAML list after the last element.

    If list_marker is provided, insertion begins only after encountering it.
    """
    new_lines: list[str] = []
    in_list = False
    inserted = False

    for line in lines:
        new_lines.append(line)
        stripped = line.strip()

        if list_marker and list_marker in line and not inserted:
            in_list = True
            continue

        if (
            not list_marker
            and not in_list
            and not inserted
            and stripped.startswith("- ")
        ):
            in_list = True

        if in_list and stripped.startswith("- "):
            continue

        if in_list and not stripped.startswith("- ") and not inserted:
            indent = default_indent
            for prev_line in reversed(new_lines[:-1]):
                if prev_line.strip().startswith("- "):
                    indent = prev_line[: len(prev_line) - len(prev_line.lstrip())]
                    break
            new_lines.insert(len(new_lines) - 1, f"{indent}- {item_to_insert}\n")
            in_list = False
            inserted = True

    if not inserted and in_list:
        indent = default_indent
        for prev_line in reversed(new_lines):
            if prev_line.strip().startswith("- "):
                indent = prev_line[: len(prev_line) - len(prev_line.lstrip())]
                break
        new_lines.append(f"{indent}- {item_to_insert}\n")

    return new_lines


def patch_ci(root: Path, member_name: str) -> None:
    """Add *member_name* to CI matrix package list.

    Inserts the package name in the ``strategy.matrix.package`` list
    of ``.github/workflows/ci.yml``.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``ci.yml`` is missing.
    """
    ci_yml = root / ".github" / "workflows" / "ci.yml"
    content = ci_yml.read_text()

    if member_name in content:
        logger.info("ci.yml already contains %s — skipping", member_name)
        return

    lines = content.splitlines(keepends=True)
    new_lines = _insert_into_yaml_list(lines, member_name, list_marker="package:")
    ci_yml.write_text("".join(new_lines))
    logger.info("Patched ci.yml matrix with %s", member_name)


def patch_publish(root: Path, member_name: str) -> None:
    """Add tag trigger pattern for *member_name*.

    Adds a ``<member_name>/v*`` tag pattern to the publish workflow's
    ``on.push.tags`` or ``on.release`` trigger.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``publish.yml`` is missing.
    """
    publish_yml = root / ".github" / "workflows" / "publish.yml"
    content = publish_yml.read_text()

    tag_pattern = f"{member_name}/v*"
    if tag_pattern in content:
        logger.info("publish.yml already contains %s tag — skipping", member_name)
        return

    # If there's a tags section, add the pattern there
    if "tags:" in content:
        lines = content.splitlines(keepends=True)
        new_lines = _insert_into_yaml_list(
            lines, f'"{tag_pattern}"', list_marker="tags:", default_indent="      "
        )
        content = "".join(new_lines)
    else:
        # No tags section — add push.tags trigger
        # Insert before the jobs: section
        content = content.replace(
            "jobs:",
            f'  push:\n    tags:\n      - "{tag_pattern}"\n\njobs:',
        )

    publish_yml.write_text(content)
    logger.info("Patched publish.yml with tag pattern %s", tag_pattern)


def patch_release(root: Path, member_name: str) -> None:
    """Add tag trigger and detect block for *member_name* in release.yml.

    Adds a ``<member_name>/v*`` tag pattern and a corresponding
    detect block (elif branch) to the release workflow so git-cliff
    scopes changelogs per-package.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``release.yml`` is missing.
    """
    release_yml = root / ".github" / "workflows" / "release.yml"
    content = release_yml.read_text()

    tag_pattern = f"{member_name}/v*"
    if tag_pattern in content:
        logger.info("release.yml already contains %s — skipping", member_name)
        return

    # 1. Add tag pattern to the tags: section
    if "tags:" in content:
        lines = content.splitlines(keepends=True)
        new_lines: list[str] = []
        in_tags = False

        for line in lines:
            new_lines.append(line)
            if "tags:" in line:
                in_tags = True
                continue

            if in_tags and line.strip().startswith("- "):
                continue

            if in_tags and not line.strip().startswith("- "):
                indent = "      "
                for prev_line in reversed(new_lines[:-1]):
                    if prev_line.strip().startswith("- "):
                        indent = prev_line[: len(prev_line) - len(prev_line.lstrip())]
                        break
                new_lines.insert(len(new_lines) - 1, f'{indent}- "{tag_pattern}"\n')
                in_tags = False

        content = "".join(new_lines)

    # 2. Add detect elif block before the "else" in the detect step
    pkg_dir = f"packages/{member_name}"
    detect_block = (
        f'          elif [[ "$TAG" == {member_name}/* ]]; then\n'
        f'            echo "package={member_name}" >> "$GITHUB_OUTPUT"\n'
        f'            echo "package-dir={pkg_dir}" >> "$GITHUB_OUTPUT"\n'
    )
    if "else" in content:
        content = content.replace(
            "          else\n",
            detect_block + "          else\n",
        )

    release_yml.write_text(content)
    logger.info("Patched release.yml with tag pattern + detect for %s", member_name)


def patch_testpaths(root: Path, member_name: str) -> None:
    """Ensure root testpaths includes ``packages/<member_name>/tests``.

    Adds the test directory of *member_name* to
    ``[tool.pytest.ini_options].testpaths`` in the root ``pyproject.toml``.
    Creates the section if it doesn't exist.
    Idempotent — skips if path already listed.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is missing.
    """
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()

    test_path = f"packages/{member_name}/tests"
    if test_path in content:
        logger.info("testpaths already contains %s — skipping", test_path)
        return

    # Check if [tool.pytest.ini_options] section exists
    if "[tool.pytest.ini_options]" in content:
        # Check if testpaths key exists
        if "testpaths" in content:
            # Add to existing testpaths array
            # Find the testpaths line and add the new path
            lines = content.splitlines(keepends=True)
            new_lines: list[str] = []
            in_testpaths = False

            for line in lines:
                new_lines.append(line)
                stripped = line.strip()

                if stripped.startswith("testpaths") and "=" in stripped:
                    in_testpaths = True
                    # If it's a single-line list, we need to insert before ]
                    if "]" in stripped:
                        # Single-line: testpaths = ["a", "b"]
                        bracket_pos = line.rindex("]")
                        new_entry = f'    "{test_path}",\n'
                        new_lines[-1] = (
                            line[:bracket_pos].rstrip().rstrip(",")
                            + ",\n"
                            + new_entry
                            + line[bracket_pos:]
                        )
                        in_testpaths = False
                    continue

                if in_testpaths and "]" in stripped:
                    # End of multi-line testpaths — insert before ]
                    indent = "    "
                    new_lines.insert(len(new_lines) - 1, f'{indent}"{test_path}",\n')
                    in_testpaths = False

            content = "".join(new_lines)
        else:
            # Add testpaths key to existing section
            content = content.replace(
                "[tool.pytest.ini_options]",
                f'[tool.pytest.ini_options]\ntestpaths = [\n    "{test_path}",\n]',
            )
    else:
        # Create the entire section
        content += (
            f'\n[tool.pytest.ini_options]\ntestpaths = [\n    "{test_path}",\n]\n'
        )

    pyproject.write_text(content)
    logger.info("Patched testpaths with %s", test_path)


def patch_all(root: Path, member_name: str) -> list[str]:
    """Run all workspace patches for *member_name*.

    Calls each ``patch_*`` function and collects the names of
    successfully patched files.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        List of patched file names (relative to *root*).
    """
    patched: list[str] = []

    patchers = [
        ("Makefile", patch_makefile),
        ("mkdocs.yml", patch_mkdocs),
        ("pyproject.toml", patch_pyproject),
        ("pyproject.toml (testpaths)", patch_testpaths),
        (".github/workflows/ci.yml", patch_ci),
        (".github/workflows/publish.yml", patch_publish),
        (".github/workflows/release.yml", patch_release),
    ]

    for name, fn in patchers:
        try:
            fn(root, member_name)
            patched.append(name)
        except FileNotFoundError:
            logger.warning("Skipping %s — file not found", name)

    return patched
