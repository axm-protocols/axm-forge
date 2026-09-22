# Scaffold provider foundation validation

Branch: `feat-domain-scaffolds` in the assigned Forge worktree.
Scope: public scaffold provider primitives, create-only rendering, optional
learning/experiment compatibility delegation, and explicit unscored rule execution.
No source checkout, domain-package worktree, archive, remote branch, or research
data was modified.

## New-behavior red/green evidence

Commands ran from the Forge worktree root using its isolated `.venv`.

1. `.venv/bin/python -m pytest packages/axm-init/tests_axm_init/unit/core/test_rule_runner.py -q --no-cov`
   failed collection because the new `axm_init.rules` API did not exist.
2. `.venv/bin/python -m pytest packages/axm-init/tests_axm_init/integration/test_scaffold_providers.py -q --no-cov`
   failed collection because the new `axm_init.scaffolding` API did not exist.
3. After implementing those APIs, the combined command below passed 11 tests:
   `.venv/bin/python -m pytest packages/axm-init/tests_axm_init/integration/test_scaffold_providers.py packages/axm-init/tests_axm_init/unit/core/test_rule_runner.py -q --no-cov`
4. Added legacy route assertions before delegation implementation: the provider
   `layers` call assertion failed for learning. The experiment fixture initially
   failed the paper-context guard; after fixing the fixture, the same route test
   failed because the provider was not called.
5. `.venv/bin/python -m pytest packages/axm-init/tests_axm_init/integration/test_scaffold_providers.py -q --no-cov -k legacy`
   failed both new metadata/check delegation assertions: the declared domain was
   `None`, and the check returned the old missing-TOML finding instead of the
   provider finding. Implementation made the combined suite pass 15 tests.
6. After agreeing the explicit legacy experiment hook with the coordinator,
   `.venv/bin/python -m pytest packages/axm-init/tests_axm_init/integration/test_scaffold_providers.py -q --no-cov -k experiment`
   failed two assertions: the legacy hook was not called and the modern provider
   was incorrectly called with the legacy route. Implementation made the combined
   provider/rule command pass **16 tests**.

The existing scaffold implementation and its tests predate this work; they are
regression evidence, not newly TDD-authored behavior. The new member delegation
branch was implemented alongside the root delegation and covered by the existing
member regression suite, rather than a separately observed member-specific red.

## Regression and static checks

```sh
.venv/bin/python -m pytest packages/axm-init/tests_axm_init/unit/core/test_templates.py packages/axm-init/tests_axm_init/unit/tools/test_scaffold.py packages/axm-init/tests_axm_init/integration/test_init_scaffold_tool__template_chain.py packages/axm-init/tests_axm_init/integration/test_init_scaffold_tool__register_learning_profile.py packages/axm-init/tests_axm_init/integration/test_init_scaffold_tool__template_type.py packages/axm-init/tests_axm_init/integration/test_scaffold_workspace.py packages/axm-init/tests_axm_init/integration/test_copier_adapter__template_layer.py -q --no-cov
```

Result: **44 passed, 1 deselected**.

```sh
.venv/bin/python -m pytest packages/axm-init/tests_axm_init/unit packages/axm-init/tests_axm_init/integration -q --no-cov
```

Initial broad collection exposed the historical learning check `__wrapped__`
attribute used by direct table-level consumers and a missing test dependency
`axm-doctor`. Restored that attribute and installed the local doctor package in
this worktree environment; final result: **1150 passed, 1 skipped, 19 deselected**.

```sh
.venv/bin/ruff check packages/axm-init/src/axm_init/scaffolding.py packages/axm-init/src/axm_init/rules.py packages/axm-init/src/axm_init/core/{templates,learning_profile}.py packages/axm-init/src/axm_init/checks/learning.py packages/axm-init/src/axm_init/tools/scaffold.py packages/axm-init/tests_axm_init/integration/test_scaffold_providers.py packages/axm-init/tests_axm_init/unit/core/test_rule_runner.py
.venv/bin/mypy --follow-imports=silent packages/axm-init/src/axm_init/scaffolding.py packages/axm-init/src/axm_init/rules.py
.venv/bin/mypy --follow-imports=silent packages/axm-init/src/axm_init/core/learning_profile.py packages/axm-init/src/axm_init/core/templates.py packages/axm-init/src/axm_init/checks/learning.py packages/axm-init/src/axm_init/tools/scaffold.py
```

All passed. Formatting checked with Ruff on the same changed Python files.

## Migration boundaries

- Domain implementations and modern template authority remain with Learning and
  Knowledge; this work has no hard imports of those packages.
- Installed providers are trusted code, and Copier tasks retain existing trust
  behavior. Create-only rendering rejects existing content but is not transactional
  and uses process-local locking, not interprocess locking.
- Legacy experiment creation uses only `legacy_experiment_layers`, never modern
  `layers`; missing hook preserves the historical bundled template.
- Learning wrappers use full-name optional hooks agreed with the Learning worker.
  Missing hooks and missing providers retain compatibility fallback.
- Rule execution preserves domain findings without project-score aggregation.
- Cross-worktree installed-provider integration and independent counter-audit are
  coordinated separately; this report does not claim their completion.

## Counter-audit and coordinator verification

The independent audit reproduced existing-project metadata replacement,
incomplete public Learning rendering, and generator layers reporting successful
empty output. Follow-up commits `dcd672038` (Forge) and `6d9e518` (Learning)
corrected these cases and normalized provider exceptions. They add an optional
provider finalizer and existing-target context without changing layers-only
providers or generic create-only safety.

After those commits, the coordinator rebuilt both wheels in temporary copies
and reran all 15 original independent counter-tests against the extracted wheels:
**15 passed**. No generated-project installation or training tasks ran.
The implementation worker also reported **1174 passed, 1 skipped** in Forge's
unit/integration suite and **182 passed** in Learning's suite.

The broader run's isolated CLI test lacked `axm` on its subprocess PATH. The
coordinator reran it with the worktree environment explicitly available:

```sh
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest packages/axm-init/tests_axm_init/e2e/test_scaffold__reserve.py::test_reserve_json_missing_identity_exits_nonzero -q -o addopts=''
```

Result: **1 passed**. This resolves the reported environment limitation for that
test; it is not a claim that every end-to-end test was rerun in this final pass.
