# `framework=` — étendre axm-init et axm-audit à Node/Svelte

> Branche worktree : `feat/node-svelte-support`. Aucun changement sur `main`.
> Principe directeur : **on ne crée pas de nouveaux outils**. On ajoute une
> dimension `framework` (défaut `python`, nouvelles valeurs `node` et `svelte`,
> `svelte` héritant de `node`). On porte l'**intention** de chaque règle/check
> Python vers son équivalent d'écosystème Node, pas l'outil.

## 1. Invariant de non-régression

Tout l'existant Python doit continuer à fonctionner à l'identique :

- chaque règle audit et chaque check init garde `framework="python"` par défaut ;
- quand aucun `framework=` n'est passé, il est **auto-détecté** à partir des
  marqueurs du projet, et un projet Python est détecté comme `python` ;
- les signatures MCP/CLI existantes ne changent pas (ajout d'un paramètre
  optionnel `framework` uniquement).

## 2. Détection de framework (partagée)

`detect_framework(path) -> Framework` (enum `python | node | svelte`) :

| Marqueur trouvé | Résultat |
|---|---|
| `pyproject.toml` (et pas de `package.json` au même niveau) | `python` |
| `package.json` avec dép/devDep `svelte` **ou** `svelte.config.js` présent | `svelte` |
| `package.json` sans marqueur Svelte | `node` |
| rien de tout ça | `python` (défaut conservateur) |

Override explicite : le paramètre `framework=` passé à l'outil court-circuite la
détection. `svelte` hérite de `node` (un projet svelte fait tourner les règles
`node` **plus** les règles `svelte`-spécifiques).

## 3. axm-audit — point d'injection

- Aujourd'hui : `@register_rule(category)` remplit `_RULE_REGISTRY[category]`,
  et `get_rules_for_category(category)` instancie ces classes.
- Extension : `@register_rule(category, framework="python")` → le registry
  devient indexé `(category, framework)` ; `get_rules_for_category(category,
  framework=...)` ne renvoie que les règles du framework demandé (avec héritage
  node→svelte). `audit_project()` / `AuditTool.execute()` acceptent un
  `framework` optionnel, sinon `detect_framework(project_path)`.
- Les règles Python existantes ne changent pas : `framework` par défaut =
  `python` dans le décorateur.

## 4. axm-init — point d'injection

### Scaffold (templates)
- `TemplateType` reste {standalone, workspace, member} ; on ajoute une
  dimension `framework`. `get_template_path(template_type, framework)` choisit le
  bon dossier Copier (`templates/node-project`, `templates/svelte-project`, …).
- `InitScaffoldTool.execute()` accepte `framework=` (défaut python).

### init_check (gold standard)
- Aujourd'hui : `_discover_checks()` scanne les modules de `axm_init.checks` ;
  le nom de module = catégorie ; toutes les fns `check_*` publiques sont prises.
- Extension : checks rangés par framework (sous-package
  `axm_init.checks.node.*`, `axm_init.checks.svelte.*`, l'existant restant le jeu
  `python`). `CheckEngine(project_path, framework=...)` choisit le jeu de checks ;
  `framework` auto-détecté si non fourni.

## 5. Mapping d'intention (résumé — détail dans AUDIT_RULE_MAPPING.md)

| Catégorie | Intention conservée | Outil Python | Outil Node/Svelte |
|---|---|---|---|
| lint | style + bugs + simplifs | ruff | ESLint (typescript-eslint, eslint-plugin-svelte) |
| type | typage statique | mypy | tsc --noEmit (+ svelte-check) |
| complexity | cc<10 / cog<15 | ruff C901 + complexipy | ESLint `complexity` + sonarjs cognitive |
| security | secrets + vulnérabilités | bandit + regex | eslint-plugin-security + `npm audit` (+ regex réutilisée) |
| deps | pins + inutilisées + vulns | deptry + pip-audit | depcheck + `npm audit` |
| testing | suite verte + couverture | pytest + coverage | vitest run + c8/istanbul |
| test_quality | pyramide, dup, tautologie, naming | AST python | AST TS (mêmes invariants, fichiers `*.test.ts`) |
| architecture | pas de cycle, couplage, god class | imports python | madge / dependency-cruiser |
| structure | manifest complet + layout | pyproject.toml | package.json + tsconfig + svelte.config |
| practices | bare except, blocking io, docstrings, mirror | AST python | no empty catch, no sync fs en async, TSDoc, test-mirror |

## 6. Plan de prototypage (ordre)

1. `detect_framework` partagé (dans `axm-ingot` ou helper local par package).
2. axm-audit : registry `(category, framework)` + filtrage + 1 règle node POC
   (lint ESLint) prouvant la chaîne de bout en bout.
3. axm-init : `framework` dans `CheckEngine` + 1 jeu de checks node POC
   (`package.json` completeness) + 1 template `node-project` minimal.
4. Tests unit + e2e ; audit_test ; commit sur la branche worktree.

## 7. Résultats du POC (livré sur `feat/node-svelte-support`)

Mécanisme `framework=` câblé de bout en bout dans **axm-audit** et **axm-init**,
100% rétro-compatible (défaut `python`, auto-détection sinon).

**axm-audit**
- `core/framework.py` : `Framework` (python/node/svelte), `detect_framework`,
  `resolve_frameworks` (svelte → node+svelte).
- Registry `@register_rule(category, framework=…)` keyé `(category, framework)` ;
  `get_registry()` reste la vue python (back-compat), `get_registry_for(fw)` est
  le nouvel accès ; `auditor` filtre via `_merged_registry` + auto-détection.
- Règle POC `NodeLintRule` (catégorie `lint`, framework `node`) → ESLint JSON,
  même `rule_id=QUALITY_LINT`, même scoring `100 - issues*2`.
- **Prouvé e2e sur un vrai projet ESLint** : 3 issues réelles → score 94,
  `passed=False`. Faux-vert (npx non-install) attrapé et corrigé : un outil non
  installé localement = `ERROR` non-vert.

**axm-init**
- `core/framework.py` (miroir), `CheckEngine(framework=…)` + `CHECKS_BY_FRAMEWORK`.
- Jeu de checks `checks/node/package_json.py` (existence + métadonnées).
- Template Copier `templates/node-project` + `get_template_path(type, framework)` ;
  `InitScaffoldTool` accepte `framework=`.
- **Boucle prouvée** : `scaffold framework=node` → `init_check` auto-détecte node
  → score 100/A.

**Validation** : axm-audit 2010 tests verts (lint A 99.8 / type 100) ;
axm-init 707 tests verts (lint A 99.8 / type 100). 28 nouveaux tests ; 9 tests
existants adaptés à l'API framework-aware (aucune régression fonctionnelle).

## 8. Reste à faire (au-delà du POC)

Le mapping (AUDIT_RULE_MAPPING.md) liste 31 règles : 11 portables 1:1,
17 à adapter, 3 svelte-spécifiques, 0 à drop. Le POC en porte **1** (lint) pour
prouver la chaîne. Suite : porter les catégories par valeur décroissante
(type → tsc/svelte-check, complexity → ESLint+sonarjs, test_quality → ts-morph,
architecture → madge, …), factoriser `framework.py` dans `axm-ingot`, et exposer
`framework=` dans les signatures MCP/CLI des tools `audit` / `init_*`.
