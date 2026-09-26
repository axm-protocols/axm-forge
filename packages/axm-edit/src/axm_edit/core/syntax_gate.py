"""Refuse a batch that would leave a Python file unparseable.

The gate compares the file as it is on disk with the content the batch
would write, both in memory, so a refusal happens before a single byte is
written. It only guards against a *regression*: a file that did not parse
before the batch is never blocked, so an edit repairing it stays possible.

Parsing uses :func:`ast.parse` of the running interpreter, which must be at
least as recent as the edited project's syntax.
"""

from __future__ import annotations

import ast
import warnings

from axm_edit.models.operations import ValidationError

__all__ = ["PYTHON_SUFFIXES", "syntax_regression"]

PYTHON_SUFFIXES: tuple[str, ...] = (".py", ".pyi")


def _syntax_error(source: str, filename: str) -> SyntaxError | ValueError | None:
    """Return the parse failure of *source*, or ``None`` when it parses.

    Args:
        source: Python source text.
        filename: Name reported in the failure, for context only.

    Returns:
        The ``SyntaxError`` (or the ``ValueError`` raised on a null byte),
        ``None`` when *source* parses.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            ast.parse(source, filename=filename)
        except (SyntaxError, ValueError) as exc:
            return exc
    return None


def syntax_regression(
    file_rel: str,
    before: str | None,
    after: str,
) -> ValidationError | None:
    """Report a batch turning *file_rel* into unparseable Python.

    Args:
        file_rel: Path of the file, relative to the batch root.
        before: Current content, ``None`` when the file does not exist yet.
        after: Content the batch would write.

    Returns:
        A validation error naming the first syntax error of *after*, or
        ``None`` when the file is not Python, parses after the batch, or
        already failed to parse before it.
    """
    if not file_rel.endswith(PYTHON_SUFFIXES):
        return None
    if before is not None and _syntax_error(before, file_rel) is not None:
        return None
    failure = _syntax_error(after, file_rel)
    if failure is None:
        return None
    line = failure.lineno if isinstance(failure, SyntaxError) else None
    reason = failure.msg if isinstance(failure, SyntaxError) else str(failure)
    where = f" at line {line}" if line else ""
    return ValidationError(
        file=file_rel,
        line=line,
        error=(
            f"Batch would break Python syntax{where}: {reason}. Nothing was"
            " written; check the quote and bracket pairing of `new`."
        ),
    )
