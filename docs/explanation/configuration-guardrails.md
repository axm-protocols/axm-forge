# Diagnostics stricts et garde-fous de lecture

`axm-config doctor` et `ConfigDoctorTool` valident maintenant les sources de
configuration qu'ils inspectent, avant de rendre leur provenance. Une configuration
absente reste normale. Un TOML malformé (y compris encodage invalide), un fichier
illisible ou un répertoire de namespaces non énumérable provoque `ConfigError` ;
la CLI sort avec le code 1, l'outil retourne success=false, sans rapport partiel.
Ces erreurs de contenu/lecture donnent le rôle et un nom sûr (`config.toml`, `<namespace>.toml`),
jamais les valeurs, le contenu, un chemin absolu ou la chaîne du parseur/OSError.
Les exceptions de parsing/lecture sont supprimées du traceback rendu.

## Sources concernées

La configuration centrale du profil actif est toujours inspectée, même si des
variables d'environnement fournissent toutes les valeurs demandées. Un profil
dev ne diagnostique pas la configuration production ou celle d'un autre profil.
Le fallback explicite AXM_HOME est également inspecté pour découvrir ses clés.
Un ancien fichier de namespace est lu uniquement lorsque la sélection existante
le consulte : une section centrale non vide, ou un overlay d'exécution canonique,
masque son ancien fichier. Un TOML étranger dont le nom n'est pas un namespace
reconnu reste hors périmètre. Doctor sans namespace découvre les namespaces du
profil actif ; une erreur d'énumération n'est jamais transformée en liste vide.
La découverte stricte utilise scandir explicitement, car Path.glob peut masquer
PermissionError dans Python 3.12.

`NamespaceStore(strict_reads=True)` offre ce comportement pour read, read_exact
et namespaces. `resolution_origin(..., strict=True)` vérifie la centrale même
si l'environnement gagne, et diagnostique les autres fichiers atteints par sa
résolution. Le défaut de ces APIs reste compatible : les lectures runtime
historiquement tolérantes le restent. Doctor choisit explicitement le mode strict
pour toutes ses lectures, sans remplacer de store global ni modifier le processus.
Il ne s'agit pas d'une validation des schémas métiers : les modèles consommateurs
restent responsables des types et contraintes de leurs namespaces.

## Tests d'architecture

Les tests unitaires normaux de chaque dépôt portent leurs propres garde-fous :

- Forge vérifie que getters, store, provenance, doctor et chemins de profil
  restent sans écriture, création, chmod, SQLite, réseau, thread ni processus,
  avec installation présente et absente.
- Nexus vérifie instanciation, découverte, résolution ID, manifeste et traces
  sans préparation de stockage ni exécution.
- Hub et Orison protègent leurs deux modules adaptateurs de chemins. Un petit
  contrôle AST suit les alias d'import et refuse leur propre parser/lecture de
  fichier, politique de profil/config et reconstruction de HOME. Les déclarations
  Path et les sélecteurs d'environnement propres aux consommateurs restent permis.
  Des snippets de régression (alias et imports qualifiés compris) prouvent que
  les règles détectent ces réintroductions. Les appels réels des getters sont
  aussi vérifiés sous garde dynamique, en production et dev.

Le contrôle est limité aux frontières concrètes, sans allowlist de dette globale,
ni dépendance à la présence des dépôts frères. Les writers explicites et init
restent autorisés : leurs fonctions ne sont pas soumises au test de lecture.
Les tests ne sont pas un sandbox contre du code hostile ou une preuve par analyse
complète de tous les flux de données (import dynamique, réflexion, etc.).

La petite fixture dynamique est volontairement locale dans quatre suites et le
scanner AST dans deux, afin de rester exécutable dans chaque dépôt autonome.
Toute évolution de cette frontière doit garder ces copies cohérentes ; une
bibliothèque de garde-fous ne sera justifiée que si leur maintenance le nécessite.

## Vérification dans la forêt de revue

Aucune dépendance ni lock n'est modifié. Le runner d'audit impose HOME/AXM_ROOT/XDG
temporaires, keyring nul et refuse les écritures canoniques et lancements réels.
Le venv partagé de revue doit recevoir PYTHONPATH vers les cinq src des nouveaux
worktrees, afin de ne pas importer les anciens editables :

```sh
BASE=/chemin/axm-guardrails-20261114
export PYTHONPATH="$BASE/workspace/axm-forge/packages/axm-config/src:$BASE/workspace/axm-nexus/packages/axm-lens/src:$BASE/workspace/axm-nexus/packages/axm-tribunal/src:$BASE/workspace/axm-hub/packages/axm-warden/src:$BASE/workspace/axm-orison/packages/axm-orison/src"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_PLUGINS=axm_config.pytest_plugin
# Les E2E existants appellent uv run : réutiliser le venv sans aucun sync.
export UV_NO_SYNC=1
export UV_PROJECT_ENVIRONMENT="$BASE/.venv"
export UV_PYTHON="$BASE/.venv/bin/python"
PY="$BASE/.venv/bin/python"
RUNNER="$BASE/audit/run_tests.py"
# Depuis axm-forge :
"$PY" "$RUNNER" -q -o addopts='' -p pytest_mock -p pytest_asyncio.plugin packages/axm-config/tests_axm_config
# Depuis axm-nexus, suites séparées pour isoler leurs registres de graphes :
"$PY" "$RUNNER" -q -o addopts='' -p pytest_mock -p pytest_asyncio.plugin packages/axm-lens/tests_axm_lens/unit
"$PY" "$RUNNER" -q -o addopts='' -p pytest_mock -p pytest_asyncio.plugin packages/axm-tribunal/tests_axm_tribunal/unit
# Depuis axm-hub :
"$PY" "$RUNNER" -q -o addopts='' -p pytest_mock -p pytest_asyncio.plugin packages/axm-warden/tests_axm_warden/unit/test_path_architecture.py packages/axm-warden/tests_axm_warden/unit/test_paths.py packages/axm-warden/tests_axm_warden/integration/test_default_socket__resolve_socket.py
# Depuis axm-orison :
"$PY" "$RUNNER" -q -o addopts='' -p pytest_mock -p pytest_asyncio.plugin packages/axm-orison/tests/unit/test_path_architecture.py packages/axm-orison/tests/unit/test_state_paths.py
```

Les paquets utilisant hatch-vcs nécessitent leurs fichiers de version générés
normalement par build ; aucun hash de lock n'est modifié pour les checkpoints.

## Résultats de revue

- Configuration : 368 tests passent ; avec les 16 diagnostics indépendants
  présents dans le même fichier d'audit, le run local compte 384 succès.
- Unités Tribunal puis Lens : 1878 tests passent, garde de lecture incluse.
- Hub ciblé local : 20 succès ; Orison ciblé local : 21 succès.
- Le contre-audit parent élargit Hub à 63 succès et Orison à 67, et compte
  23 contrats indépendants (diagnostics, UTF-8 et variantes des règles AST).
- Ruff, format, mypy des 14 modules axm-config et git diff --check passent.

Un run E2E simultané avait rencontré un venv créé par uv sous un HOME temporaire
expiré ; la relance avec UV_NO_SYNC et UV_PROJECT_ENVIRONMENT ci-dessus est verte.
Aucun changement produit ou de registre de graphes n'a été ajouté pour ces
particularités d'orchestration des tests. Les suites Nexus sont aussi valides en
un run ordonné Tribunal puis Lens ; les commandes séparées ci-dessus évitent de
partager leur registre pendant la vérification.
