"""Minification strategy."""

from __future__ import annotations

import json
import re

import yaml

from axm_smelt.core.detector import Format, detect_format
from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["MinifyStrategy"]

# A ``#`` starting a line (outside a quoted scalar) is a YAML comment that
# parse+dump would silently drop.
_YAML_COMMENT_RE = re.compile(r"(?m)^\s*#")


class MinifyStrategy(SmeltStrategy):
    """Remove unnecessary whitespace."""

    @property
    def name(self) -> str:
        """Strategy identifier used in the registry."""
        return "minify"

    @property
    def category(self) -> str:
        """Strategy category (``whitespace``)."""
        return "whitespace"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Minify *ctx* by removing unnecessary whitespace.

        Uses ``ctx.parsed`` when available to avoid redundant
        ``json.loads`` calls. Falls back to text-based detection
        for YAML and XML formats.
        """
        # Fast path: parsed already available — compact serialization
        parsed = ctx.parsed
        if parsed is not None:
            result = json.dumps(
                parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            return SmeltContext(text=result, format=ctx.format, parsed=parsed)

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        # JSON minification
        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                result = json.dumps(
                    data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
                return SmeltContext(text=result, format=ctx.format, parsed=data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Use ctx.format when already set, otherwise detect
        fmt = ctx.format if ctx.format is not Format.TEXT else detect_format(stripped)

        # YAML minification
        if fmt is Format.YAML:
            return SmeltContext(text=self._minify_yaml(stripped), format=ctx.format)

        # XML minification
        if fmt is Format.XML:
            return SmeltContext(text=self._minify_xml(stripped), format=ctx.format)

        return ctx

    @staticmethod
    def _minify_yaml(text: str) -> str:
        """Compact YAML via parse+dump with flow style.

        ``yaml.safe_load`` + ``yaml.dump`` silently drops all comments, so a
        source carrying a ``#`` comment line would lose content — often the
        most useful part to a reader. When a comment is present the input is
        returned unchanged: the ``safe`` preset must never delete content.
        """
        if _YAML_COMMENT_RE.search(text):
            return text
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, (dict, list)):
                return text
            return yaml.dump(
                data,
                default_flow_style=True,
                sort_keys=False,
                width=999,
            ).rstrip("\n")
        except yaml.YAMLError:
            return text

    @staticmethod
    def _minify_xml(text: str) -> str:
        """Strip inter-tag whitespace in XML."""
        # Remove whitespace between tags (but not inside CDATA)
        # Split on CDATA sections to protect their content
        parts = re.split(r"(<!\[CDATA\[.*?\]\]>)", text, flags=re.DOTALL)
        for i, part in enumerate(parts):
            if not part.startswith("<![CDATA["):
                # Remove whitespace between tags
                part = re.sub(r">\s+<", "><", part)
                # Strip whitespace around text nodes
                part = re.sub(
                    r">([ \t]+)([^<])", lambda m: ">" + m.group(2).lstrip(), part
                )
                part = re.sub(
                    r"([^>])([ \t]+)<", lambda m: m.group(1).rstrip() + "<", part
                )
                parts[i] = part
        return "".join(parts).strip()
