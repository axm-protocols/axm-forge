"""Split from ``test_compress_filtering.py``."""

import json

from axm_ast.formatters import format_compressed, format_json


def test_compress_smaller_than_summary(pkg_with_tests):
    """Compressed output must be smaller than JSON summary."""
    compressed = format_compressed(pkg_with_tests)
    summary = format_json(pkg_with_tests, detail="summary")
    assert len(compressed) <= len(json.dumps(summary))
