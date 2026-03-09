"""Generate code reference pages for mkdocstrings."""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

packages = [
    ("axm_ast", "packages/axm-ast/src"),
    ("axm_audit", "packages/axm-audit/src"),
    ("axm_init", "packages/axm-init/src"),
    ("axm_git", "packages/axm-git/src"),
]

for package_name, src_path in packages:
    src_root = Path(src_path) / package_name
    if not src_root.exists():
        continue

    for path in sorted(src_root.rglob("*.py")):
        # Skip template directories (Copier/Jinja files, not real Python)
        if "templates" in path.parts:
            continue

        module_path = path.relative_to(Path(src_path))
        doc_path = path.relative_to(Path(src_path)).with_suffix(".md")
        full_doc_path = Path("reference", doc_path)

        parts = tuple(module_path.with_suffix("").parts)

        if parts[-1] == "__init__":
            parts = parts[:-1]
            doc_path = doc_path.with_name("index.md")
            full_doc_path = full_doc_path.with_name("index.md")
        elif parts[-1] == "__main__" or parts[-1].startswith("_"):
            continue

        nav[parts] = doc_path.as_posix()

        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            ident = ".".join(parts)
            fd.write(f"::: {ident}\n")

        mkdocs_gen_files.set_edit_path(full_doc_path, path.as_posix())

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
