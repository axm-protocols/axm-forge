from __future__ import annotations

from pathlib import Path


def _make_pkg(tmp_path: Path, pkg_name: str = "pkg") -> Path:
    """Create a minimal package under tmp_path/src for src_path detection."""
    src = tmp_path / "src"
    pkg = src / pkg_name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").touch()
    return src


# ---------------------------------------------------------------------------
# Unit tests — _classify_module_role (AC1, AC5)
# ---------------------------------------------------------------------------


class TestClassifyModuleRole:
    """Verify orchestrator vs leaf classification based on sibling diversity."""

    def test_classify_orchestrator_3_siblings(self, tmp_path: Path) -> None:
        """3 distinct sibling imports → orchestrator."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        imports = [
            "pkg.core.rules.a",
            "pkg.core.rules.b",
            "pkg.core.rules.c",
        ]
        result = classify_module_role("pkg.core.rules.quality", imports, src_path)
        assert result == "orchestrator"

    def test_classify_leaf_2_siblings(self, tmp_path: Path) -> None:
        """Only 2 sibling imports → leaf."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        imports = [
            "pkg.core.rules.a",
            "pkg.core.rules.b",
        ]
        result = classify_module_role("pkg.core.rules.quality", imports, src_path)
        assert result == "leaf"

    def test_classify_ignores_external_imports(self, tmp_path: Path) -> None:
        """External imports (stdlib/third-party) are excluded from sibling count."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        imports = [
            "os",
            "pathlib",
            "typing",
            "pkg.core.rules.a",
        ]
        result = classify_module_role("pkg.core.rules.quality", imports, src_path)
        assert result == "leaf"

    def test_flat_package_all_leaf(self, tmp_path: Path) -> None:
        """Flat package (no subpackages) — all modules classified as leaf."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        # Top-level modules, no dotted subpackage structure
        imports = [
            "pkg.module_a",
            "pkg.module_b",
            "pkg.module_c",
        ]
        result = classify_module_role("pkg.module_x", imports, src_path)
        assert result == "leaf"

    def test_one_deep_subpackage_2_siblings(self, tmp_path: Path) -> None:
        """Two siblings under one deep subpackage → 2 < 3 → leaf."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        imports = [
            "pkg.a.b.c.d",
            "pkg.a.b.c.e",
        ]
        result = classify_module_role("pkg.a.b.c.f", imports, src_path)
        assert result == "leaf"


# ---------------------------------------------------------------------------
# Threshold resolution — orchestrator bonus in _build_coupling_result (AC3, AC4)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Config parsing — orchestrator_bonus in _read_coupling_config (AC2)
# ---------------------------------------------------------------------------


class TestReadCouplingConfigOrchestratorBonus:
    """Verify orchestrator_bonus is parsed from pyproject.toml."""

    def test_read_coupling_config_orchestrator_bonus(self, tmp_path: Path) -> None:
        """orchestrator_bonus = 8 in pyproject.toml → config returns 8."""
        from axm_audit.core.rules.architecture.coupling import read_coupling_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.axm-audit.coupling]\nthreshold = 10\norchestrator_bonus = 8\n"
        )
        threshold, _, bonus, _ = read_coupling_config(tmp_path)
        assert threshold == 10
        assert bonus == 8

    def test_read_coupling_config_default_bonus(self, tmp_path: Path) -> None:
        """Missing orchestrator_bonus → default 5."""
        from axm_audit.core.rules.architecture.coupling import read_coupling_config

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.axm-audit.coupling]\nthreshold = 10\n")
        _, _, bonus, _ = read_coupling_config(tmp_path)
        assert bonus == 5
