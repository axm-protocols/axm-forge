from __future__ import annotations

__all__ = ["build_commit_cmd"]


def build_commit_cmd(
    message: str,
    body: str | None,
    *,
    skip_hooks: bool = True,
    author: str | None = None,
) -> list[str]:
    """Build the ``git commit`` argument list.

    Args:
        message: Commit summary line.
        body: Optional extended commit body.
        skip_hooks: Append ``--no-verify`` when *True*.
        author: Git ``--author`` value (``"Name <email>"``).
            When *None*, git uses the default identity.
    """
    cmd = ["commit", "-m", message]
    if body:
        cmd.extend(["-m", body])
    if skip_hooks:
        cmd.append("--no-verify")
    if author:
        cmd.append(f"--author={author}")
    return cmd
