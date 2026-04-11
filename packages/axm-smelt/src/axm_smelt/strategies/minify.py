"""Minification strategy."""

from __future__ import annotations

import json
import re

import yaml

from axm_smelt.core.detector import Format, detect_format
from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["MinifyStrategy"]


class MinifyStrategy(SmeltStrategy):
    """Remove unnecessary whitespace."""

    @property
    def name(self) -> str:
        return "minify"

    @property
    def category(self) -> str:
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
            result = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
            new_ctx = SmeltContext(text=result, format=ctx.format)
            new_ctx._parsed = parsed
            return new_ctx

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        # JSON minification
        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                result = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
                new_ctx = SmeltContext(text=result, format=ctx.format)
                new_ctx._parsed = data
                return new_ctx
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
        """Compact YAML via parse+dump with flow style."""
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
