"""Format detection via parse-based heuristics."""

from __future__ import annotations

import csv
import io
import json
import re
import tomllib

import yaml

from axm_smelt.core.models import Format

__all__ = ["Format", "detect_format", "detect_format_parsed"]

_YAML_INDICATORS = re.compile(r"(^---|^\w[\w\s]*:.*$|^\s*-\s+\S)", re.MULTILINE)


def try_json(stripped: str) -> Format | None:
    """Return ``Format.JSON`` if *stripped* is valid JSON, else ``None``."""
    if not stripped:
        return None
    if stripped[0] in ("{", "["):
        try:
            json.loads(stripped)
            return Format.JSON
        except (json.JSONDecodeError, ValueError):
            pass
    return None


_HTML_TAGS = frozenset(
    {
        "a",
        "abbr",
        "article",
        "aside",
        "b",
        "blockquote",
        "body",
        "br",
        "button",
        "code",
        "col",
        "dd",
        "details",
        "div",
        "dl",
        "dt",
        "em",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "i",
        "iframe",
        "img",
        "input",
        "label",
        "li",
        "link",
        "main",
        "meta",
        "nav",
        "ol",
        "option",
        "p",
        "pre",
        "script",
        "section",
        "select",
        "small",
        "span",
        "strong",
        "style",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "u",
        "ul",
        "video",
    }
)


def try_xml(stripped: str) -> Format | None:
    """Return ``Format.XML`` if *stripped* looks like XML, else ``None``."""
    if stripped.startswith("<") and not stripped.startswith("<!"):
        # XML declaration is a strong signal
        if stripped.startswith("<?xml"):
            return Format.XML
        match = re.match(r"<(\w+)[\s>]", stripped)
        if match and re.search(r"<\w+[^>]*>", stripped):
            root_tag = match.group(1).lower()
            if root_tag not in _HTML_TAGS:
                return Format.XML
    return None


def try_yaml(stripped: str) -> Format | None:
    """Return ``Format.YAML`` if *stripped* has YAML indicators, else ``None``."""
    if _YAML_INDICATORS.search(stripped):
        try:
            result = yaml.safe_load(stripped)
            if isinstance(result, (dict, list)):
                return Format.YAML
        except yaml.YAMLError:
            pass
    return None


_MD_HEADING = re.compile(r"^#{1,6}\s", re.MULTILINE)
_MD_TABLE_SEP = re.compile(r"^\|.*\|$", re.MULTILINE)
_MD_TABLE_DASH = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)
_MD_FENCED = re.compile(r"^```\w*$", re.MULTILINE)
_MD_LINK = re.compile(r"\[.+\]\(.+\)")


def try_markdown(stripped: str) -> Format | None:
    """Return ``Format.MARKDOWN`` if *stripped* has >=2 distinct markdown indicators."""
    indicators = 0
    heading_levels = {len(m.group().rstrip()) for m in _MD_HEADING.finditer(stripped)}
    if len(heading_levels) >= 2:  # noqa: PLR2004
        indicators += 2
    elif heading_levels:
        indicators += 1
    if _MD_TABLE_SEP.search(stripped) and _MD_TABLE_DASH.search(stripped):
        indicators += 2  # pipe table with separator is a strong signal
    if len(_MD_FENCED.findall(stripped)) >= 2:  # noqa: PLR2004
        indicators += 1
    if _MD_LINK.search(stripped):
        indicators += 1
    if indicators >= 2:  # noqa: PLR2004
        return Format.MARKDOWN
    return None


def try_toml(stripped: str) -> Format | None:
    """Return ``Format.TOML`` if *stripped* parses as a non-empty TOML mapping.

    Requires a successful :func:`tomllib.loads` yielding at least one
    key or table, so plain text never matches. Ordered after the YAML
    probe; YAML mappings (``key: value``) fail TOML parsing (which needs
    ``=``), so this never steals YAML inputs.
    """
    try:
        parsed = tomllib.loads(stripped)
    except tomllib.TOMLDecodeError:
        return None
    if parsed:
        return Format.TOML
    return None


_CSV_MIN_COLUMNS = 2
_CSV_MIN_ROWS = 2


def try_csv(stripped: str) -> Format | None:
    """Return ``Format.CSV`` if *stripped* is a consistent delimited grid.

    Heuristic: at least two rows sharing the same column count of two or
    more, with a delimiter sniffed by :class:`csv.Sniffer`. Single-line
    comma prose has only one row and falls through to ``None``.
    """
    if "\n" not in stripped:
        return None
    try:
        dialect = csv.Sniffer().sniff(stripped, delimiters=",;\t|")
    except csv.Error:
        return None
    rows = [row for row in csv.reader(io.StringIO(stripped), dialect) if row]
    if len(rows) < _CSV_MIN_ROWS:
        return None
    width = len(rows[0])
    if width < _CSV_MIN_COLUMNS:
        return None
    if any(len(row) != width for row in rows):
        return None
    return Format.CSV


def detect_format(text: str) -> Format:
    """Detect the format of *text* using parse-based heuristics."""
    fmt, _ = detect_format_parsed(text)
    return fmt


def detect_format_parsed(text: str) -> tuple[Format, object | None]:
    """Detect format and return ``(format, parsed_data)``.

    *parsed_data* is non-None only when the format is JSON, giving the
    caller the already-parsed object so it can be injected into a
    :class:`SmeltContext` without a redundant ``json.loads`` call.
    """
    stripped = text.strip()
    if not stripped:
        return Format.TEXT, None

    # JSON probe — capture the parsed object
    if stripped[0] in ("{", "["):
        try:
            data = json.loads(stripped)
            return Format.JSON, data
        except (json.JSONDecodeError, ValueError):
            pass

    # Remaining probes (XML, YAML, Markdown, TOML, CSV) — no parsed data
    for probe in (try_xml, try_yaml, try_markdown, try_toml, try_csv):
        result = probe(stripped)
        if result is not None:
            return result, None

    return Format.TEXT, None
