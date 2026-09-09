"""Generate module references and navigation for the assembled workspace site."""

from pathlib import Path

import mkdocs_gen_files
import yaml


def _nav_paths(value: object) -> list[str]:
    """Collect page paths from a MkDocs navigation tree."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [path for item in value.values() for path in _nav_paths(item)]
    if isinstance(value, list):
        return [path for item in value for path in _nav_paths(item)]
    return []


packages_dir = Path("packages")
catalog: list[str] = [
    "# Module reference\n",
    (
        "Generated from the workspace source. For supported public contracts, "
        "start with the [package guides](../packages/index.md).\n"
    ),
]

for pkg_dir in sorted(packages_dir.iterdir()):
    src_dir = pkg_dir / "src"
    if not src_dir.is_dir():
        continue
    pages: list[tuple[str, Path]] = []
    for path in sorted(src_dir.rglob("*.py")):
        if "templates" in path.parts or "resources" in path.parts:
            continue
        module_path = path.relative_to(src_dir).with_suffix("")
        doc_path = path.relative_to(src_dir).with_suffix(".md")
        parts = tuple(module_path.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
            doc_path = doc_path.with_name("index.md")
        elif parts[-1] in ("__main__", "_version"):
            continue
        identifier = ".".join(parts)
        full_doc_path = Path("reference", doc_path)
        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            fd.write(f"::: {identifier}\n")
        mkdocs_gen_files.set_edit_path(full_doc_path, path)
        pages.append((identifier, doc_path))

    catalog.append(f"## {pkg_dir.name}\n")
    catalog.extend(f"- [{name}]({path.as_posix()})\n" for name, path in pages)

    # Package generators do not run when monorepo includes their navigation.
    # Supply directory landings that their standalone gen-files step owns.
    config_path = pkg_dir / "mkdocs.yml"
    if not config_path.is_file():
        continue
    config = yaml.load(config_path.read_text(), Loader=yaml.BaseLoader)
    if "reference/api/" not in _nav_paths(config.get("nav", [])):
        continue
    if (pkg_dir / "docs/reference/api/index.md").is_file():
        continue
    landing = Path(config["site_name"], "reference/api/index.md")
    with mkdocs_gen_files.open(landing, "w") as fd:
        fd.write(f"# {pkg_dir.name} module reference\n\n")
        fd.writelines(
            f"- [{name}](../../../reference/{path.as_posix()})\n"
            for name, path in pages
        )

with mkdocs_gen_files.open("reference/index.md", "w") as fd:
    fd.write("\n".join(catalog))
