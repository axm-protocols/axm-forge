"""Structured docstring parser for axm-ast.

Parses raw docstring strings into structured sections without requiring
external dependencies.  Supports Google, NumPy, and Sphinx styles.

Only non-redundant sections are extracted:

- ``summary`` — first paragraph (unique value vs signature)
- ``raises``  — exception types + descriptions (absent from signature)
- ``examples`` — usage examples (pedagogical, not in signature)

``Args`` and ``Returns`` are intentionally **skipped**: the information
they contain is already present in the function ``signature`` field.

Example:
    >>> from axm_ast.docstring_parser import parse_docstring
    >>> parsed = parse_docstring('Do thing.\\n\\nRaises:\\n    ValueError: bad.')
    >>> parsed.summary
    'Do thing.'
    >>> parsed.raises
    [('ValueError', 'bad.')]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["ParsedDocstring", "parse_docstring"]

# ─── Section header patterns ──────────────────────────────────────────────────

# Google-style:  "Args:", "Returns:", "Raises:", "Example:", "Examples:"
_GOOGLE_HEADER = re.compile(
    r"^(Args|Arguments|Parameters|Returns?|Raises?|Examples?|Notes?|References?|"
    r"Attributes?|Todo|Warns?|See Also|Yields?)\s*:$",
    re.IGNORECASE | re.MULTILINE,
)

# NumPy-style:  "Raises\n-------"
_NUMPY_HEADER = re.compile(
    r"^(Args|Arguments|Parameters|Returns?|Raises?|Examples?|Notes?|References?|"
    r"Attributes?|See Also|Yields?)\s*\n[ \t]*[-=]{3,}",
    re.IGNORECASE | re.MULTILINE,
)

# Sphinx-style:  ":raises ValueError:", ":raises:"
_SPHINX_RAISES = re.compile(
    r"^\s*:raises?\s+([^:]+):\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Section names we want to keep
_RAISES_NAMES = frozenset({"raises", "raise"})
_EXAMPLE_NAMES = frozenset({"example", "examples"})
_SKIP_NAMES = frozenset(
    {"args", "arguments", "parameters", "returns", "return", "yields", "yield"}
)


# ─── Data model ───────────────────────────────────────────────────────────────


@dataclass
class ParsedDocstring:
    """Structured representation of a parsed docstring.

    Attributes:
        summary: First paragraph of the docstring (may be multi-line).
        raises: List of (exception_type, description) tuples.
        examples: List of example blocks as raw strings.
    """

    summary: str | None = None
    raises: list[tuple[str, str]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


# ─── Public API ───────────────────────────────────────────────────────────────


def parse_docstring(raw: str | None) -> ParsedDocstring:
    """Parse a raw docstring string into structured sections.

    Supports Google, NumPy, and Sphinx docstring styles.
    ``Args``/``Returns`` sections are deliberately ignored (redundant
    with the function ``signature`` field).

    Args:
        raw: Raw docstring content, or ``None``.

    Returns:
        ``ParsedDocstring`` with ``summary``, ``raises``, and ``examples``.

    Example:
        >>> p = parse_docstring('Summary.\\n\\nRaises:\\n    ValueError: bad input.')
        >>> p.summary
        'Summary.'
        >>> p.raises
        [('ValueError', 'bad input.')]
    """
    if not raw:
        return ParsedDocstring()

    # Normalise indentation (strip common leading whitespace)
    lines = raw.expandtabs().splitlines()
    lines = _strip_indent(lines)
    text = "\n".join(lines).strip()

    style = _detect_style(text)

    summary = _extract_summary(text)

    if style == "sphinx":
        raises = _extract_raises_sphinx(text)
        examples: list[str] = []
    elif style == "numpy":
        raises = _extract_raises_numpy(text)
        examples = _extract_examples_numpy(text)
    else:  # google (default)
        raises = _extract_raises_google(text)
        examples = _extract_examples_google(text)

    return ParsedDocstring(summary=summary, raises=raises, examples=examples)


# ─── Style detection ─────────────────────────────────────────────────────────


def _detect_style(text: str) -> str:
    """Detect the docstring style: 'google', 'numpy', or 'sphinx'."""
    if _SPHINX_RAISES.search(text):
        return "sphinx"
    if _NUMPY_HEADER.search(text):
        return "numpy"
    return "google"


# ─── Summary extraction ───────────────────────────────────────────────────────


def _extract_summary(text: str) -> str | None:
    """Extract the first paragraph (summary) of the docstring."""
    paragraphs = re.split(r"\n\s*\n", text, maxsplit=1)
    if not paragraphs:
        return None
    first = paragraphs[0].strip()
    if not first:
        return None
    # Stop at the first section header to avoid swallowing Google-style headers
    # that appear without a blank line gap (unusual but defensive)
    match = _GOOGLE_HEADER.search(first)
    if match:
        first = first[: match.start()].strip()
    return first or None


# ─── Google-style parsers ─────────────────────────────────────────────────────


def _split_google_sections(text: str) -> dict[str, str]:
    """Split text into {section_name: body} for Google-style docstrings."""
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        # A section header is a line whose *stripped* content matches "Word:" exactly
        stripped = line.strip()
        header_match = re.match(r"^([A-Za-z][A-Za-z ]*?)\s*:$", stripped)
        if header_match:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = header_match.group(1).lower()
            current_lines = []
        else:
            current_lines.append(line)

    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()

    return sections


def _extract_raises_google(text: str) -> list[tuple[str, str]]:
    """Parse Raises section from a Google-style docstring."""
    sections = _split_google_sections(text)
    raises_body = sections.get("raises", sections.get("raise", ""))
    if not raises_body:
        return []
    return _parse_raises_body(raises_body)


def _extract_examples_google(text: str) -> list[str]:
    """Parse Examples section from a Google-style docstring."""
    sections = _split_google_sections(text)
    body = sections.get("examples", sections.get("example", ""))
    if not body:
        return []
    return [body.strip()]


# ─── NumPy-style parsers ──────────────────────────────────────────────────────


def _split_numpy_sections(text: str) -> dict[str, str]:
    """Split text into {section_name: body} for NumPy-style docstrings."""
    sections: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    current_name: str | None = None
    current_lines: list[str] = []

    while i < len(lines):
        # Check for NumPy header: "Name\n---"
        if i + 1 < len(lines) and re.match(r"^[-=]{3,}\s*$", lines[i + 1]):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = lines[i].strip().lower()
            current_lines = []
            i += 2  # skip the dashes line
            continue
        current_lines.append(lines[i])
        i += 1

    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()

    return sections


def _extract_raises_numpy(text: str) -> list[tuple[str, str]]:
    """Extract Raises section from NumPy-style docstrings."""
    sections = _split_numpy_sections(text)
    for name in _RAISES_NAMES:
        body = sections.get(name, "")
        if body:
            return _parse_raises_body(body)
    return []


def _extract_examples_numpy(text: str) -> list[str]:
    """Extract Examples section from NumPy-style docstrings."""
    sections = _split_numpy_sections(text)
    for name in _EXAMPLE_NAMES:
        body = sections.get(name, "")
        if body:
            return [body.strip()]
    return []


# ─── Sphinx-style parsers ─────────────────────────────────────────────────────


def _extract_raises_sphinx(text: str) -> list[tuple[str, str]]:
    """Parse :raises ExcType: description from Sphinx-style docstrings."""
    return [
        (m.group(1).strip(), m.group(2).strip()) for m in _SPHINX_RAISES.finditer(text)
    ]


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _flush_raises_entry(
    result: list[tuple[str, str]],
    current_type: str | None,
    current_desc: list[str],
) -> None:
    """Append the accumulated raises entry to *result* if valid."""
    if current_type is not None:
        result.append((current_type, " ".join(current_desc).strip()))


def _parse_raises_body(body: str) -> list[tuple[str, str]]:
    """Parse a Raises section body into (exc_type, description) pairs.

    Handles both Google (``ExcType: desc``) and NumPy (``ExcType`` alone) formats.
    """
    result: list[tuple[str, str]] = []
    current_type: str | None = None
    current_desc: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Google: "ExcType: description" — has a colon with type before it
        google_match = re.match(
            r"^\s*([A-Za-z][A-Za-z0-9_.]*(?:\[.*?\])?)\s*:\s*(.*)", line
        )
        # NumPy: "ExcType" alone (no colon, not indented relative to other entries)
        numpy_match = re.match(r"^([A-Za-z][A-Za-z0-9_.]*(?:\[.*?\])?)\s*$", stripped)

        if google_match:
            _flush_raises_entry(result, current_type, current_desc)
            current_type = google_match.group(1).strip()
            current_desc = (
                [google_match.group(2).strip()] if google_match.group(2).strip() else []
            )
        elif numpy_match and not line.startswith(" "):
            _flush_raises_entry(result, current_type, current_desc)
            current_type = numpy_match.group(1).strip()
            current_desc = []
        elif current_type and stripped:
            current_desc.append(stripped)

    _flush_raises_entry(result, current_type, current_desc)
    return result


def _strip_indent(lines: list[str]) -> list[str]:
    """Strip common leading whitespace from all non-empty lines.

    Uses the minimum indentation of non-empty lines (ignoring the first
    line, which is typically unindented in triple-quote docstrings).
    """
    non_empty = [ln for ln in lines[1:] if ln.strip()]
    if not non_empty:
        return lines
    indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
    if indent == 0:
        return lines
    result = [lines[0]] if lines else []
    result += [ln[indent:] if len(ln) >= indent else ln for ln in lines[1:]]
    return result
