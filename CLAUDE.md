# Consignes projet — Prompteur

## ⚠️ RÈGLE ABSOLUE — Navigateur : uniquement l'intégré local, JAMAIS un navigateur externe

Pour **tester ou prévisualiser** quoi que ce soit, utiliser **exclusivement le navigateur
intégré local** de l'outil : le volet de prévisualisation *in-app* (serveurs MCP
`Claude_Browser` / `Claude_Preview`). Ce volet reste **local à la machine en cours** et ne
peut jamais s'afficher ailleurs.

**Il est INTERDIT d'utiliser un navigateur externe / réel** — c'est-à-dire les outils
`mcp__claude-in-chrome__*` (et l'ancienne graphie `mcp__Claude_in_Chrome__*`), soit tout ce
qui pilote un **vrai Chrome, Firefox ou Edge** via une extension « navigateur connecté ».
Ne pas les charger, ne pas les appeler.

**Pourquoi.** Le compte Claude de ce poste est **partagé** entre plusieurs personnes.
L'outil « navigateur externe » se connecte au navigateur réel *rattaché au compte* : il peut
donc ouvrir un onglet **sur le PC de quelqu'un d'autre** (Chrome **comme Firefox**).
C'est déjà arrivé sur plusieurs projets de ce poste. Le navigateur intégré local n'a pas ce problème.

**Garde-fou technique.** Un blocage dur est en place dans `.claude/settings.local.json`
(`permissions.deny` sur `mcp__claude-in-chrome` et `mcp__Claude_in_Chrome`).
**Ne pas le retirer.**

> Règle simple : si un test nécessite un navigateur, c'est le **volet de prévisualisation
> intégré**, point. Jamais un vrai navigateur.

## Reprise du travail : la mémoire du projet

**Au début de chaque session**, lire `.claude/memoire/MEMORY.md`, puis
`.claude/memoire/reprise-nouveau-pc.md` (point d'entrée) et les autres fichiers utiles de ce
dossier : c'est la mémoire de travail du projet (état du boîtier, choix passés, consignes de
l'utilisateur, accès à distance). Si la mémoire automatique de Claude Code est vide (nouveau
PC), y recopier ces fichiers, puis tenir les deux à jour.

Ce dossier est **volontairement hors de git** (`.claude/` est ignoré : le dépôt est public).
Ne jamais le committer, et n'y écrire aucun secret (mot de passe, jeton, clé privée). S'il
manque, le demander à l'utilisateur : il voyage avec le dossier du projet, pas avec GitHub.
