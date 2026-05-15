"""Integration tests for ``FileNamingRule`` on synthetic projects.

Each scenario builds a temporary project tree with carefully crafted test
files and runs the rule end-to-end (filesystem I/O is the boundary).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.file_naming import FileNamingRule

pytestmark = pytest.mark.integration

_PYPROJECT_DEFAULT = (
    textwrap.dedent(
        """
    [project]
    name = "mypkg"
    version = "0"
    """
    ).strip()
    + "\n"
)

_PYPROJECT_SINGLE_BINARY = (
    textwrap.dedent(
        """
    [project]
    name = "mypkg"
    version = "0"

    [project.scripts]
    pkg-cli = "mypkg.cli:main"
    """
    ).strip()
    + "\n"
)


def _seed_pkg(project: Path, pyproject: str = _PYPROJECT_DEFAULT) -> None:
    """Create a minimal src/mypkg + pyproject layout."""
    (project / "src" / "mypkg").mkdir(parents=True, exist_ok=True)
    (project / "src" / "mypkg" / "__init__.py").write_text(
        "class Rule:\n    pass\nclass Engine:\n    pass\n"
    )
    (project / "pyproject.toml").write_text(pyproject)


def _findings(project: Path) -> list[dict[str, object]]:
    result = FileNamingRule().check(project)
    return list(result.details.get("findings", [])) if result.details else []


def test_name_mismatch_emits_info_finding(tmp_path: Path) -> None:
    """AC4 — name diverging from canonical emits NAME_MISMATCH at INFO."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_foo.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    findings = _findings(project)
    assert len(findings) == 1
    f = findings[0]
    assert f["verdict"] == "NAME_MISMATCH"
    assert f["severity"] == "info"
    assert f["proposed_name"] == "test_rule.py"
    assert f["current_name"] == "test_foo.py"
    assert f["tier"] == "integration"


def test_name_match_no_finding(tmp_path: Path) -> None:
    """AC4 — file whose name matches its canonical emits nothing."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_rule.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    assert _findings(project) == []


def test_split_emits_warning(tmp_path: Path) -> None:
    """AC5 — distinct tuples across tests emit a single SPLIT WARNING."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_mixed.py").write_text(
        "from mypkg import Rule, Engine\n\n"
        "def test_one():\n    Rule()\n\n"
        "def test_two():\n    Engine()\n"
    )

    findings = _findings(project)
    splits = [f for f in findings if f["verdict"] == "SPLIT"]
    assert len(splits) == 1
    s = splits[0]
    assert s["severity"] == "warning"
    suggested = set(s["suggested_splits"])
    assert {"test_rule.py", "test_engine.py"} <= suggested


def test_collide_emits_warning_per_group(tmp_path: Path) -> None:
    """AC6 — two integration files proposing the same name emit one COLLIDE."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_a.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )
    (project / "tests" / "integration" / "test_b.py").write_text(
        "from mypkg import Rule\n\ndef test_y():\n    Rule()\n"
    )

    findings = _findings(project)
    collides = [f for f in findings if f["verdict"] == "COLLIDE"]
    assert len(collides) == 1
    c = collides[0]
    assert c["severity"] == "warning"
    assert c["canonical_name"] == "test_rule.py"
    files = {Path(p).name for p in c["files"]}
    assert files == {"test_a.py", "test_b.py"}


def test_collide_groups_by_tier(tmp_path: Path) -> None:
    """AC6 — same canonical name in different tiers is not a COLLIDE."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "e2e").mkdir(parents=True)
    (project / "tests" / "integration" / "test_rule.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )
    (project / "tests" / "e2e" / "test_rule.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    findings = _findings(project)
    assert [f for f in findings if f["verdict"] == "COLLIDE"] == []


def test_marker_scenario_name_ok_skips_mismatch_only(tmp_path: Path) -> None:
    """AC7 — marker suppresses NAME_MISMATCH only; SPLIT survives."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_unrelated_name.py").write_text(
        "import pytest\n"
        "from mypkg import Rule, Engine\n\n"
        "pytestmark = pytest.mark.scenario_name_ok\n\n"
        "def test_one():\n    Rule()\n\n"
        "def test_two():\n    Engine()\n"
    )

    findings = _findings(project)
    verdicts = {f["verdict"] for f in findings}
    assert "NAME_MISMATCH" not in verdicts
    assert "SPLIT" in verdicts


def test_e2e_single_binary_emission(tmp_path: Path) -> None:
    """AC3 — single-binary e2e strips the binary prefix from the canonical."""
    project = tmp_path / "proj"
    _seed_pkg(project, pyproject=_PYPROJECT_SINGLE_BINARY)
    (project / "tests" / "e2e").mkdir(parents=True)
    (project / "tests" / "e2e" / "test_x.py").write_text(
        'import subprocess\n\ndef test_y():\n    subprocess.run(["pkg-cli", "do"])\n'
    )

    findings = _findings(project)
    mismatches = [f for f in findings if f["verdict"] == "NAME_MISMATCH"]
    assert len(mismatches) == 1
    assert mismatches[0]["proposed_name"] == "test_do.py"


def test_score_arithmetic(tmp_path: Path) -> None:
    """AC9 — score = 100 - 1 * n_info - 3 * n_warning."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    for stem, sym in (("test_foo.py", "Rule"), ("test_bar.py", "Engine")):
        (project / "tests" / "integration" / stem).write_text(
            f"from mypkg import {sym}\n\ndef test_x():\n    {sym}()\n"
        )
    (project / "tests" / "e2e").mkdir(parents=True)
    (project / "tests" / "e2e" / "test_baz.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )
    (project / "tests" / "integration" / "test_split.py").write_text(
        "from mypkg import Rule, Engine\n\n"
        "def test_a():\n    Rule()\n\n"
        "def test_b():\n    Engine()\n"
    )

    result = FileNamingRule().check(project)
    findings = result.details.get("findings", []) if result.details else []
    n_info = len([f for f in findings if f["severity"] == "info"])
    n_warning = len([f for f in findings if f["severity"] == "warning"])
    expected = max(0, 100 - 1 * n_info - 3 * n_warning)
    assert result.score == expected
    assert (n_info, n_warning) == (3, 1)
    assert result.score == 94


def test_score_floors_at_zero(tmp_path: Path) -> None:
    """AC9 — score floors at 0 when penalties exceed 100."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    # Each file: name diverges (NAME_MISMATCH INFO) AND tests cover 2 unrelated
    # tuples (SPLIT WARNING). 40 such files yield 40*1 + 40*3 = 160 penalty,
    # well past the 100 floor.
    for i in range(40):
        (project / "tests" / "integration" / f"test_misnamed_{i}.py").write_text(
            "from mypkg import Rule, Engine\n\n"
            "def test_a():\n    Rule()\n\n"
            "def test_b():\n    Engine()\n"
        )

    result = FileNamingRule().check(project)
    assert result.score == 0
