"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.core.checker import CheckEngine
from axm_init.models.check import Grade


def test_run_all_categories(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """Gold project scores 100 with all 40 checks."""
    engine = CheckEngine(gold_project__from_check_engine_run_and_format)
    result = engine.run()
    assert result.score == 100
    assert result.grade == Grade.A
    assert len(result.checks) == 40


class TestEngineStandalone:
    """Standalone context must be fully regression-safe."""

    def test_engine_standalone_unchanged(
        self, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Standalone gold project still gets 40 checks, score 100."""
        engine = CheckEngine(gold_project__from_check_engine_run_and_format)
        result = engine.run()
        assert result.score == 100
        assert result.grade == Grade.A
        assert len(result.checks) == 40
        assert result.context == "standalone"
        assert result.workspace_root is None
        assert result.excluded_checks == []
