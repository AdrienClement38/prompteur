#!/usr/bin/env bash
# =============================================================================
#  Prompteur — vérification du boîtier, étape par étape
# =============================================================================
#  À lancer après chaque mise à jour, depuis la fenêtre noire du boîtier (celle du
#  bureau, pas en SSH : il faut l'écran) :
#      cd ~/prompteur && ./install/verifier-boitier.sh
#  sudo est demandé une fois, pour l'essai des pédales « comme le vrai pédalier »
#  (clavier virtuel). Pendant l'essai, le texte du grand écran avance puis revient
#  au début : c'est normal.
#
#  Chaque étape affiche ✅ ou ❌, avec ce qu'il faut regarder. Ce qu'aucun
#  programme ne peut voir (l'image du petit écran, le stylet) est listé à la fin.
#  Rien n'est modifié sur le boîtier, sinon la position du texte (remise au début).
# =============================================================================
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"
PORT="${PROMPTEUR_PORT:-5000}"
URL="http://localhost:${PORT}"
[ -n "${DISPLAY:-}" ] || export DISPLAY=:0

REUSSIES=0
ECHECS=0
ok() { echo "✅ $1"; REUSSIES=$((REUSSIES + 1)); }
ko() { echo "❌ $1"; [ -z "${2:-}" ] || echo "   → $2"; ECHECS=$((ECHECS + 1)); }
titre() { echo; echo "── $1"; }

# Valeur d'un champ JSON (chemin « a.b ») lu sur l'entrée.
champ() {
  python3 -c 'import json, sys
d = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d = d.get(k) if isinstance(d, dict) else None
print("" if d is None else d)' "$1" 2>/dev/null
}

echo "Vérification du Prompteur — $(date '+%d/%m/%Y %H:%M')"
echo "Version : $(git -C "$ICI/.." log -1 --format='%h du %cd' --date=format:'%d/%m %H:%M' 2>/dev/null || echo inconnue)"

titre "1. Le logiciel du boîtier"
if VERSION="$(curl -s -m 5 "$URL/api/version")" && [ -n "$VERSION" ]; then
  ok "Le serveur répond."
else
  ko "Le serveur ne répond pas." "sudo systemctl restart prompteur, puis relancer cette vérification."
  echo
  echo "Arrêt : sans serveur, rien d'autre ne peut être vérifié."
  exit 1
fi
if [ "$(echo "$VERSION" | champ veille)" = "True" ]; then
  ko "Le système est en veille." "Touchez l'écran ou appuyez sur une pédale, puis relancez."
fi

titre "2. Le grand écran"
ETAT_GRAND="$("$ICI/kiosk.sh" --status 2>/dev/null)"
case "$ETAT_GRAND" in
  "running journaliste") ok "Il affiche la vue Journaliste." ;;
  running*) ko "Il affiche la vue ${ETAT_GRAND#running }, pas le prompteur." "En haut de Settings : « Écran journaliste » → Journaliste." ;;
  *) ko "Le prompteur n'est pas ouvert sur le grand écran." "Icône « Le Prompteur » du bureau, ou « Écran journaliste » → Journaliste." ;;
esac
SEQ1="$(curl -s -m 5 "$URL/api/scroll" | champ seq)"
sleep 3
SEQ2="$(curl -s -m 5 "$URL/api/scroll" | champ seq)"
if [ -n "$SEQ1" ] && [ -n "$SEQ2" ] && [ "$SEQ2" != "$SEQ1" ]; then
  ok "La vue Journaliste pilote le défilement (elle donne sa position)."
else
  ko "La vue Journaliste ne donne pas sa position." "Est-elle ouverte ? Affiche-t-elle « déjà ouverte ailleurs » ?"
fi

titre "3. Les pédales"
essai() {
  local moyen="$1" nom="$2" sortie code
  if [ "$moyen" = clavier ]; then
    sortie="$(sudo python3 "$ICI/essai_pedales.py" clavier "$PORT")"
  else
    sortie="$(python3 "$ICI/essai_pedales.py" relais "$PORT")"
  fi
  code=$?
  if [ "$code" -eq 0 ]; then
    ok "$nom : le texte avance, puis s'arrête (mode $(echo "$sortie" | champ mode))."
  elif [ "$code" -eq 2 ]; then
    ko "$nom : essai impossible." "$(echo "$sortie" | champ erreur)"
  else
    local a
    a="$(echo "$sortie" | champ avance)"
    if [ "$a" != "True" ]; then
      ko "$nom : le texte n'a PAS avancé." "Positions : $(echo "$sortie" | champ positions)"
    else
      ko "$nom : le texte a avancé mais ne s'est PAS arrêté." "Positions : $(echo "$sortie" | champ positions)"
    fi
  fi
}
echo "   (le texte du grand écran va avancer, puis revenir au début)"
essai clavier "Pédale, comme le vrai pédalier"
essai relais "Pédale transmise par le petit écran"

titre "4. Le petit écran"
ECRANS="$("$ICI/kiosk.sh" --ecrans 2>&1)"
PETIT="$(echo "$ECRANS" | sed -n 's/^Petit écran (la régie) : //p')"
if [ -z "$PETIT" ] && [ ! -f "$HOME/.config/prompteur/petit-ecran.conf" ]; then
  echo "   Pas de petit écran sur ce boîtier : étape sans objet."
else
  if [ -n "$PETIT" ]; then ok "Le bureau voit le petit écran ($PETIT)."; else ko "Le bureau ne voit pas le petit écran." "./install/petit-ecran.sh etat, et une photo."; fi
  if echo "$ECRANS" | grep -q "^  $PETIT [0-9]"; then
    ok "Il est allumé, à côté du grand écran."
  else
    ko "Il n'est pas allumé à côté du grand écran." "./install/kiosk.sh --menu, et lire le message."
  fi
  PRIME="$(xrandr --current --prop 2>/dev/null | awk -v s="$PETIT" '$1 == s {d = 1; next} /^[^ \t]/ {d = 0} d && /PRIME Synchronization:/ {print $3; exit}')"
  case "$PRIME" in
    0) ok "Son image est réglée pour se rafraîchir (PRIME Synchronization à 0)." ;;
    1) ko "Son image risque d'être figée (PRIME Synchronization à 1)." "Normalement remis à 0 tout seul en 30 s : relancez la vérification." ;;
    *) echo "   (réglage de rafraîchissement sans objet pour cet écran)" ;;
  esac
  if echo "$ECRANS" | grep -q "Vue Settings du petit écran : affichée"; then
    ok "La page Settings y est ouverte."
  else
    ko "La page Settings n'y est pas ouverte." "tail -15 /tmp/prompteur-menu-$(id -u).log, et une photo."
  fi
  TACTILE_ID="$(xinput list --short 2>/dev/null | grep -iE 'slave +pointer' | grep -iE 'touch|ads7846|ft5x06|goodix|ilitek' | sed -n 's/.*id=\([0-9]\+\).*/\1/p' | head -1)"
  if [ -z "$TACTILE_ID" ]; then
    ko "Aucune dalle tactile reconnue." "./install/petit-ecran.sh etat, et une photo."
  else
    MATRICE="$(xinput list-props "$TACTILE_ID" 2>/dev/null | sed -n 's/.*Coordinate Transformation Matrix ([0-9]*):[[:space:]]*//p')"
    case "$MATRICE" in
      "1.000000, 0.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000, 0.000000, 1.000000" | "")
        ko "Le tactile n'est pas calé sur le petit écran." "./install/kiosk.sh --caler-tactile" ;;
      *) ok "Le tactile est calé sur le petit écran (corrections : $(sed -n 's/^tactile=//p' "$HOME/.config/prompteur/petit-ecran.conf" 2>/dev/null | tail -1))." ;;
    esac
  fi
fi

echo
echo "══ Résultat : $REUSSIES vérification(s) réussie(s), $ECHECS en échec."
echo
echo "À vérifier à l'œil (aucun programme ne le voit) :"
echo "  • Le VRAI pédalier fait défiler le texte, et l'arrête."
echo "  • Après un appui sur le petit écran, le pédalier marche toujours."
echo "  • Sur le petit écran, l'horloge (en bas à droite) avance chaque seconde."
echo "  • Un appui au stylet fait un rond rouge SOUS la pointe, tout de suite."
[ "$ECHECS" -eq 0 ]
