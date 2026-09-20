"""Unit tests for the learning profile check (``axm_init.checks.learning``).

The check validates the opt-in ``[tool.axm-init.learning]`` table of a
generated project. ``check_learning_profile`` is wrapped by ``requires_toml``,
so the public callable takes only the project path and loads ``pyproject.toml``
itself; ``__wrapped__`` is the undecorated ``(project, data)`` body, which the
table-level cases below drive directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks import learning as learning_module
from axm_init.checks.learning import check_learning_profile
from axm_init.core.checker import get_check_name

# The undecorated body: ``(project, data) -> CheckResult``.
_check_table = check_learning_profile.__wrapped__


def _profile(**fields: object) -> dict[str, object]:
    """Wrap *fields* into a full ``[tool.axm-init.learning]`` TOML tree."""
    return {"tool": {"axm-init": {"learning": dict(fields)}}}


@pytest.fixture
def generated_project(tmp_path: Path) -> Path:
    """A project directory carrying both generated learning config files."""
    (tmp_path / "study.toml").write_text("", encoding="utf-8")
    (tmp_path / "training.toml").write_text("", encoding="utf-8")
    return tmp_path


class TestValidProfile:
    """A complete, supported profile passes and names its domain."""

    def test_complete_profile_passes_and_reports_its_domain(
        self, generated_project: Path
    ) -> None:
        """The profile a ``kind="learning"`` scaffold emits is accepted as-is."""
        result = _check_table(
            generated_project,
            _profile(schema_version=1, domain="learn_member"),
        )

        assert result.passed is True
        assert result.message == "Learning profile for learn_member is configured"
        assert result.details == []
        assert result.fix == ""
        assert result.weight == 2

    def test_reported_domain_follows_the_declared_one(
        self, generated_project: Path
    ) -> None:
        """The pass message echoes the declared domain, not a fixed string."""
        result = _check_table(
            generated_project,
            _profile(schema_version=1, domain="vision_transfer"),
        )

        assert result.passed is True
        assert result.message == "Learning profile for vision_transfer is configured"


class TestNoProfileDeclared:
    """Opt-in metadata: its absence is a pass that scores nothing."""

    @pytest.mark.parametrize(
        ("data", "case"),
        [
            pytest.param({}, "no tool table at all", id="no_tool"),
            pytest.param({"tool": {}}, "no axm-init table", id="no_axm_init"),
            pytest.param(
                {"tool": {"axm-init": {"exclude": ["ci"]}}},
                "axm-init present without learning",
                id="axm_init_without_learning",
            ),
        ],
    )
    def test_absent_table_passes_with_zero_weight(
        self, tmp_path: Path, data: dict[str, object], case: str
    ) -> None:
        """A project with no profile passes and contributes no points (%s)."""
        result = _check_table(tmp_path, data)

        assert result.passed is True, case
        assert result.message == "No learning profile declared"
        assert result.weight == 0
        assert result.details == []

    def test_absent_table_is_not_penalised_by_missing_config_files(
        self, tmp_path: Path
    ) -> None:
        """No profile means study.toml/training.toml are never required."""
        assert not (tmp_path / "study.toml").exists()
        assert not (tmp_path / "training.toml").exists()

        result = _check_table(tmp_path, {"tool": {"axm-init": {}}})

        assert result.passed is True
        assert result.details == []


class TestDomainRefusal:
    """A declared profile must carry a non-empty string domain."""

    @pytest.mark.parametrize(
        "domain",
        [
            pytest.param(None, id="missing"),
            pytest.param("", id="empty_string"),
            pytest.param(42, id="not_a_string"),
            pytest.param(["learn_member"], id="list_instead_of_string"),
        ],
    )
    def test_invalid_domain_is_refused(
        self, generated_project: Path, domain: object
    ) -> None:
        """A missing or non-string domain fails with the domain complaint."""
        fields: dict[str, object] = {"schema_version": 1}
        if domain is not None:
            fields["domain"] = domain

        result = _check_table(generated_project, _profile(**fields))

        assert result.passed is False
        assert result.message == "Learning profile configuration is incomplete"
        assert result.details == [
            "Missing or invalid domain in [tool.axm-init.learning]"
        ]
        assert result.weight == 2
        assert (
            result.fix
            == "Regenerate the learning profile to restore its configuration files."
        )


class TestSchemaVersionRefusal:
    """Only schema_version 1 is supported; anything else is refused."""

    @pytest.mark.parametrize(
        ("schema_version", "rendered"),
        [
            pytest.param(None, "None", id="missing"),
            pytest.param(2, "2", id="future_version"),
            pytest.param(0, "0", id="zero"),
            pytest.param("1", "'1'", id="string_not_int"),
        ],
    )
    def test_unsupported_schema_version_is_refused(
        self,
        generated_project: Path,
        schema_version: object,
        rendered: str,
    ) -> None:
        """The refusal names both the expected version and the value seen."""
        fields: dict[str, object] = {"domain": "learn_member"}
        if schema_version is not None:
            fields["schema_version"] = schema_version

        result = _check_table(generated_project, _profile(**fields))

        assert result.passed is False
        assert result.details == [
            "Unsupported schema_version in [tool.axm-init.learning]: "
            f"expected 1, got {rendered}"
        ]

    def test_supported_version_is_exactly_one(self, generated_project: Path) -> None:
        """Version 1 raises no schema complaint, unlike its neighbours."""
        result = _check_table(generated_project, _profile(schema_version=1, domain="d"))

        assert result.passed is True
        assert result.details == []


class TestGeneratedConfigFiles:
    """A declared profile must be backed by its generated config files."""

    @pytest.mark.parametrize(
        ("present", "missing"),
        [
            pytest.param((), ("study.toml", "training.toml"), id="both_missing"),
            pytest.param(("study.toml",), ("training.toml",), id="training_missing"),
            pytest.param(("training.toml",), ("study.toml",), id="study_missing"),
        ],
    )
    def test_missing_config_files_are_listed_by_name(
        self,
        tmp_path: Path,
        present: tuple[str, ...],
        missing: tuple[str, ...],
    ) -> None:
        """Each absent generated file yields its own named complaint."""
        for name in present:
            (tmp_path / name).write_text("", encoding="utf-8")

        result = _check_table(
            tmp_path, _profile(schema_version=1, domain="learn_member")
        )

        assert result.passed is False
        assert result.details == [
            f"Missing generated configuration file: {name}" for name in missing
        ]

    def test_a_directory_does_not_satisfy_a_config_file(self, tmp_path: Path) -> None:
        """The check requires files: a same-named directory is still missing."""
        (tmp_path / "study.toml").mkdir()
        (tmp_path / "training.toml").write_text("", encoding="utf-8")

        result = _check_table(
            tmp_path, _profile(schema_version=1, domain="learn_member")
        )

        assert result.passed is False
        assert result.details == ["Missing generated configuration file: study.toml"]


class TestAccumulatedProblems:
    """Every refusal is reported at once, in declaration order."""

    def test_all_problems_are_reported_together(self, tmp_path: Path) -> None:
        """A wholly broken profile lists domain, schema and both files."""
        result = _check_table(tmp_path, _profile(schema_version=9, domain=""))

        assert result.passed is False
        assert result.details == [
            "Missing or invalid domain in [tool.axm-init.learning]",
            "Unsupported schema_version in [tool.axm-init.learning]: expected 1, got 9",
            "Missing generated configuration file: study.toml",
            "Missing generated configuration file: training.toml",
        ]


class TestResultIdentity:
    """The result keys the report and the exclusion config off stable names."""

    @pytest.mark.parametrize(
        ("data", "fixture_name"),
        [
            pytest.param({"tool": {"axm-init": {}}}, "tmp_path", id="no_profile_pass"),
            pytest.param(
                {"tool": {"axm-init": {"learning": {}}}}, "tmp_path", id="refusal"
            ),
            pytest.param(
                {
                    "tool": {
                        "axm-init": {"learning": {"schema_version": 1, "domain": "d"}}
                    }
                },
                "generated_project",
                id="valid_pass",
            ),
        ],
    )
    def test_every_outcome_carries_the_same_name_and_category(
        self,
        request: pytest.FixtureRequest,
        data: dict[str, object],
        fixture_name: str,
    ) -> None:
        """Pass or fail, the result is keyed learning.profile / learning."""
        project: Path = request.getfixturevalue(fixture_name)

        result = _check_table(project, data)

        assert result.name == "learning.profile"
        assert result.category == "learning"

    def test_canonical_discovery_id_is_derived_from_the_function(self) -> None:
        """Discovery derives learning.learning_profile from module + name."""
        assert get_check_name(check_learning_profile) == "learning.learning_profile"


class TestOptInDiscovery:
    """The category is opt-in: default runs must not pick it up."""

    def test_module_is_marked_explicit_only(self) -> None:
        """The opt-in marker keeps `learning` out of the default inventory."""
        assert learning_module.__axm_explicit_only__ is True

    def test_learning_is_absent_from_the_default_registry(self) -> None:
        """A default check run never discovers the learning category."""
        from axm_init.core.checker import ALL_CHECKS

        assert "learning" not in ALL_CHECKS
        discovered = [get_check_name(fn) for fns in ALL_CHECKS.values() for fn in fns]
        assert "learning.learning_profile" not in discovered


class TestMissingPyproject:
    """The requires_toml wrapper fails loudly when there is nothing to read."""

    def test_absent_pyproject_fails_with_the_learning_fix(self, tmp_path: Path) -> None:
        """No pyproject.toml is a weighted failure, not a silent pass."""
        result = check_learning_profile(tmp_path)

        assert result.passed is False
        assert result.message == "pyproject.toml not found or unparsable"
        assert result.name == "learning.profile"
        assert result.category == "learning"
        assert result.weight == 2
        assert (
            result.fix
            == "Regenerate the learning profile to restore its configuration files."
        )

    def test_declared_profile_is_read_from_a_real_pyproject(
        self, generated_project: Path
    ) -> None:
        """End to end through the wrapper: the TOML on disk drives the verdict."""
        (generated_project / "pyproject.toml").write_text(
            '[project]\nname = "demo-ml"\n\n'
            "[tool.axm-init.learning]\n"
            "schema_version = 1\n"
            'domain = "learn_member"\n',
            encoding="utf-8",
        )

        result = check_learning_profile(generated_project)

        assert result.passed is True
        assert result.message == "Learning profile for learn_member is configured"
