"""Subprocess runners for git, gh, and uv commands."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from axm.tools.base import ToolResult

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_GH_TIMEOUT",
    "DEFAULT_GIT_TIMEOUT",
    "detect_package_name",
    "find_git_root",
    "gh_available",
    "not_a_repo_error",
    "parse_porcelain_z",
    "reset_paths",
    "resolve_default_branch",
    "run_gh",
    "run_git",
    "stage_spec_files",
    "staged_delta",
    "suggest_git_repos",
    "timeout_error_result",
]

# Minimum length of a porcelain record: 2-char XY status + space + 1-char path.
_MIN_PORCELAIN_RECORD_LEN = 4


def staged_delta(before: set[str], after: set[str]) -> list[str]:
    """Return the sorted paths staged between two index snapshots.

    The delta is ``after - before`` — exactly the paths a staging operation
    introduced, excluding anything a third party had already staged before
    the call. Sorted for deterministic output.
    """
    return sorted(after - before)


def reset_paths(paths: list[str], git_root: Path) -> None:
    """Unstage exactly *paths* via a scoped ``git reset -- <paths>``.

    Restoration is strictly scoped to *paths*: it never runs a bare
    ``git reset`` (which would unstage the whole index, including third-party
    staged files) and never touches the worktree (no checkout/clean). A
    no-op when *paths* is empty.
    """
    if not paths:
        return
    run_git(["reset", "--quiet", "--", *paths], git_root)


def stage_spec_files(
    files: list[str],
    git_root: Path,
    *,
    working_dir: Path | None = None,
    warnings: list[str] | None = None,
) -> str | None:
    """Stage each file in *files*, returning an error message on failure.

    Paths in *files* are resolved against *git_root* first, then against
    *working_dir* (if provided and distinct), so both git-root-relative
    and package-relative inputs work transparently. Absolute inputs are
    accepted when they point inside *git_root*.

    Tracked-but-deleted files (git status ``D``) are staged as deletions.
    Gitignored files are skipped with a warning appended to *warnings*.
    Truly missing files (never tracked) produce a clear diagnostic error
    listing every absolute path that was attempted.
    """
    for filepath in files:
        err = _stage_single_file(filepath, git_root, working_dir, warnings)
        if err:
            return err
    return None


def _resolve_repo_path(
    filepath: str,
    git_root: Path,
    working_dir: Path | None,
) -> tuple[Path | None, list[Path], str | None]:
    """Resolve *filepath* to an absolute path inside *git_root*.

    Tries ``git_root / filepath`` then ``working_dir / filepath`` (when
    *working_dir* is passed and differs from *git_root*). Absolute inputs
    are accepted verbatim when they resolve inside *git_root*.

    Returns ``(resolved, tried, error)``. On success ``resolved`` is the
    absolute path (which may not exist if the file is tracked-but-deleted)
    and ``error`` is ``None``. On out-of-tree absolute input, ``error``
    describes the violation. If neither candidate exists, ``resolved`` is
    ``None`` and callers can decide whether that is fatal.
    """
    git_root_abs = git_root.resolve()
    raw = Path(filepath)
    if raw.is_absolute():
        resolved = raw.resolve()
        if not resolved.is_relative_to(git_root_abs):
            return (
                None,
                [resolved],
                (
                    f"absolute path outside repository: {filepath} "
                    f"(git_root: {git_root_abs})"
                ),
            )
        return resolved, [resolved], None

    tried: list[Path] = []
    candidates = [git_root_abs / filepath]
    if working_dir is not None and working_dir.resolve() != git_root_abs:
        candidates.append(working_dir.resolve() / filepath)
    for candidate in candidates:
        tried.append(candidate)
        if candidate.exists():
            return candidate, tried, None
    return None, tried, None


def _resolve_add_target(
    filepath: str,
    git_root: Path,
    working_dir: Path | None,
) -> tuple[str, str | None]:
    """Return the path to pass to ``git add`` for *filepath*.

    When the resolved path exists on disk it is used verbatim. When it
    does not exist but ``git ls-files -d`` reports it as tracked-but-deleted,
    *filepath* is returned so git stages the deletion. Otherwise an error
    listing every attempted path is returned.
    """
    resolved, tried, err = _resolve_repo_path(filepath, git_root, working_dir)
    if err:
        return "", err
    if resolved is not None and resolved.exists():
        return str(resolved), None
    # Tracked-but-deleted: probe ``git ls-files -d`` with each candidate path
    # relativized to git_root (``ls-files`` interprets the pathspec relative
    # to its cwd, which is git_root). Return that git_root-relative path so
    # the deletion stages even when working_dir is a subdir of git_root.
    git_root_abs = git_root.resolve()
    for candidate in tried:
        if not candidate.is_relative_to(git_root_abs):
            continue
        rel = candidate.relative_to(git_root_abs).as_posix()
        ls_result = run_git(["ls-files", "-d", rel], git_root)
        if ls_result.stdout.strip():
            return rel, None
    attempts = ", ".join(str(p) for p in tried)
    return "", f"files not found: {filepath!r} (tried: {attempts})"


def _stage_single_file(
    filepath: str,
    git_root: Path,
    working_dir: Path | None,
    warnings: list[str] | None,
) -> str | None:
    """Stage one file, returning an error message on failure."""
    add_target, err = _resolve_add_target(filepath, git_root, working_dir)
    if err:
        return err
    add_result = run_git(["add", "--", add_target], git_root)
    if add_result.returncode == 0:
        return None
    if "ignored" in add_result.stderr.lower():
        if warnings is not None:
            warnings.append(f"skipped gitignored file: {filepath}")
        return None
    return f"git add failed for {filepath}: {add_result.stderr}"


def parse_porcelain_z(status_stdout: str) -> list[dict[str, str]]:
    """Parse ``git status --porcelain -z`` output into ``{path, status}`` rows.

    Records are NUL-terminated rather than newline-terminated, so paths with
    spaces are emitted verbatim (unquoted, unescaped). Rename/copy entries
    (``R``/``C``) span two NUL-separated fields — ``XY <space>dest`` followed
    by the original source path — so the destination is kept as ``path`` and
    the trailing source field is consumed and discarded.

    Args:
        status_stdout: Raw stdout from ``git status --porcelain -z``.

    Returns:
        List of ``{"path", "status"}`` dicts in encounter order.
    """
    records = [rec for rec in status_stdout.split("\x00") if rec]
    files: list[dict[str, str]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < _MIN_PORCELAIN_RECORD_LEN:
            continue
        status = record[:2].strip()
        files.append({"path": record[3:], "status": status})
        # Rename/copy entries carry a trailing source-path field; skip it.
        if record[:2].strip(" ?")[:1] in {"R", "C"}:
            index += 1
    return files


# Interim defaults — will be replaced by axm-common.run_safe.
DEFAULT_GIT_TIMEOUT = 30.0
DEFAULT_GH_TIMEOUT = 120.0


def timeout_error_result(exc: subprocess.TimeoutExpired) -> ToolResult:
    """Build a ``ToolResult`` for a ``subprocess.TimeoutExpired``."""
    cmd = exc.cmd
    if isinstance(cmd, (list, tuple)) and cmd:
        cmd_str = str(cmd[0])
    else:
        cmd_str = str(cmd)
    return ToolResult(
        success=False,
        error=f"{cmd_str} timed out after {exc.timeout}s",
    )


_ORIGIN_HEAD_PREFIX = "refs/remotes/origin/"


def resolve_default_branch(working_dir: Path) -> str:
    """Resolve the repository's default branch.

    Reads ``git symbolic-ref refs/remotes/origin/HEAD`` (e.g.
    ``refs/remotes/origin/master``) and strips the
    ``refs/remotes/origin/`` prefix. Falls back to ``"main"`` when the
    command fails or returns an empty/unexpected value (for instance a
    repo with no ``origin/HEAD`` ref).

    Args:
        working_dir: A directory inside the git repository.

    Returns:
        The default branch name, or ``"main"`` as a fallback.
    """
    result = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], working_dir)
    ref = result.stdout.strip()
    if result.returncode != 0 or not ref.startswith(_ORIGIN_HEAD_PREFIX):
        return "main"
    branch = ref.removeprefix(_ORIGIN_HEAD_PREFIX)
    return branch or "main"


def find_git_root(path: Path) -> Path | None:
    """Find the git repository root containing *path*.

    Uses ``git rev-parse --show-toplevel`` which walks up the directory
    tree, supporting mono-repo and workspace layouts where ``.git``
    lives above the package directory.

    Args:
        path: Any directory that may be inside a git repository.

    Returns:
        Repository root as a ``Path``, or ``None`` if *path* is not
        inside a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git rev-parse timed out after %ss", DEFAULT_GIT_TIMEOUT)
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def run_git(
    args: list[str],
    cwd: Path,
    *,
    timeout: float | None = DEFAULT_GIT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given directory.

    Args:
        args: Git subcommand and arguments (e.g. ``["status", "--short"]``).
        cwd: Working directory (project root).
        timeout: Subprocess timeout in seconds (default 30.0). Use
            ``None`` to disable.

    Returns:
        Completed process result with ``capture_output=True`` and ``text=True``.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds *timeout*.
            Callers should catch and convert via :func:`timeout_error_result`.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git %s timed out after %ss", args[0] if args else "", timeout)
        raise


def gh_available() -> bool:
    """Check whether the GitHub CLI is installed and authenticated."""
    if not shutil.which("gh"):
        return False
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("gh auth status timed out after %ss", DEFAULT_GIT_TIMEOUT)
        return False
    return result.returncode == 0


def run_gh(
    args: list[str],
    cwd: Path,
    *,
    timeout: float | None = DEFAULT_GH_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command.

    Args:
        args: gh subcommand and arguments.
        cwd: Working directory (project root).
        timeout: Subprocess timeout in seconds (default 120.0). Use
            ``None`` to disable.

    Returns:
        Completed process result with ``capture_output=True`` and ``text=True``.

    Raises:
        FileNotFoundError: If ``gh`` is not installed.
        subprocess.TimeoutExpired: If the command exceeds *timeout*.
            Callers should catch and convert via :func:`timeout_error_result`.
    """
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=str(cwd),
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("gh %s timed out after %ss", args[0] if args else "", timeout)
        raise


def detect_package_name(project_path: Path) -> str | None:
    """Read the package name from ``pyproject.toml``.

    Args:
        project_path: Project root containing ``pyproject.toml``.

    Returns:
        Package name or ``None`` if not found.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return None

    try:
        import tomllib

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("name")  # type: ignore[no-any-return]
    except (OSError, KeyError, ValueError):
        return None


def suggest_git_repos(path: Path) -> list[str]:
    """Find immediate child directories that are git repositories.

    Scans one level deep for subdirectories containing a ``.git`` dir.
    Returns a sorted list of directory names.  If *path* is itself a
    git repository (has ``.git/`` at root), returns an empty list.

    Args:
        path: Directory to scan.

    Returns:
        Sorted list of child directory names that are git repos.
    """
    if (path / ".git").is_dir():
        return []

    repos: list[str] = []
    try:
        children = sorted(path.iterdir())
    except (PermissionError, FileNotFoundError):
        return []

    for child in children:
        if not child.is_dir():
            continue
        try:
            if (child / ".git").is_dir():
                repos.append(child.name)
        except PermissionError:
            continue

    return repos


def not_a_repo_error(stderr: str, path: Path) -> ToolResult:
    """Build a ``ToolResult`` for a failed git command.

    If *stderr* contains ``"not a git repository"`` and *path* has
    child directories that are git repos, the error message is enriched
    with suggestions.  Otherwise a standard error is returned.

    Args:
        stderr: Stderr output from the failed git command.
        path: Directory that was used as ``cwd``.

    Returns:
        ``ToolResult(success=False, ...)`` with optional suggestions.
    """
    msg = stderr.strip()

    if "not a git repository" not in msg:
        return ToolResult(success=False, error=msg)

    suggestions = suggest_git_repos(path)
    if suggestions:
        hint = ", ".join(suggestions)
        return ToolResult(
            success=False,
            error=(
                f"{msg}. This directory contains git repos: {hint}. "
                f"Pass one of these as the path instead."
            ),
            data={"suggestions": suggestions},
        )

    return ToolResult(success=False, error=msg)
