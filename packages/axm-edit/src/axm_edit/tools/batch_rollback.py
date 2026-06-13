"""BatchRollbackTool — restore project state to a checkpoint.

Registered as ``batch_rollback`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.checkpoint import rollback, snapshot_paths

_SHA_LEN = 7


def _restored_files(checkpoint: str) -> list[str]:
    """Return the relative paths captured by *checkpoint* (read-only).

    Reads the targeted-path snapshot — these are exactly the files a
    successful rollback restores. Purely informational: a malformed
    snapshot yields an empty list so the text view degrades gracefully
    without affecting the rollback outcome.
    """
    return snapshot_paths(checkpoint)


def render_text(
    *,
    success: bool,
    checkpoint: str,
    files: list[str],
    error: str | None,
) -> str:
    """Render a compact, LLM-facing view of a rollback outcome.

    The header carries the global status — ``✓`` when the working tree was
    restored, ``✗`` otherwise so a failed/no-op rollback is impossible to
    miss — alongside the restored-file count and the (short) checkpoint SHA.
    Every restored file is then listed verbatim, one per line. On failure the
    header surfaces the error and the checkpoint, so nothing carried in
    ``data`` (the ``restored`` flag) or the error is lost: only JSON
    structure is dropped.
    """
    sha = checkpoint[:_SHA_LEN] if checkpoint else "?"
    if success:
        n = len(files)
        plural = "s" if n != 1 else ""
        header = f"batch_rollback | ✓ | {n} file{plural} restored from {sha}"
        return "\n".join([header, *files])
    reason = error or "nothing restored"
    header = f"batch_rollback | ✗ | {reason} (checkpoint {sha})"
    return "\n".join([header, *files])


class BatchRollbackTool:
    """Restore project state to a previous checkpoint.

    Registered as ``batch_rollback`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_rollback"

    def execute(self, **kwargs: object) -> ToolResult:
        """Rollback to a checkpoint created by batch_edit.

        Args:
            **kwargs: Keyword arguments.
                path: Project root directory.
                checkpoint: The snapshot payload from batch_edit's response.

        Returns:
            ToolResult indicating whether the rollback succeeded.
        """
        raw_path = kwargs.get("path", ".")
        path = raw_path if isinstance(raw_path, str) else "."
        raw_checkpoint = kwargs.get("checkpoint")
        checkpoint = raw_checkpoint if isinstance(raw_checkpoint, str) else None

        if not checkpoint:
            return ToolResult(
                success=False,
                error="checkpoint is required",
            )

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            files = _restored_files(checkpoint)
            success = rollback(root, checkpoint).ok
            error = None if success else "Rollback failed"
            return ToolResult(
                success=success,
                data={"restored": success},
                error=error,
                text=render_text(
                    success=success,
                    checkpoint=checkpoint,
                    files=files,
                    error=error,
                ),
            )
        except (OSError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc))
