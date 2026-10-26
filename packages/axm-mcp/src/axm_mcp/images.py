"""Bounded image snapshots become MCP image blocks, never JSON text."""

from __future__ import annotations

import base64
import io

from axm import ToolImage, ToolResult
from mcp.types import CallToolResult, ImageContent, TextContent
from PIL import Image, UnidentifiedImageError

_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}


def _validated(image: ToolImage) -> ToolImage:
    """Reject malformed or oversized decoded images before they enter a chat."""
    snapshot = ToolImage(data=image.data, mime_type=image.mime_type)
    try:
        with Image.open(io.BytesIO(snapshot.data)) as decoded:
            width, height = decoded.size
            if (
                decoded.format != _FORMATS[snapshot.mime_type]
                or not 0 < width <= ToolImage.MAX_SIDE
                or not 0 < height <= ToolImage.MAX_SIDE
                or width * height > ToolImage.MAX_PIXELS
                or getattr(decoded, "is_animated", False)
            ):
                raise ValueError(
                    "tool image must be a still image within 4096 px and 16 MP"
                )
            decoded.load()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError(
            "tool image is not a complete decodable PNG, JPEG or WebP"
        ) from exc
    return snapshot


__all__ = ["image_result"]


def image_result(images: object, text: str) -> CallToolResult:
    """Encode validated snapshots without reading files or duplicating data.

    Revalidate at the transport seam too: structural AXM tools may return a
    result-like object rather than the SDK dataclass.
    """
    if not isinstance(images, tuple) or any(
        not isinstance(image, ToolImage) for image in images
    ):
        raise ValueError("images must be a tuple of ToolImage snapshots")
    checked = ToolResult(success=True, images=images)
    snapshots = tuple(_validated(image) for image in checked.images)
    return CallToolResult(
        content=[
            TextContent(type="text", text=text),
            *(
                ImageContent(
                    type="image",
                    data=base64.b64encode(image.data).decode("ascii"),
                    mime_type=image.mime_type,
                )
                for image in snapshots
            ),
        ],
        is_error=False,
    )
