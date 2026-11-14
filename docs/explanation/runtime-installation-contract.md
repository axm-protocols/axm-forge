# Contrat de configuration et de chemins runtime

`axm-config` possède la résolution des installations, profils et chemins. Les
consommateurs appellent `axm_home_path`, `axm_state_path`, `axm_data_path`, les
getters typés de `axm_config.paths` et `resolve_socket_path` dans
`axm_config.socket`. Ils ne lisent pas leur propre copie du TOML.

## Priorités et validation

Une valeur CLI explicite est traitée par le consommateur avant les getters.
Pour `resolve(namespace, key)` : variable `AXM_<NS>_<KEY>` (points de namespace
encodés `__`), alias explicitement déclarés, fichier du profil actif,
compatibilité `AXM_HOME/config.toml`, puis défaut fourni par le code. Un profil
non-production n'hérite pas automatiquement de la configuration production.
`AXM_HOME` reste un fallback de configuration et ne déplace pas l'installation.
La lecture du fallback AXM_HOME, précédemment propre aux chemins, est maintenant
partagée par le resolver ; elle s'applique donc aussi aux getters scalaires.

Les getters de chemins normalisent et refusent les valeurs configurées dans un
checkout Git ; les profils non-production imposent la containment de leurs
chemins configurés. Les getters booléens/entiers et `load` (modèle Pydantic du
consommateur) assurent la validation de type. Le store conserve sa compatibilité
historique : sa lecture bas niveau tolère un TOML central invalide comme absent,
mais ses mutations refusent un fichier invalide. Ce contrat ne constitue pas un
schéma global pour tous les namespaces : chaque consommateur valide son modèle.

La socket Warden conserve sa priorité historique particulière : CLI explicite,
`AXM_WARDEN_SOCKET`, puis `AXM_PATHS_WARDEN_SOCKET`/fichier/défaut. Avec AXM_HOME
et un profil non-production, son ancienne racine `AXM_HOME/profiles/<profil>`
est conservée et validée par axm-config ; aucune mutation d'environnement ne sert
à valider une valeur. Les callers conservent leurs chemins explicites tels quels
après validation, pour compatibilité.

`resolution_origin(namespace, key, env_aliases=...)` retourne uniquement
`{layer, present}`. Aucun secret, valeur, contenu de fichier ou environnement
n'est renvoyé. `axm-config doctor` utilise cette même décision pour les clés
qu'il découvre (store actif, fallback AXM_HOME et environnement), y compris les
namespaces enfants. Les alias non déclarés ne sont pas devinés : ils peuvent être
interrogés explicitement via `resolution_origin(..., env_aliases=...)`. La provenance des
sélecteurs CLI ou des substitutions de sandbox reste la responsabilité de la
surface qui les applique.

## Installation, profils et compatibilité

Avec `AXM_ROOT` absolu et hors checkout : configuration à la racine,
`state/` pour l'état des services, `data/` pour les données durables,
`profiles/<profil>/` pour l'isolation. Sans AXM_ROOT, les conventions historiques
`~/.axm` et `~/axm` restent en vigueur. Le sandbox pytest retire et restaure
AXM_ROOT pour isoler les tests.

`relocate_runtime_path` traduit seulement une référence d'accès historique,
jamais le contenu des manifestes, identités de jugement ou contrats capturés.
La traduction est idempotente pour les chemins canoniques ; les alias de casse
réellement identiques sur macOS sont détectés avant la traduction de `~/axm`.
Aucune migration en masse ni copie de données n'est effectuée.

Vault reste propriétaire des secrets. Ce changement ne transfère pas de secret
dans le store de configuration, et conserve `resolve_safe` et ses protections
hors checkout.

## Préparer et démarrer

`axm-config path` calcule et affiche le chemin sans créer le répertoire ni changer
ses permissions. `axm-config init` effectue explicitement la préparation 0700.
Aucune de ces commandes ne démarre un service. `axm_home()` reste l'API de
préparation pour les écritures explicites ; les lectures utilisent
`axm_home_path()`. Les modèles, Warden et Orison ne sont pas lancés par ces APIs.

Les chemins Orison usage, résumés, préférences et favoris sont également résolus
par `get_path` dans le namespace `orison`, avec les noms de variables existants.
Leurs overrides sont maintenant normalisés, refusés en checkout et confinés au
profil non-production. Une ancienne configuration dev qui pointait vers un
fichier extérieur doit choisir un chemin sous son profil ; ce durcissement est
volontaire pour empêcher les écritures croisées avec la production.
