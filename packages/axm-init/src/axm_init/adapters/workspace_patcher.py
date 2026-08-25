"""Workspace patcher — patch root files after member scaffold.

Provides idempotent patching functions for workspace root files
(Makefile, mkdocs.yml, pyproject.toml, ci.yml, publish.yml, release.yml)
when a new member sub-package is added via ``scaffold --member``.
"""

from __future__ import annotations

__all__ = [
    "PatchReport",
    "patch_all",
    "patch_ci",
    "patch_dependabot",
    "patch_makefile",
    "patch_mkdocs",
    "patch_publish",
    "patch_pyproject",
    "patch_release",
    "patch_testpaths",
]

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def patch_makefile(root: Path, member_name: str) -> bool:
    """Append per-package test/lint targets for *member_name*.

    Adds ``test-<name>`` and ``lint-<name>`` Makefile targets.
    Idempotent — skips if targets already exist.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if the Makefile was modified, ``False`` if the targets
        already existed (no-op).

    Raises:
        FileNotFoundError: If ``Makefile`` is missing.
    """
    makefile = root / "Makefile"
    content = makefile.read_text()

    target = f"test-{member_name}"
    # Token-exact guard: match the target the patcher inserts (``<target>:``
    # at line start), not a bare substring — otherwise a prefix collision
    # (member ``foo`` vs an existing ``test-foo-bar:`` target) would silently
    # skip ``foo``. Mirrors the anchored guard in ``patch_ci``.
    if any(line.startswith(f"{target}:") for line in content.splitlines()):
        logger.info("Makefile already contains target %s — skipping", target)
        return False

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
    return True


def patch_mkdocs(root: Path, member_name: str) -> bool:
    """Add ``!include`` nav entry for *member_name*.

    Appends a nav entry referencing the member's ``mkdocs.yml``
    so the monorepo plugin picks it up.
    Idempotent — skips if entry already exists.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``mkdocs.yml`` was modified, ``False`` if the include
        entry already existed (no-op).

    Raises:
        FileNotFoundError: If ``mkdocs.yml`` is missing.
    """
    mkdocs = root / "mkdocs.yml"
    content = mkdocs.read_text()

    include = f"!include ./packages/{member_name}/mkdocs.yml"
    if include in content:
        logger.info("mkdocs.yml already includes %s — skipping", member_name)
        return False

    # Append nav entry at the end of the nav section
    entry = f"  - {member_name}: '{include}'\n"
    content = content.rstrip("\n") + "\n" + entry
    mkdocs.write_text(content)
    logger.info("Patched mkdocs.yml with !include for %s", member_name)
    return True


def patch_pyproject(root: Path, member_name: str) -> bool:
    """Register *member_name* as a UV workspace source.

    The primary effect is appending a ``[tool.uv.sources.<member_name>]``
    entry with ``workspace = true``. Additionally, **only if** a
    ``dependencies = [...]`` array is present in ``pyproject.toml``, the
    member is also added to it; on the shipped workspace template (which
    declares ``[dependency-groups]`` rather than ``[project.dependencies]``)
    this branch is a no-op and only the source entry is written.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``pyproject.toml`` was modified, ``False`` if the member
        was already registered (no-op).

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is missing.
    """
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()

    modified = False
    patched_deps = False

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
            # Ensure the preceding element carries a trailing comma before
            # inserting the new one — a single-line ``["axm-core"]`` (no
            # trailing comma, perfectly legal TOML) would otherwise produce
            # ``["axm-core"    "member",]`` and corrupt the whole workspace.
            head = content[:bracket_pos].rstrip()
            if head.endswith("["):
                new_dep = f'\n    "{member_name}",\n'
            elif head.endswith(","):
                new_dep = f'    "{member_name}",\n'
            else:
                content = content[:bracket_pos] + ",\n" + content[bracket_pos:]
                new_dep = f'    "{member_name}",\n'
                bracket_pos += 2
            content = content[:bracket_pos] + new_dep + content[bracket_pos:]
            modified = True
            patched_deps = True

    # 2. Add to [tool.uv.sources] if not present
    source_key = f"[tool.uv.sources.{member_name}]"
    if source_key not in content:
        # Append source entry
        source_block = f"\n{source_key}\nworkspace = true\n"
        content += source_block
        modified = True

    if modified:
        pyproject.write_text(content)
        effect = "dependency + source" if patched_deps else "source"
        logger.info("Patched pyproject.toml with %s (%s)", member_name, effect)
    else:
        logger.info("pyproject.toml already contains %s — skipping", member_name)
    return modified


def _detect_yaml_indent(lines: list[str], default: str = "          ") -> str:
    """Return the indentation of the last YAML list item in *lines*."""
    for line in reversed(lines):
        if line.strip().startswith("- "):
            return line[: len(line) - len(line.lstrip())]
    return default


def _advance_past_marker(lines: list[str], list_marker: str | None) -> int:
    """Return the first index to start scanning from (after the marker line).

    If *list_marker* is ``None``, returns ``0`` so the whole buffer is scanned.
    If the marker is never found, returns ``len(lines)`` so the outer loop
    yields no items.
    """
    if list_marker is None:
        return 0
    for i, line in enumerate(lines):
        if list_marker in line:
            return i + 1
    return len(lines)


def _find_yaml_list_range(
    lines: list[str],
    list_marker: str | None,
) -> tuple[int, int] | None:
    """Find the (start, end) indices of a YAML list.

    *start* is the index of the first ``- `` item.
    *end* is the index of the line **after** the last ``- `` item.
    If *list_marker* is given, the search begins only after that marker.
    Returns ``None`` if no list is found.

    The range is bounded by YAML indentation: once a non-empty line is
    found at an indent level at or above the first list item, the list is
    considered closed. This prevents the search from leaking into
    sibling / parent blocks (e.g. ``steps:`` siblings of
    ``matrix.package:``).
    """
    first = -1
    last = -1
    list_indent = -1

    for i in range(_advance_past_marker(lines, list_marker), len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            continue
        current_indent = len(line) - len(line.lstrip())

        if stripped.startswith("- "):
            if first == -1:
                first = i
                list_indent = current_indent
                last = i
            elif current_indent == list_indent:
                last = i
            else:
                # `- ` at a different indent — belongs to another list.
                break
        elif first >= 0 and current_indent <= list_indent:
            # Non-list line at or above the list's indent → list closed.
            break

    if first == -1:
        return None
    return first, last + 1


def _insert_into_yaml_list(
    lines: list[str],
    item_to_insert: str,
    list_marker: str | None = None,
    default_indent: str = "          ",
) -> tuple[list[str], bool]:
    """Insert an item into a YAML list after the last element.

    If *list_marker* is provided, insertion begins only after
    encountering it.  Uses a 2-pass approach: first locate the
    list boundaries, then insert at the correct position.

    Returns:
        A ``(lines, changed)`` pair. ``changed`` is ``False`` (and *lines*
        is returned unmodified) when no target list is found.
    """
    bounds = _find_yaml_list_range(lines, list_marker)
    if bounds is None:
        return list(lines), False

    _, end = bounds
    indent = _detect_yaml_indent(lines[:end], default=default_indent)
    new_line = f"{indent}- {item_to_insert}\n"
    return [*lines[:end], new_line, *lines[end:]], True


def patch_ci(root: Path, member_name: str) -> bool:
    """Add *member_name* to CI matrix package list.

    Inserts the package name in the ``strategy.matrix.package`` list
    of ``.github/workflows/ci.yml``.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``ci.yml`` was modified, ``False`` if the member was
        already listed or no matrix list was found (no-op).

    Raises:
        FileNotFoundError: If ``ci.yml`` is missing.
    """
    ci_yml = root / ".github" / "workflows" / "ci.yml"
    content = ci_yml.read_text()

    lines = content.splitlines(keepends=True)
    # Token-exact guard: match the matrix entry the patcher inserts
    # (``<indent>- <member_name>``), not a bare substring — otherwise a
    # prefix collision (``foo`` already listed) would silently skip
    # ``foo-bar``. Indentation is normalized away via ``strip``.
    matrix_entry = f"- {member_name}"
    if any(line.strip() == matrix_entry for line in lines):
        logger.info("ci.yml already contains %s — skipping", member_name)
        return False

    new_lines, changed = _insert_into_yaml_list(
        lines, member_name, list_marker="package:"
    )
    if not changed:
        logger.info("ci.yml has no matrix package list — skipping %s", member_name)
        return False
    ci_yml.write_text("".join(new_lines))
    logger.info("Patched ci.yml matrix with %s", member_name)
    return True


def _find_top_level_key_index(lines: list[str], key: str) -> int | None:
    """Return the index of the line holding the top-level mapping *key*.

    A top-level key sits at column 0 (no leading indentation), is not a
    comment, and its token before ``:`` equals *key* exactly. Anchors
    structurally so a ``# jobs:`` comment or an indented step name never
    masquerades as the real mapping key.

    Args:
        lines: File split with ``splitlines(keepends=True)``.
        key: Bare mapping key to anchor on (e.g. ``"jobs"``).

    Returns:
        Line index of the matching top-level key, or ``None`` if absent.
    """
    for idx, line in enumerate(lines):
        if line[:1].isspace() or line.lstrip().startswith("#"):
            continue
        head, sep, _ = line.strip().partition(":")
        if sep and head == key:
            return idx
    return None


def patch_publish(root: Path, member_name: str) -> bool:
    """Add tag trigger pattern for *member_name*.

    Adds a ``<member_name>/v*`` tag pattern to the publish workflow's
    ``on.push.tags`` or ``on.release`` trigger.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``publish.yml`` was modified, ``False`` if the tag
        pattern already existed or nothing changed (no-op).

    Raises:
        FileNotFoundError: If ``publish.yml`` is missing.
    """
    publish_yml = root / ".github" / "workflows" / "publish.yml"
    content = publish_yml.read_text()
    original = content

    tag_pattern = f"{member_name}/v*"
    if tag_pattern in content:
        logger.info("publish.yml already contains %s tag — skipping", member_name)
        return False

    # If there's a tags section, add the pattern there
    if "tags:" in content:
        lines = content.splitlines(keepends=True)
        new_lines, _ = _insert_into_yaml_list(
            lines, f'"{tag_pattern}"', list_marker="tags:", default_indent="      "
        )
        content = "".join(new_lines)
    else:
        # No tags section — add a push.tags trigger before the real
        # top-level ``jobs:`` mapping key. Anchor structurally (column-0,
        # exact key token, not a ``# jobs:`` comment or an indented step
        # name) instead of a first-substring replace; skip cleanly when no
        # top-level ``jobs:`` exists so the file is never corrupted.
        lines = content.splitlines(keepends=True)
        idx = _find_top_level_key_index(lines, "jobs")
        if idx is None:
            logger.info(
                "publish.yml has no top-level jobs: for %s — skipping",
                member_name,
            )
            return False
        lines.insert(idx, f'  push:\n    tags:\n      - "{tag_pattern}"\n\n')
        content = "".join(lines)

    if content == original:
        logger.info("publish.yml unchanged for %s — skipping", member_name)
        return False
    publish_yml.write_text(content)
    logger.info("Patched publish.yml with tag pattern %s", tag_pattern)
    return True


def patch_release(root: Path, member_name: str) -> bool:
    """Add tag trigger and detect block for *member_name* in release.yml.

    Adds a ``<member_name>/v*`` tag pattern and a corresponding
    detect block (elif branch) to the release workflow so git-cliff
    scopes changelogs per-package.
    Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``release.yml`` was modified, ``False`` if the tag
        pattern already existed or nothing changed (no-op).

    Raises:
        FileNotFoundError: If ``release.yml`` is missing.
    """
    release_yml = root / ".github" / "workflows" / "release.yml"
    content = release_yml.read_text()
    original = content

    tag_pattern = f"{member_name}/v*"
    if tag_pattern in content:
        logger.info("release.yml already contains %s — skipping", member_name)
        return False

    # 1. Add tag pattern — reuse the shared YAML list inserter
    if "tags:" in content:
        lines = content.splitlines(keepends=True)
        lines, _ = _insert_into_yaml_list(
            lines,
            f'"{tag_pattern}"',
            list_marker="tags:",
            default_indent="      ",
        )
        content = "".join(lines)

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

    if content == original:
        logger.info("release.yml unchanged for %s — skipping", member_name)
        return False
    release_yml.write_text(content)
    logger.info("Patched release.yml with tag pattern + detect for %s", member_name)
    return True


def _insert_into_toml_array(
    content: str,
    value: str,
    key: str = "testpaths",
    section: str = "[tool.pytest.ini_options]",
) -> str:
    """Insert *value* into a TOML array, creating the section if needed.

    Handles three cases:
    1. Section + key exist → append to array (single-line or multi-line).
    2. Section exists, key missing → add key with new array.
    3. Section missing → append entire section + key + array.
    """
    if section not in content:
        return content + f'\n{section}\n{key} = [\n    "{value}",\n]\n'

    if not _toml_key_present(content, key):
        return content.replace(
            section,
            f'{section}\n{key} = [\n    "{value}",\n]',
        )

    return _append_to_toml_array_lines(content, value, key)


def _toml_key_present(content: str, key: str) -> bool:
    """Return ``True`` if *content* has a top-level ``key = ...`` assignment.

    Matches the exact key token before ``=`` (ignoring surrounding
    whitespace), so ``testpaths`` never matches ``testpaths_extra``.
    """
    for line in content.splitlines():
        head, sep, _ = line.strip().partition("=")
        if sep and head.strip() == key:
            return True
    return False


def _append_to_toml_array_lines(content: str, value: str, key: str) -> str:
    """Append *value* to an existing TOML array (single-line or multi-line)."""
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    in_array = False

    for line in lines:
        stripped = line.strip()

        head, sep, _ = stripped.partition("=")
        if sep and head.strip() == key:
            if "]" in stripped:
                # Single-line: testpaths = ["a", "b"]
                pos = line.rindex("]")
                result.append(
                    line[:pos].rstrip().rstrip(",")
                    + ",\n"
                    + f'    "{value}",\n'
                    + line[pos:]
                )
                continue
            in_array = True

        if in_array and "]" in stripped:
            result.append(f'    "{value}",\n')
            in_array = False

        result.append(line)

    return "".join(result)


def patch_testpaths(root: Path, member_name: str) -> bool:
    """Ensure root testpaths includes the member's derived test suite.

    The suite is named ``tests_<module_name>`` rather than a shared ``tests``:
    a common directory name makes every member's ``tests.conftest`` resolve to
    the same module path, which kills collection at the workspace root.

    Adds the test directory of *member_name* to
    ``[tool.pytest.ini_options].testpaths`` in the root ``pyproject.toml``.
    Creates the section if it doesn't exist.
    Idempotent — skips if path already listed.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``pyproject.toml`` was modified, ``False`` if the test
        path was already listed (no-op).

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is missing.
    """
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()

    test_path = f"packages/{member_name}/tests_{member_name.replace('-', '_')}"
    if test_path in content:
        logger.info("testpaths already contains %s — skipping", test_path)
        return False

    content = _insert_into_toml_array(content, test_path)
    pyproject.write_text(content)
    logger.info("Patched testpaths with %s", test_path)
    return True


def patch_dependabot(root: Path, member_name: str) -> bool:
    """Add a per-package Dependabot entry for *member_name*.

    Appends a ``package-ecosystem: uv`` update block scoped to
    ``/packages/<member_name>`` so Dependabot keeps that published package's
    pyproject constraints current (its PyPI contract), alongside the shared
    workspace-root lockfile entry. The block is inserted before the trailing
    ``github-actions`` entry. Idempotent — skips if already present.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        ``True`` if ``dependabot.yml`` was modified, ``False`` if the member
        entry already existed (no-op).

    Raises:
        FileNotFoundError: If ``.github/dependabot.yml`` is missing.
    """
    dependabot_yml = root / ".github" / "dependabot.yml"
    content = dependabot_yml.read_text()

    member_dir = f"directory: /packages/{member_name}"
    if member_dir in content:
        logger.info("dependabot.yml already covers %s — skipping", member_name)
        return False

    block = (
        f"  - package-ecosystem: uv\n"
        f"    directory: /packages/{member_name}\n"
        f"    schedule:\n"
        f"      interval: weekly\n"
        f"    groups:\n"
        f"      {member_name}:\n"
        f"        patterns:\n"
        f'          - "*"\n'
    )

    anchor = "  - package-ecosystem: github-actions\n"
    if anchor in content:
        content = content.replace(anchor, block + anchor, 1)
    else:
        # No github-actions entry to anchor on — append at end of file.
        if not content.endswith("\n"):
            content += "\n"
        content += block

    dependabot_yml.write_text(content)
    logger.info("Patched dependabot.yml with per-package entry for %s", member_name)
    return True


@dataclass(frozen=True, slots=True)
class PatchReport:
    """Truthful accounting of a :func:`patch_all` run.

    Attributes:
        patched: Names of files a patcher actually modified.
        skipped: Names of files left unchanged — either a no-op (already
            patched) or absent (``FileNotFoundError``). Never overlaps
            *patched*.
        failed: Names of files whose patcher raised an unexpected error
            (``PermissionError``, ``UnicodeDecodeError``, …). A non-empty
            list is the partial-state signal.
    """

    patched: list[str]
    skipped: list[str]
    failed: list[str]

    @property
    def has_partial_failure(self) -> bool:
        """``True`` when at least one patcher failed unexpectedly."""
        return bool(self.failed)


def patch_all(root: Path, member_name: str) -> PatchReport:
    """Run all workspace patches for *member_name*.

    Calls each ``patch_*`` function and records, per file, whether it was
    actually modified (*patched*), left unchanged (*skipped* — no-op or
    missing file), or failed unexpectedly (*failed*). Non-``FileNotFoundError``
    exceptions are caught and surfaced as a partial-state signal instead of
    being raised, so a single unwritable file never aborts the whole run.

    Args:
        root: Workspace root directory.
        member_name: Name of the new member package.

    Returns:
        A :class:`PatchReport` partitioning every patcher into patched /
        skipped / failed. ``patched`` lists only files with a real write.
    """
    patched: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    patchers = [
        ("Makefile", patch_makefile),
        ("mkdocs.yml", patch_mkdocs),
        ("pyproject.toml", patch_pyproject),
        ("pyproject.toml (testpaths)", patch_testpaths),
        (".github/workflows/ci.yml", patch_ci),
        (".github/workflows/publish.yml", patch_publish),
        (".github/workflows/release.yml", patch_release),
        (".github/dependabot.yml", patch_dependabot),
    ]

    for name, fn in patchers:
        try:
            if fn(root, member_name):
                patched.append(name)
            else:
                skipped.append(name)
        except FileNotFoundError:
            logger.warning("Skipping %s — file not found", name)
            skipped.append(name)
        except (OSError, UnicodeDecodeError) as exc:
            logger.error("Failed to patch %s — %s", name, exc)
            failed.append(name)

    return PatchReport(patched=patched, skipped=skipped, failed=failed)
