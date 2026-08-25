"""Copier adapter for template-based scaffolding."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Iterator, Mapping
from io import StringIO
from pathlib import Path

from copier import run_copy
from pydantic import BaseModel, ConfigDict

from axm_init.models.results import ScaffoldResult

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_output() -> Iterator[None]:
    """Discard Python-level stdout/stderr for the duration of the block.

    Uses :func:`contextlib.redirect_stdout` / :func:`contextlib.redirect_stderr`
    to swap the interpreter-level streams to an in-memory sink, so child-tool
    chatter (git / uv / prek) written through ``sys.stdout`` / ``sys.stderr`` is
    swallowed.  Unlike ``os.dup2`` on fds 1/2, this never mutates the
    process-global file descriptors, so a concurrent writer on fd 1/2 is left
    completely unaffected.
    """
    sink = StringIO()
    with (
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        yield


def _offload_to_thread(sync_call: Callable[[], None]) -> None:
    """Run *sync_call* on a worker thread, awaiting it via ``asyncio.to_thread``.

    Called when a loop is already running on the current thread (e.g. an MCP
    server): copier calls ``asyncio.run()`` internally and therefore needs a
    thread without a running loop.  The worker thread runs its own loop and
    awaits ``asyncio.to_thread(sync_call)``, so the caller's running loop is
    never driven with a blocking ``future.result()``.  Exceptions raised by
    *sync_call* are re-raised on the calling thread.
    """
    import asyncio
    import threading

    errors: list[Exception] = []

    def _worker() -> None:
        async def _main() -> None:
            await asyncio.to_thread(sync_call)

        try:
            asyncio.run(_main())
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]


class CopierConfig(BaseModel):  # type: ignore[explicit-any]
    """Configuration for Copier execution.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    template_path: Path
    destination: Path
    data: Mapping[str, object]
    defaults: bool = True
    overwrite: bool = False
    trust_template: bool = False

    model_config = ConfigDict(extra="forbid")


class CopierAdapter:
    """Adapter for Copier template operations.

    Wraps Copier's run_copy function with a Pydantic-based interface
    and returns structured ScaffoldResult.
    """

    @staticmethod
    def _do_copy(config: CopierConfig) -> None:
        """Run copier, offloading to a thread if an event loop is active.

        Copier (via prompt_toolkit) calls ``asyncio.run()`` internally.
        When we are already inside an async event loop (e.g. MCP server),
        this raises ``RuntimeError: asyncio.run() cannot be called from
        a running event loop``.  The fix: detect the running loop and
        execute the blocking copy in a **separate thread** which gets
        its own event loop context.
        """
        import asyncio

        def _run() -> None:
            # ``run_copy`` declares ``data: dict[str, Any] | None``;
            # converting our ``Mapping[str, object]`` to a plain ``dict``
            # widens cleanly to the expected type.
            run_copy(
                src_path=str(config.template_path),
                dst_path=config.destination,
                data=dict(config.data),
                defaults=config.defaults,
                overwrite=config.overwrite,
                unsafe=config.trust_template,
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop — safe to call directly (CLI context).
            _run()
        else:
            # Inside an event loop (MCP server) — offload without blocking
            # the running loop on a synchronous ``future.result()``.
            _offload_to_thread(_run)

    def copy(self, config: CopierConfig) -> ScaffoldResult:
        """Execute Copier copy operation.

        Suppresses stdout/stderr via the scoped :func:`_suppress_output`
        context manager so that post-copy tasks (git init, uv sync,
        pre-commit install) don't pollute the parent process stdio —
        critical when running inside an MCP server.  Suppression is scoped
        to the interpreter-level streams and never mutates the process-global
        file descriptors 1/2, so concurrent writers on those fds are
        unaffected.

        Args:
            config: Copier configuration with template path, destination, and data.

        Returns:
            ScaffoldResult with success status and path.
        """
        if config.trust_template:
            logger.warning(
                "Running Copier with unsafe=True — template may execute "
                "arbitrary post-copy tasks."
            )
        try:
            with _suppress_output():
                self._do_copy(config)
            # Walk destination to collect created files, excluding noise
            # from post-copy tasks (.git, .venv, __pycache__, node_modules).
            _excluded = {
                ".git",
                ".venv",
                "__pycache__",
                "node_modules",
                ".mypy_cache",
            }
            created: list[str] = sorted(
                str(p.relative_to(config.destination))
                for p in config.destination.rglob("*")
                if p.is_file()
                and not any(
                    part in _excluded
                    for part in p.relative_to(config.destination).parts[:-1]
                )
            )
            return ScaffoldResult(
                success=True,
                path=str(config.destination),
                message="Project scaffolded via Copier",
                files_created=created,
            )
        except Exception as e:
            return ScaffoldResult(
                success=False,
                path=str(config.destination),
                message=f"Copier failed: {e}",
            )
