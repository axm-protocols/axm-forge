"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.core.checker import format_json
from tests.integration._helpers import _make_result


class TestFormatJson:
    """Tests for format_json()."""

    def test_structure(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=True)
        data = format_json(result)
        assert set(data.keys()) == {
            "project",
            "score",
            "grade",
            "context",
            "workspace_root",
            "excluded_checks",
            "categories",
            "checks",
            "failures",
        }
        assert data["score"] == 100
        assert data["grade"] == "A"

    def test_failures_list(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=False)
        data = format_json(result)
        assert len(data["failures"]) == 1
        assert data["failures"][0]["fix"] == "Run fix command"
