#!/usr/bin/env bash
# =============================================================================
#  Rejoue localement TOUTES les vérifications de la CI, dans le même ordre.
# =============================================================================
#  À lancer depuis la racine du projet, avant de pousser :
#      bash scripts/verifier-ci.sh
#
#  Pourquoi ce script existe : la CI est restée rouge six commits d'affilée sans
#  que personne le voie. La cause était une alerte bandit de sévérité FAIBLE, et
#  les contrôles locaux étaient filtrés sur les sévérités « High » et « Medium ».
#  L'alerte n'apparaissait donc pas à l'écran — alors que bandit, lui, sort en
#  erreur dès la moindre alerte, quelle que soit sa sévérité.
#
#  La leçon tient en une ligne : ce qui compte, c'est le CODE DE SORTIE, pas ce
#  qu'on choisit d'afficher. Ce script ne filtre donc rien et s'arrête net au
#  premier échec.
# =============================================================================
set -e

etape() {
  echo
  echo "=============================================================="
  echo "  $1"
  echo "=============================================================="
}

etape "Ruff — lint"
python -m ruff check .

etape "Ruff — format"
python -m ruff format --check .

etape "Bandit — analyse de sécurité"
python -m bandit -c pyproject.toml -r .

etape "pip-audit — vulnérabilités des dépendances"
python -m pip_audit -r requirements.txt

etape "Pytest — tests"
python -m pytest -q

etape "Node — vérification de syntaxe"
node --check static/display.js
node --check static/remote.js
node --check static/commun.js
node --check static/plages.js

etape "Bancs d'essai (pédales, suivi, frappe)"
node tests/banc_pedales.js
node tests/banc_plages.js

etape "ESLint"
npx --no-install eslint static

etape "Shellcheck"
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -S error install/*.sh scripts/*.sh
else
  echo "shellcheck absent — installable par : pip install shellcheck-py"
  echo "/!\\ Cette étape N'A PAS été vérifiée localement."
fi

echo
echo "=============================================================="
echo "  Tout est vert."
echo "=============================================================="
