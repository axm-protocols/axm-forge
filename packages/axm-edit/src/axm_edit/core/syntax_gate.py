"""Refuse syntax regressions in Python, TOML and JSON before writing.

The gate compares the file as it is on disk with the content the batch
would write, both in memory, so a refusal happens before a single byte is
written. It only guards against a *regression*: a file that did not parse
before the batch is never blocked, so an edit repairing it stays possible.
New Python and TOML files must parse; new JSON files are unchecked. JSON
comments and trailing commas are tolerated. Data parser recursion limits
produce no verdict and the content is considered parseable.

Python parsing uses :func:`ast.parse` of the running interpreter, which must
be at least as recent as the edited project's syntax.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
import warnings
from collections.abc import Callable
from dataclasses import dataclass

from axm_edit.models.operations import ValidationError

__all__ = ["PYTHON_SUFFIXES", "syntax_regression"]

PYTHON_SUFFIXES: tuple[str, ...] = (".py", ".pyi")


@dataclass(frozen=True)
class _Failure:
    """A parser failure with an optional source line."""

    line: int | None
    reason: str


@dataclass(frozen=True)
class _Format:
    """A format checker and its creation policy and diagnostic hint."""

    name: str
    checker: Callable[[str], _Failure | None]
    check_new: bool
    hint: str


def _python_error(source: str) -> _Failure | None:
    """Return a Python parse failure, suppressing parser warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            ast.parse(source)
        except SyntaxError as exc:
            return _Failure(exc.lineno, exc.msg)
        except ValueError as exc:
            return _Failure(None, str(exc))
    return None


def _toml_error(source: str) -> _Failure | None:
    """Return a TOML parse failure across Python 3.12+ exception layouts."""
    try:
        tomllib.loads(source)
    except RecursionError:
        return None
    except tomllib.TOMLDecodeError as exc:
        line = getattr(exc, "lineno", None)
        if not isinstance(line, int):
            match = re.search(r"\(at line (\d+), column \d+\)", str(exc))
            line = int(match.group(1)) if match else None
        return _Failure(line, str(exc))
    return None


def _string_end(source: str, start: int) -> int:
    """Find the end of a JSON string, skipping escaped characters."""
    index = start + 1
    while index < len(source):
        char = source[index]
        index += 1
        if char == "\\":
            index += 1
        elif char == '"':
            return index
    return len(source)


def _comment_end(source: str, start: int) -> int:
    """Find a comment end, leaving unclosed block comments for the parser."""
    if source.startswith("//", start):
        index = start + 2
        while index < len(source) and source[index] not in "\r\n":
            index += 1
        return index
    if source.startswith("/*", start):
        end = source.find("*/", start + 2)
        if end != -1:
            return end + 2
    return start


def _blank_comments(source: str) -> str:
    """Blank comments outside strings without changing source locations."""
    chars = list(source)
    index = 0
    while index < len(source):
        if source[index] == '"':
            index = _string_end(source, index)
            continue
        end = _comment_end(source, index)
        for position in range(index, end):
            if chars[position] not in "\r\n":
                chars[position] = " "
        index = max(index + 1, end)
    return "".join(chars)


def _blank_trailing_commas(source: str) -> str:
    """Blank commas before closing delimiters strictly outside strings."""
    chars = list(source)
    previous = 0
    index = 0
    while index < len(source):
        char = source[index]
        if char == '"':
            index = _string_end(source, index)
            previous = index - 1
            continue
        if char in "}]" and source[previous] == ",":
            chars[previous] = " "
        if char not in " \t\r\n":
            previous = index
        index += 1
    return "".join(chars)


def _json_error(source: str) -> _Failure | None:
    """Return a JSON parse failure, tolerating comments and trailing commas."""
    try:
        try:
            json.loads(source)
        except json.JSONDecodeError:
            # Strict JSON is the common case and parses in C; the tolerant
            # view costs a pure-Python scan, so it is only built on failure.
            json.loads(_blank_trailing_commas(_blank_comments(source)))
    except RecursionError:
        return None
    except json.JSONDecodeError as exc:
        return _Failure(exc.lineno, exc.msg)
    return None


_PYTHON = _Format(
    name="Python",
    checker=_python_error,
    check_new=True,
    hint="check the quote and bracket pairing of `new`.",
)
_FORMATS: dict[str, _Format] = {
    **dict.fromkeys(PYTHON_SUFFIXES, _PYTHON),
    ".toml": _Format(
        name="TOML",
        checker=_toml_error,
        check_new=True,
        hint="check TOML values, quotes and table declarations.",
    ),
    ".json": _Format(
        name="JSON",
        checker=_json_error,
        check_new=False,
        hint="check JSON quotes, commas and bracket pairing.",
    ),
}


def syntax_regression(
    file_rel: str,
    before: str | None,
    after: str,
) -> ValidationError | None:
    """Report a batch turning a supported file into unparseable content.

    Args:
        file_rel: Path of the file, relative to the batch root.
        before: Current content, ``None`` when the file does not exist yet.
        after: Content the batch would write.

    Returns:
        A validation error naming the first syntax error of *after*, or
        ``None`` for unsupported formats, valid content, already-broken files,
        or new files whose format policy skips checking.
    """
    format_spec = next(
        (spec for suffix, spec in _FORMATS.items() if file_rel.endswith(suffix)), None
    )
    if format_spec is None:
        return None
    if before is None:
        if not format_spec.check_new:
            return None
    elif format_spec.checker(before) is not None:
        return None
    failure = format_spec.checker(after)
    if failure is None:
        return None
    where = f" at line {failure.line}" if failure.line else ""
    return ValidationError(
        file=file_rel,
        line=failure.line,
        error=(
            f"Batch would break {format_spec.name} syntax{where}: {failure.reason}."
            f" Nothing was written; {format_spec.hint}"
        ),
    )
