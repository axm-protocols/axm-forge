"""Shared error-handling helpers for ``axm_ast`` tool implementations."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import ParamSpec

from axm.tools.base import ToolResult

__all__ = ["log_and_fallback", "safe_execute"]


_P = ParamSpec("_P")


def safe_execute(
    method: Callable[_P, ToolResult],
) -> Callable[_P, ToolResult]:
    """Wrap a tool ``execute`` method to log + return structured failures.

    The wrapper logs any uncaught exception at ``WARNING`` on the calling
    module's logger with ``exc_info=True``, then returns a
    ``ToolResult(success=False, error=str(exc))`` so callers never see a
    raised exception.
    """
    logger = logging.getLogger(method.__module__)

    @functools.wraps(method)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> ToolResult:
        try:
            return method(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — final boundary
            tool_name = type(args[0]).__name__ if args else "<unknown>"
            logger.warning(
                "Tool %s failed: %s",
                tool_name,
                exc,
                exc_info=True,
            )
            return ToolResult(success=False, error=str(exc))

    return wrapper


def log_and_fallback[T](
    logger: logging.Logger,
    exc: BaseException,
    fallback: T,
) -> T:
    """Log an exception at ``WARNING`` with ``exc_info`` and return *fallback*.

    Used inside helpers that return a ``dict`` (or other structured value)
    instead of a ``ToolResult`` — they can't use :func:`safe_execute` but
    still need centralized logging on the failure boundary.
    """
    logger.warning("Tool helper failed: %s", exc, exc_info=True)
    return fallback
