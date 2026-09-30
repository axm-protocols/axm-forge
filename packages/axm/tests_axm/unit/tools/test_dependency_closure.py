"""The read closure follows active requirements without executing dependencies."""

from importlib import metadata
from pathlib import Path

from axm.tools._dependency_probe import closure, declared_requirements


def test_active_transitive_extras_and_dev_groups(tmp_path: Path, monkeypatch) -> None:
    requirements = declared_requirements(
        {
            "project": {"dependencies": ["api[registry]"]},
            "dependency-groups": {
                "dev": [{"include-group": "test"}],
                "test": ["witness"],
                "docs": ["not-installed"],
            },
        }
    )
    for name, children in {
        "api": ["registry; extra == 'registry'", "not-installed; python_version < '2'"],
        "registry": ["leaf"],
        "leaf": [],
        "witness": [],
    }.items():
        dist = tmp_path / f"{name}-1.dist-info"
        dist.mkdir()
        dist.joinpath("METADATA").write_text(
            f"Name: {name}\nVersion: 1\n"
            + "".join(f"Requires-Dist: {child}\n" for child in children)
        )
    monkeypatch.setattr(
        metadata,
        "distribution",
        lambda name: next(
            dist
            for dist in metadata.distributions(path=[str(tmp_path)])
            if dist.metadata["Name"] == name
        ),
    )
    assert {dist.metadata["Name"] for dist in closure(requirements)} == {
        "api",
        "registry",
        "leaf",
        "witness",
    }
