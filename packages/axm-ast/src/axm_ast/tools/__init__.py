"""AXM tool wrappers for axm-ast.

Each tool wraps an axm-ast core function as an AXMTool
for auto-discovery via ``axm.tools`` entry points.
"""

# Register virtual impact_text submodule (avoids adding a file to TOC).
import axm_ast.tools.impact as _impact  # noqa: F401  # isort: skip
