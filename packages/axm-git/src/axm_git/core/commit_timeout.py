"""Internal bounded provenance for timed-out commit attempts."""

from __future__ import annotations

import subprocess

__all__: list[str] = []


def _bounded_output(value: str | bytes | None) -> str:
    """Decode and bound one captured stream to 8192 characters."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")[:8192]
    return (value or "")[:8192]


class CommitTimeoutError(subprocess.TimeoutExpired):
    """Carry causal timeout evidence through the scoped refusal path."""

    def __init__(
        self,
        timeout: subprocess.TimeoutExpired,
        *,
        retried: bool = False,
        auto_fixed: list[str] | None = None,
    ) -> None:
        """Snapshot retry metadata and bounded streams without retrying."""
        super().__init__(
            timeout.cmd,
            timeout.timeout,
            output=_bounded_output(timeout.output),
            stderr=_bounded_output(timeout.stderr),
        )
        self.seconds = timeout.timeout
        self.retried = retried
        self.auto_fixed = list(auto_fixed or [])
        self.output = (
            _bounded_output(timeout.stdout) + "\n" + _bounded_output(timeout.stderr)
        )

    def __str__(self) -> str:
        """Keep the public refusal diagnostic explicit and stable."""
        return f"git timed out after {self.seconds}s"
