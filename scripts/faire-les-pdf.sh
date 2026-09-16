#!/usr/bin/env bash
# =============================================================================
#  Régénère les PDF des guides à partir des fichiers Markdown.
# =============================================================================
#  À lancer depuis la racine du dépôt, après TOUTE modification d'un guide :
#      bash scripts/faire-les-pdf.sh
#
#  Les PDF sont versionnés dans le dépôt parce que ce sont eux qu'on imprime et
#  qu'on envoie ; le convertisseur l'est aussi, pour que personne ne se retrouve
#  avec des PDF qu'il ne peut plus refabriquer.
# =============================================================================
set -e

cd "$(dirname "$0")/.."

# Nom du fichier source | nom du PDF | titre imprimé en pied de page
GUIDES="
MISE-EN-ROUTE.md|Mise-En-Route-Prompteur.pdf|Mise en route du Prompteur
MODE-EMPLOI.md|Mode-Emploi-Prompteur.pdf|Mode d'emploi du Prompteur
MISE-A-JOUR.md|Mise-A-Jour-Prompteur.pdf|Mettre le boitier a jour
ACCES-A-DISTANCE.md|Acces-A-Distance-Prompteur.pdf|Acces a distance au boitier
ASSISTANCE-A-DISTANCE.md|Assistance-A-Distance-Prompteur.pdf|Assistance a distance
PROCEDURE-INSTALLATION.md|Procedure-Installation-Prompteur.pdf|Procedure d'installation
SAUVEGARDE-ET-RESTAURATION.md|Sauvegarde-Restauration-Prompteur.pdf|Sauvegarde et restauration
ECRAN-TACTILE.md|Ecran-Tactile-Prompteur.pdf|Le petit ecran tactile
PIEGES.md|Pieges-Prompteur.pdf|Les pieges du Prompteur
README.md|Guide-Prompteur.pdf|Le Prompteur - guide complet
"

echo "$GUIDES" | while IFS='|' read -r src dst titre; do
  [ -n "$src" ] || continue
  if [ ! -f "$src" ]; then
    echo "    /!\\ $src introuvable, ignoré."
    continue
  fi
  python scripts/md2pdf.py "$src" "$dst" "$titre"
done

echo
echo "Terminé. Pensez à committer les PDF avec les .md : ils partent ensemble."
