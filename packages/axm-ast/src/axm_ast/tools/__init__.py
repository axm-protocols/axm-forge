"""AXM tool wrappers for axm-ast.

Each tool wraps an axm-ast core function as an AXMTool
for auto-discovery via ``axm.tools`` entry points.
"""

# Register virtual *_text submodules (avoids adding files to TOC).
import axm_ast.tools.impact as _impact  # noqa: F401  # isort: skip
