"""Image snapshots are bounded and never leak bytes in representations."""

from __future__ import annotations

import pytest

from axm import ToolImage, ToolResult


def test_image_bytes_are_not_in_result_representations() -> None:
    image = ToolImage(b"\x89PNG\r\n\x1a\nprivate-pixels")
    result = ToolResult(success=True, text="page 1", images=(image,))
    assert "private-pixels" not in repr(image)
    assert "private-pixels" not in repr(result)
    assert result.images[0].data.endswith(b"private-pixels")


@pytest.mark.parametrize(
    ("data", "mime_type"),
    [(b"", "image/png"), (b"not a picture", "image/png"), (b"<svg/>", "image/svg+xml")],
)
def test_untyped_or_empty_images_are_refused(data: bytes, mime_type: str) -> None:
    with pytest.raises(ValueError):
        ToolImage(data, mime_type)


def test_individual_and_aggregate_image_budgets_are_enforced() -> None:
    with pytest.raises(ValueError, match="encoded bytes"):
        ToolImage(b"\x89PNG\r\n\x1a\n" + b"x" * (4 * 1024 * 1024))
    image = ToolImage(b"\x89PNG\r\n\x1a\n" + b"x" * (4 * 1024 * 1024 - 8))
    with pytest.raises(ValueError, match="four images"):
        ToolResult(success=True, images=(image,) * 5)
    with pytest.raises(ValueError, match="twelve MiB"):
        ToolResult(success=True, images=(image,) * 4)


def test_existing_text_results_keep_an_empty_image_channel() -> None:
    result = ToolResult(success=True, data={"value": 42}, text="42")
    assert result.images == ()
    assert result.data == {"value": 42}
