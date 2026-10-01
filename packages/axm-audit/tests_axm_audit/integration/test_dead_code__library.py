"""Dead-code audit is a hermetic library analysis, independent of CLI PATH."""

from pathlib import Path

import pytest

from axm_audit.core.rules.dead_code import DeadCodeRule

pytestmark = pytest.mark.integration


def test_dead_code_requires_no_executable_or_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "src" / "sample"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "unused.py").write_text("def abandoned():\n    return 42\n")
    monkeypatch.setenv("PATH", "")

    def refuse(*args: object, **kwargs: object) -> None:
        pytest.fail("dead-code spawned a subprocess")

    monkeypatch.setattr("subprocess.Popen", refuse)
    result = DeadCodeRule().check(tmp_path)

    assert not result.passed
    assert result.score == 95
    assert result.details is not None
    assert result.details["symbols"] == [
        {
            "name": "abandoned",
            "module_path": str(package / "unused.py"),
            "line": 1,
            "kind": "function",
        }
    ]
