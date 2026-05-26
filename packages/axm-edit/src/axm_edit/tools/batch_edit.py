"""BatchEditTool — atomic batch file editing for AI agents.

Registered as ``batch_edit`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import (
    CreateOp,
    DeleteOp,
    Operation,
    ReplaceOp,
)
from axm_edit.services import lint as _lint
from axm_edit.services.lint import claude_fix
from axm_edit.services.lint_diff import compute_lint_diffs, extract_rules_by_file


def _collect_python_files(root: Path, operations: list[Operation]) -> list[Path]:
    """Extract resolved paths of Python files from operations."""
    paths: list[Path] = []
    for op in operations:
        if hasattr(op, "file") and op.file.endswith(".py"):
            resolved = root / op.file
            if resolved.is_file():
                paths.append(resolved)
    return sorted(set(paths))


def _ruff_check(
    root: Path,
    str_files: list[str],
    extend: list[str],
    *,
    warnings: list[str] | None = None,
) -> list[str]:
    """Run ``ruff check`` and return diagnostic lines."""
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "--output-format=concise",
                *extend,
                *str_files,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff check failed: {exc}")
        return []

    if result.returncode > 1:
        if warnings is not None:
            warnings.append(f"ruff crashed (exit {result.returncode}), lint skipped")
        return []

    if result.returncode != 0 and result.stdout.strip():
        return [
            line
            for line in result.stdout.strip().splitlines()
            if line.strip()
            and not line.startswith("Found ")
            and not line.startswith("[*] ")
            and not line.startswith("No fixes")
        ]
    return []


def _run_ruff(
    root: Path,
    files: list[Path],
    *,
    warnings: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Run ruff fix then check on *files*.

    Returns:
        Tuple of (auto-fixed diagnostic lines, remaining diagnostic lines).
    """
    if not _lint._has_ruff:
        if warnings is not None:
            warnings.append("ruff not found, lint skipped")
        return [], []

    str_files = [str(f) for f in files]
    extend = ["--extend-select", "I"]

    # Snapshot diagnostics before fix
    before = _ruff_check(root, str_files, extend, warnings=warnings)

    # Auto-fix what we can
    try:
        subprocess.run(
            ["uv", "run", "ruff", "check", "--fix", "--exit-zero", *extend, *str_files],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff fix failed: {exc}")
        return [], []

    # Format files
    try:
        subprocess.run(
            ["uv", "run", "ruff", "format", *str_files],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff format failed: {exc}")

    # Check remaining after fix
    remaining = _ruff_check(root, str_files, extend, warnings=warnings)

    remaining_set = set(remaining)
    auto_fixed = [e for e in before if e not in remaining_set]

    return auto_fixed, remaining


def _parse_operations(raw_ops: list[dict[str, Any]]) -> list[Operation]:
    """Parse raw dicts into typed Operation models.

    Uses the ``op`` discriminator to select the correct model.
    """
    parsed: list[Operation] = []
    for raw in raw_ops:
        op_type = raw.get("op")
        if op_type == "replace":
            parsed.append(ReplaceOp.model_validate(raw))
        elif op_type == "create":
            parsed.append(CreateOp.model_validate(raw))
        elif op_type == "delete":
            parsed.append(DeleteOp.model_validate(raw))
        else:
            msg = f"Unknown operation type: {op_type}"
            raise ValueError(msg)
    return parsed


class BatchEditTool:
    """Atomic batch file editing for AI agents.

    Replaces, creates, and deletes files in a single atomic operation.
    Registered as ``batch_edit`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Apply multiple file edits atomically via op=replace"
        " with old/new pairs. Safer than sed — validates before writing."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_edit"

    def execute(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        path: str = ".",
        operations: list[dict[str, Any]] | None = None,
        lint: bool = True,
        lint_diff: bool = True,
        lint_diff_max_ratio: float = 0.5,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a batch of file operations atomically.

        Args:
            path: Project root directory.
            operations: List of operation dicts with ``op`` discriminator.
            lint: Run ruff --fix on changed Python files after apply.
            lint_diff: Surface per-file diffs of post-lint mutations.
            lint_diff_max_ratio: Fallback threshold (diff / file size).

        Returns:
            ToolResult with applied counts and checkpoint SHA.
        """
        raw_operations: list[dict[str, Any]] = operations or []

        if not raw_operations:
            return ToolResult(
                success=False,
                error="No operations provided",
            )

        try:
            parsed = _parse_operations(raw_operations)
        except (ValueError, TypeError) as exc:
            return ToolResult(success=False, error=f"Invalid operations: {exc}")

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            result = batch_apply(root, parsed)

            data: dict[str, Any] = {
                "checkpoint": result.checkpoint,
                "applied": result.applied,
                "summary": result.summary,
                "details": [d.model_dump(exclude_none=True) for d in result.details]
                if result.details
                else [],
            }

            if result.success and lint:
                py_files = _collect_python_files(root, parsed)
                if py_files:
                    lint_warnings: list[str] = []
                    post_agent: dict[str, str] = {}
                    if lint_diff:
                        for py_file in py_files:
                            try:
                                rel = str(py_file.relative_to(root))
                                post_agent[rel] = py_file.read_text()
                            except OSError:
                                continue
                    auto_fixed, lint_errors = _run_ruff(
                        root,
                        py_files,
                        warnings=lint_warnings,
                    )
                    claude_fixed: list[str] = []
                    if lint_errors:
                        before_claude = lint_errors
                        lint_errors = claude_fix(
                            root,
                            lint_errors,
                            warnings=lint_warnings,
                        )
                        remaining_set = set(lint_errors)
                        claude_fixed = [
                            e for e in before_claude if e not in remaining_set
                        ]
                    data["lint"] = {
                        "auto_fixed": len(auto_fixed),
                        "claude_fixed": len(claude_fixed),
                        "remaining": len(lint_errors),
                    }
                    if lint_errors:
                        data["lint_errors"] = lint_errors
                    if lint_warnings:
                        data["warnings"] = lint_warnings
                    if lint_diff and (auto_fixed or claude_fixed):
                        post_lint: dict[str, str] = {}
                        for py_file in py_files:
                            try:
                                rel = str(py_file.relative_to(root))
                                post_lint[rel] = py_file.read_text()
                            except OSError:
                                continue

                        def _resolve(raw: str, root: Path = root) -> str:
                            candidate = Path(raw)
                            if candidate.is_absolute():
                                try:
                                    return str(candidate.relative_to(root))
                                except ValueError:
                                    return raw
                            return raw

                        rules_by_file = extract_rules_by_file(
                            auto_fixed, path_resolver=_resolve
                        )
                        diffs = compute_lint_diffs(
                            post_agent,
                            post_lint,
                            rules_by_file,
                            max_ratio=lint_diff_max_ratio,
                        )
                        if diffs:
                            data["lint_diffs"] = diffs

            return ToolResult(
                success=result.success,
                data=data,
                error=result.error,
            )
        except (OSError, ValueError, TypeError) as exc:
            return ToolResult(success=False, error=str(exc))
