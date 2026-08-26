"""BatchRollbackTool — restore project state to a checkpoint.

Registered as ``batch_rollback`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.checkpoint import rollback, snapshot_paths


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
    miss — alongside the restored-file count. (The checkpoint is an opaque
    JSON snapshot payload, not a short hash, so it is not summarised in the
    header.) Every restored file is then listed verbatim, one per line. On
    failure the header surfaces the error, so nothing carried in ``data``
    (the ``restored`` flag) or the error is lost: only JSON structure is
    dropped.
    """
    del checkpoint  # opaque payload, not summarisable — kept for signature parity
    if success:
        n = len(files)
        plural = "s" if n != 1 else ""
        header = f"batch_rollback | ✓ | {n} file{plural} restored"
        return "\n".join([header, *files])
    reason = error or "nothing restored"
    header = f"batch_rollback | ✗ | {reason}"
    return "\n".join([header, *files])


class BatchRollbackTool:
    """Restore project state to a previous checkpoint.

    Registered as ``batch_rollback`` via axm.tools entry point.

    Not to be confused with the atomicity of ``batch_edit``. A batch that
    fails mid-apply restores every file it touched by itself, through the
    same :func:`axm_edit.core.checkpoint.rollback` primitive and without
    anyone calling this tool. What this tool undoes is a batch that
    *succeeded*.

    That case is reachable only by a caller holding the checkpoint payload
    from ``batch_edit``'s structured ``data``. An MCP agent sees the text
    view, which omits the payload on purpose (it is the base64 of every
    touched file), so in practice a successful batch is undone with git.
    """

    agent_hint: str = (
        "Programmatic undo of a batch_edit, for callers that read the tool's"
        " structured `data`. It needs the full checkpoint snapshot payload"
        " (a JSON string, not a hash), which lives in batch_edit's"
        " `data['checkpoint']` and is deliberately absent from its text"
        " view — the payload is the base64 of every touched file and costs"
        " tens of thousands of tokens to render. An agent reading only that"
        " text cannot supply it: undo a successful batch with git instead"
        " (`git checkout -- .`). A batch that fails mid-apply already rolls"
        " itself back — nothing to call here."
    )

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
