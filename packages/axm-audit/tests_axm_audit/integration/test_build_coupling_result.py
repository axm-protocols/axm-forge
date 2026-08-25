"""Split from ``test_coupling_orchestrator.py``."""

from pathlib import Path


def _make_pkg(tmp_path: Path, pkg_name: str = "pkg") -> Path:
    """Create a minimal package under tmp_path/src for src_path detection."""
    src = tmp_path / "src"
    pkg = src / pkg_name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").touch()
    return src


class TestOrchestratorBonusThreshold:
    """Verify effective threshold = override > base+bonus > base."""

    def test_orchestrator_bonus_applied(self, tmp_path: Path) -> None:
        """fan_out=12, base=10, bonus=5 → effective=15 → not over threshold."""
        from axm_audit.core.rules.architecture.coupling import build_coupling_result

        src_path = _make_pkg(tmp_path, "pkg")
        fan_out = {"pkg.core.rules.quality": 12}
        fan_in = {"pkg.core.rules.a": 1}
        imports_map = {
            "pkg.core.rules.quality": [
                "pkg.core.rules.a",
                "pkg.core.rules.b",
                "pkg.core.rules.c",
                "pkg.utils.d",
                "pkg.utils.e",
                "pkg.utils.f",
                "pkg.utils.g",
                "pkg.utils.h",
                "pkg.utils.i",
                "os",
                "pathlib",
                "typing",
            ],
        }
        result = build_coupling_result(
            fan_out,
            fan_in,
            threshold=10,
            overrides=None,
            orchestrator_bonus=5,
            imports_map=imports_map,
            src_path=src_path,
        )
        assert result["over_threshold"] == []

    def test_override_takes_precedence_over_bonus(self, tmp_path: Path) -> None:
        """Per-module override=8 wins over bonus; fan_out=9 > 8 → over."""
        from axm_audit.core.rules.architecture.coupling import build_coupling_result

        src_path = _make_pkg(tmp_path, "pkg")
        fan_out = {"pkg.core.rules.quality": 9}
        fan_in = {"pkg.core.rules.a": 1}
        imports_map = {
            "pkg.core.rules.quality": [
                "pkg.core.rules.a",
                "pkg.core.rules.b",
                "pkg.core.rules.c",
                "pkg.utils.d",
                "pkg.utils.e",
                "pkg.utils.f",
                "os",
                "pathlib",
                "typing",
            ],
        }
        result = build_coupling_result(
            fan_out,
            fan_in,
            threshold=10,
            overrides={"pkg.core.rules.quality": 8},
            orchestrator_bonus=5,
            imports_map=imports_map,
            src_path=src_path,
        )
        over = result["over_threshold"]
        assert len(over) == 1
        assert over[0]["module"] == "pkg.core.rules.quality"

    def test_over_threshold_includes_role_and_effective_threshold(
        self, tmp_path: Path
    ) -> None:
        """AC4: over_threshold entries carry role + effective_threshold keys."""
        from axm_audit.core.rules.architecture.coupling import build_coupling_result

        src_path = _make_pkg(tmp_path, "pkg")
        fan_out = {"pkg.core.rules.quality": 16}
        fan_in = {"pkg.core.rules.a": 1}
        imports_map = {
            "pkg.core.rules.quality": [
                "pkg.core.rules.a",
                "pkg.core.rules.b",
                "pkg.core.rules.c",
                "pkg.utils.d",
                "pkg.utils.e",
                "pkg.utils.f",
                "pkg.utils.g",
                "pkg.utils.h",
                "pkg.utils.i",
                "pkg.utils.j",
                "pkg.utils.k",
                "pkg.utils.l",
                "os",
                "pathlib",
                "typing",
                "typing_extensions",
            ],
        }
        result = build_coupling_result(
            fan_out,
            fan_in,
            threshold=10,
            overrides=None,
            orchestrator_bonus=5,
            imports_map=imports_map,
            src_path=src_path,
        )
        assert len(result["over_threshold"]) == 1
        entry = result["over_threshold"][0]
        assert entry["role"] == "orchestrator"
        assert entry["effective_threshold"] == 15

    def test_orchestrator_bonus_zero_no_bonus(self, tmp_path: Path) -> None:
        """orchestrator_bonus=0 disables bonus; fan_out=11 > base=10 → over."""
        from axm_audit.core.rules.architecture.coupling import build_coupling_result

        src_path = _make_pkg(tmp_path, "pkg")
        fan_out = {"pkg.core.rules.quality": 11}
        fan_in = {"pkg.core.rules.a": 1}
        imports_map = {
            "pkg.core.rules.quality": [
                "pkg.core.rules.a",
                "pkg.core.rules.b",
                "pkg.core.rules.c",
                "pkg.utils.d",
                "pkg.utils.e",
                "pkg.utils.f",
                "pkg.utils.g",
                "pkg.utils.h",
                "os",
                "pathlib",
                "typing",
            ],
        }
        result = build_coupling_result(
            fan_out,
            fan_in,
            threshold=10,
            overrides=None,
            orchestrator_bonus=0,
            imports_map=imports_map,
            src_path=src_path,
        )
        assert len(result["over_threshold"]) == 1
