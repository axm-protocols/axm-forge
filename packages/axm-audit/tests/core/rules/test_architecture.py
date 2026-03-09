"""Tests for Architecture Rules — RED phase."""

from pathlib import Path


class TestCircularImportRule:
    """Tests for CircularImportRule (import graph + Tarjan SCC)."""

    def test_no_cycles_passes(self, tmp_path: Path) -> None:
        """Clean project with no circular imports passes."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("from src import b\n")
        (src / "b.py").write_text("x = 1\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["cycles"] == []

    def test_detects_simple_cycle(self, tmp_path: Path) -> None:
        """Detects A→B→A cycle."""
        from axm_audit.core.rules.architecture import CircularImportRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # Use direct imports that match module names
        (src / "a.py").write_text("import b\n")
        (src / "b.py").write_text("import a\n")

        rule = CircularImportRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["cycles"]) > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_CIRCULAR."""
        from axm_audit.core.rules.architecture import CircularImportRule

        rule = CircularImportRule()
        assert rule.rule_id == "ARCH_CIRCULAR"


class TestGodClassRule:
    """Tests for GodClassRule (line count + method count)."""

    def test_small_class_passes(self, tmp_path: Path) -> None:
        """Class under thresholds passes."""
        from axm_audit.core.rules.architecture import GodClassRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "small.py").write_text('''
class SmallClass:
    """A small class."""

    def method_a(self) -> None:
        pass

    def method_b(self) -> None:
        pass
''')

        rule = GodClassRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_detects_class_with_many_methods(self, tmp_path: Path) -> None:
        """Flags class with >15 methods."""
        from axm_audit.core.rules.architecture import GodClassRule

        src = tmp_path / "src"
        src.mkdir()
        methods = "\n".join(
            f"    def method_{i}(self) -> None:\n        pass\n" for i in range(20)
        )
        (src / "god.py").write_text(f"class GodClass:\n{methods}")

        rule = GodClassRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["god_classes"]) > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_GOD_CLASS."""
        from axm_audit.core.rules.architecture import GodClassRule

        rule = GodClassRule()
        assert rule.rule_id == "ARCH_GOD_CLASS"


class TestCouplingMetricRule:
    """Tests for CouplingMetricRule (fan-in/fan-out)."""

    def test_low_coupling_passes(self, tmp_path: Path) -> None:
        """Low coupling project passes."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "a.py").write_text("x = 1\n")
        (src / "b.py").write_text("y = 2\n")

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_detects_high_coupling(self, tmp_path: Path) -> None:
        """Flags module with many imports (high fan-out)."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # Create many distinct modules
        for i in range(15):
            (src / f"mod_{i}.py").write_text(f"val_{i} = {i}\n")
        # Create hub module that imports all (distinct module names)
        imports = "\n".join(f"import mod_{i}" for i in range(15))
        (src / "hub.py").write_text(imports)

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["max_fan_out"] >= 10
        assert result.details["n_over_threshold"] >= 1

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_COUPLING."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        assert rule.rule_id == "ARCH_COUPLING"


class TestTarjanSCC:
    """Direct tests for the iterative _tarjan_scc algorithm."""

    def test_tarjan_iterative_simple_cycle(self) -> None:
        """A→B→A graph detects SCC [A, B]."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        graph = {"A": {"B"}, "B": {"A"}}
        sccs = _tarjan_scc(graph)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A", "B"}

    def test_tarjan_iterative_no_cycle(self) -> None:
        """A→B→C linear chain produces no SCCs."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        graph = {"A": {"B"}, "B": {"C"}, "C": set()}
        sccs = _tarjan_scc(graph)
        assert sccs == []

    def test_tarjan_iterative_multiple_sccs(self) -> None:
        """Two independent cycles both detected."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        graph = {
            "A": {"B"},
            "B": {"A"},
            "C": {"D"},
            "D": {"C"},
        }
        sccs = _tarjan_scc(graph)
        assert len(sccs) == 2
        scc_sets = [set(scc) for scc in sccs]
        assert {"A", "B"} in scc_sets
        assert {"C", "D"} in scc_sets

    def test_tarjan_deep_chain_no_recursion_error(self) -> None:
        """2000-node linear chain completes without RecursionError."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        n = 2000
        graph: dict[str, set[str]] = {}
        for i in range(n):
            graph[f"n{i}"] = {f"n{i + 1}"} if i < n - 1 else set()
        # Should not raise RecursionError
        sccs = _tarjan_scc(graph)
        assert sccs == []

    def test_tarjan_self_loop(self) -> None:
        """A→A self-loop is not reported (len=1 filtered)."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        graph = {"A": {"A"}}
        sccs = _tarjan_scc(graph)
        assert sccs == []

    def test_tarjan_disconnected_nodes(self) -> None:
        """Nodes with no edges produce no SCCs."""
        from axm_audit.core.rules.architecture import _tarjan_scc

        graph: dict[str, set[str]] = {"A": set(), "B": set(), "C": set()}
        sccs = _tarjan_scc(graph)
        assert sccs == []
