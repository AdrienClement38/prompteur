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

**Pourquoi.** Le compte Codex de ce poste est **partagé** entre plusieurs personnes.
L'outil « navigateur externe » se connecte au navigateur réel *rattaché au compte* : il peut
donc ouvrir un onglet **sur le PC de quelqu'un d'autre** (Chrome **comme Firefox**).
C'est déjà arrivé sur plusieurs projets de ce poste. Le navigateur intégré local n'a pas ce problème.

**Garde-fou technique.** Un blocage dur est en place dans `.claude/settings.local.json`
(`permissions.deny` sur `mcp__claude-in-chrome` et `mcp__Claude_in_Chrome`).
**Ne pas le retirer.** Ce fichier n'est pas suivi par git (`.gitignore` exclut `.claude/`) :
sur un poste neuf, il faut donc le recréer — le garde-fou ne voyage pas avec le dépôt.

> Règle simple : si un test nécessite un navigateur, c'est le **volet de prévisualisation
> intégré**, point. Jamais un vrai navigateur.
