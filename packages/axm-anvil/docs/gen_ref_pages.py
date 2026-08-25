"""Auto-generate API reference pages by walking the source tree.

This script is executed by the mkdocs-gen-files plugin during build.
It scans ``src/axm_anvil/`` for Python modules and generates a
``::: module.path`` page for each, which mkdocstrings then renders
under ``reference/api/axm_anvil/``. A ``SUMMARY.md`` is emitted for the
mkdocs-literate-nav plugin so the reference tree is navigable. The
``api/`` prefix matches the ``Python API: reference/api/`` nav entry in
``mkdocs.yml``.

See: https://mkdocstrings.github.io/recipes/#automatic-code-reference-pages
"""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()
src = Path("src")
package = "axm_anvil"

for path in sorted(src.rglob("*.py")):
    module_path = path.relative_to(src).with_suffix("")
    parts = list(module_path.parts)

    # Skip private / dunder modules, but keep package ``__init__`` files.
    if any(part.startswith("_") and part != "__init__" for part in parts):
        continue

    # ``__init__.py`` documents its package; map it to an ``index`` page so the
    # rendered tree exposes ``reference/<package>/index.md``.
    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_parts = [*parts, "index"]
    else:
        doc_parts = parts

    if not parts:
        continue

    module_name = ".".join(parts)
    doc_path = Path(*doc_parts).with_suffix(".md")
    full_doc_path = Path("reference", "api", *doc_parts).with_suffix(".md")

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"# `{module_name}`\n\n::: {module_name}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, Path("..", "..", "..") / path)
    nav[tuple(parts)] = doc_path.as_posix()

with mkdocs_gen_files.open("reference/api/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
