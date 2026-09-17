"""Generate each member's API reference during the aggregated root build.

``mkdocs-monorepo-plugin`` merges the members' ``nav`` into the root site, but
it does not run the plugins a member declares: the member's own
``gen-files``/``literate-nav`` pair never executes here, so nothing emits the
pages its ``Python API: reference/api/`` nav entry points at. Building the
member standalone works (it runs its own plugins); building from the root does
not. This script closes that gap for the aggregated build.

The output path mirrors what each member generates for itself —
``<member>/reference/api/<module path>`` plus a ``SUMMARY.md`` for
literate-nav. Writing anywhere else is what the previous version of this
script did (``reference/<module path>``, with no member prefix and no ``api``
segment): pages no nav referenced, and a "not found in the documentation
files" warning per member.
"""

from pathlib import Path

import mkdocs_gen_files

packages_dir = Path("packages")

for pkg_dir in sorted(packages_dir.iterdir()):
    src_dir = pkg_dir / "src"
    if not src_dir.is_dir():
        continue

    nav = mkdocs_gen_files.Nav()
    for path in sorted(src_dir.rglob("*.py")):
        module_path = path.relative_to(src_dir).with_suffix("")
        parts = list(module_path.parts)

        # Skip private and dunder modules, but keep package ``__init__`` files.
        if any(part.startswith("_") and part != "__init__" for part in parts):
            continue

        # ``__init__.py`` documents its package: map it to an ``index`` page.
        if parts[-1] == "__init__":
            parts = parts[:-1]
            doc_parts = [*parts, "index"]
        else:
            doc_parts = parts

        if not parts:
            continue

        doc_path = Path(*doc_parts).with_suffix(".md")
        full_doc_path = pkg_dir.name / Path("reference", "api", *doc_parts)
        full_doc_path = full_doc_path.with_suffix(".md")

        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            fd.write(f"# `{'.'.join(parts)}`\n\n::: {'.'.join(parts)}\n")

        mkdocs_gen_files.set_edit_path(full_doc_path, path)
        nav[tuple(parts)] = doc_path.as_posix()

    summary = Path(pkg_dir.name, "reference", "api", "SUMMARY.md")
    with mkdocs_gen_files.open(summary, "w") as nav_file:
        nav_file.writelines(nav.build_literate_nav())
