#!/usr/bin/env bash
# =============================================================================
#  Prompteur — vérification du boîtier, étape par étape
# =============================================================================
#  À lancer après chaque mise à jour, depuis la fenêtre noire du boîtier (celle du
#  bureau, pas en SSH : il faut l'écran) :
#      cd ~/prompteur && ./install/verifier-boitier.sh
#  sudo est demandé une fois, AU DÉBUT, pour l'essai des pédales « comme le vrai
#  pédalier » (clavier virtuel). Si le prompteur est fermé (Alt + F4 pour atteindre
#  cette fenêtre le ferme), la vérification l'ouvre elle-même le temps des essais,
#  puis le referme pour qu'on puisse lire le résultat. Pendant l'essai, le texte du
#  grand écran avance puis revient au début : c'est normal.
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

# La touche d'une pédale (« c », « ArrowDown »…) -> son code pour le noyau, d'après
# la disposition du clavier du boîtier : une lettre n'est pas au même endroit en
# AZERTY et en QWERTY. Vide si introuvable.
code_touche() {
  local sym="$1"
  case "$sym" in
    ArrowDown) sym=Down ;;
    ArrowUp) sym=Up ;;
    ArrowLeft) sym=Left ;;
    ArrowRight) sym=Right ;;
    " ") sym=space ;;
    Enter) sym=Return ;;
    PageDown) sym=Next ;;
    PageUp) sym=Prior ;;
  esac
  xmodmap -pke 2>/dev/null | awk -v k="$sym" '$4 == k {print $2 - 8; exit}'
}

echo "Vérification du Prompteur — $(date '+%d/%m/%Y %H:%M')"
echo "Le mot de passe est demandé maintenant, une seule fois (rien ne s'affiche en tapant) :"
sudo -v || echo "   (sans mot de passe, l'essai « comme le vrai pédalier » sera sauté)"
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
OUVERT_ICI=""
ETAT_GRAND="$("$ICI/kiosk.sh" --status 2>/dev/null)"
if [ "$ETAT_GRAND" = "running journaliste" ]; then
  ok "Le prompteur est ouvert sur le grand écran."
else
  echo "   Le prompteur est fermé (${ETAT_GRAND:-état inconnu}) : la vérification l'ouvre le temps des essais."
  setsid -f "$ICI/kiosk.sh" --vue journaliste </dev/null >/dev/null 2>&1
  OUVERT_ICI=1
  for _ in $(seq 1 30); do
    [ "$("$ICI/kiosk.sh" --status 2>/dev/null)" = "running journaliste" ] &&
      [ "$(curl -s -m 3 "$URL/api/presenter" | champ sur_le_boitier)" = "True" ] && break
    sleep 1
  done
  sleep 3 # le temps que la page soit dessinée et prenne la main
  if [ "$("$ICI/kiosk.sh" --status 2>/dev/null)" = "running journaliste" ]; then
    ok "Le prompteur s'ouvre sur le grand écran."
  else
    ko "Le prompteur ne s'ouvre pas sur le grand écran." "Ce qu'en dit son journal (à envoyer en photo) :"
    tail -n 8 "/tmp/prompteur-kiosk-$(id -u).log" 2>/dev/null | cut -c1-150 | sed 's/^/      /'
  fi
fi
PILOTE="$(curl -s -m 5 "$URL/api/presenter")"
if [ "$(echo "$PILOTE" | champ sur_le_boitier)" = "True" ]; then
  ok "C'est bien la vue du grand écran qui pilote le défilement."
elif [ "$(echo "$PILOTE" | champ taken)" = "True" ]; then
  ko "Une vue Journaliste ouverte sur un AUTRE appareil pilote le défilement ($(echo "$PILOTE" | champ appareil))." \
    "Fermez cette page sur cet appareil : tant qu'elle est ouverte, le grand écran ne pilote pas."
else
  ko "Aucune vue Journaliste ne pilote le défilement." "Le prompteur affiche-t-il « déjà ouverte ailleurs » ?"
fi

titre "3. Les pédales"
essai() {
  local moyen="$1" nom="$2" sortie code
  if [ "$moyen" = clavier ]; then
    if ! sudo -n true 2>/dev/null; then
      ko "$nom : essai sauté (pas de mot de passe)."
      return
    fi
    sortie="$(sudo -n python3 "$ICI/essai_pedales.py" clavier "$PORT" "$CODE_AVANT" "$CODE_CENTRALE")"
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
REGLAGES="$(curl -s -m 5 "$URL/api/state")"
TOUCHE_AVANT="$(echo "$REGLAGES" | champ settings.keyForward)"
TOUCHE_CENTRALE="$(echo "$REGLAGES" | champ settings.keyCenter)"
CODE_AVANT="$(code_touche "${TOUCHE_AVANT:-ArrowDown}")"
CODE_CENTRALE="$(code_touche "${TOUCHE_CENTRALE:-ArrowRight}")"
echo "   Touches des pédales : avant « ${TOUCHE_AVANT} », centrale « ${TOUCHE_CENTRALE} »."
echo "   (le texte du grand écran va avancer, puis revenir au début)"
essai clavier "Pédale, comme le vrai pédalier"
essai relais "Pédale transmise par le petit écran"

titre "4. Le petit écran"
ECRANS="$("$ICI/kiosk.sh" --ecrans 2>&1)"
PETIT="$(echo "$ECRANS" | sed -n 's/^Petit écran (la régie) : //p')"
if [ -f /etc/systemd/system/prompteur-petit-ecran-x.service ]; then
  # Le petit écran a son propre affichage (X :1, installé par petit-ecran.sh).
  if echo "$ECRANS" | grep -q "^Affichage propre du petit écran (:1) : actif"; then
    ok "Le petit écran a son propre affichage, et il répond."
  else
    ko "L'affichage du petit écran ne répond pas." "systemctl status prompteur-petit-ecran-x, et une photo."
  fi
  # L'image arrive-t-elle vraiment à l'écran ? On compte ce que le boîtier lui
  # envoie sur ses broches pendant 3 s : l'horloge de la page change chaque
  # seconde, il doit donc partir quelque chose (c'est ce qui manquait avant).
  SPI=""
  for d in /sys/bus/spi/devices/*; do
    [ -r "$d/statistics/bytes_tx" ] || continue
    [ "$(basename "$(readlink -f "$d/driver" 2>/dev/null)")" = ads7846 ] && continue
    SPI="$d/statistics/bytes_tx"
  done
  if [ -n "$SPI" ]; then
    AVANT="$(cat "$SPI")"
    sleep 3
    ENVOYE=$(($(cat "$SPI") - AVANT))
    if [ "$ENVOYE" -gt 0 ]; then
      ok "Le petit écran reçoit son image ($ENVOYE octets en 3 s)."
    else
      ko "Rien n'a été envoyé au petit écran en 3 s : son image est figée." "Une photo du petit écran, et ./install/kiosk.sh --ecrans"
    fi
  fi
  if echo "$ECRANS" | grep -q "Vue Settings du petit écran : affichée"; then
    ok "La page Settings y est ouverte."
  else
    ko "La page Settings n'y est pas ouverte." "tail -15 /tmp/prompteur-menu-$(id -u).log, et une photo."
  fi
  if echo "$ECRANS" | sed -n '/^Affichage propre du petit écran/,/^[^ ]/p' | grep -qi 'ads7846\|touch'; then
    ok "Sa dalle tactile est branchée sur lui (corrections : $(sed -n 's/^tactile=//p' "$HOME/.config/prompteur/petit-ecran.conf" 2>/dev/null | tail -1))."
  else
    ko "Sa dalle tactile n'est pas reconnue." "./install/petit-ecran.sh etat, et une photo."
  fi
elif [ -z "$PETIT" ] && [ ! -f "$HOME/.config/prompteur/petit-ecran.conf" ]; then
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
  FREQ="$(xrandr --current 2>/dev/null | awk -v s="$PETIT" '$1 == s {d = 1; next} /^[^ \t]/ {d = 0} d && /\*/ {for (i = 2; i <= NF; i++) if ($i ~ /\*/) {gsub(/[*+]/, "", $i); print $i; exit}}')"
  if [ -n "$FREQ" ] && awk -v f="$FREQ" 'BEGIN { exit !(f + 0 >= 5) }'; then
    ok "Sa fréquence d'image est normale (${FREQ} Hz)."
  elif [ -n "$FREQ" ]; then
    ko "Sa fréquence d'image est factice (${FREQ} Hz) : la page n'est redessinée que toutes les quelques secondes." \
      "Normalement corrigée au lancement de la page : ./install/kiosk.sh --menu-stop puis ./install/kiosk.sh --menu"
  fi
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

titre "5. La charge du boîtier"
# %CPU instantané (deuxième mesure de top, sur une seconde) des programmes les
# plus gourmands. Un serveur d'affichage (Xorg) saturé ralentit TOUT : le grand
# écran, le petit, et l'arrivée des pédales.
CHARGE="$(top -b -n 2 -d 1 2>/dev/null | awk '/^top -/ {n++} n == 2 && $1 ~ /^[0-9]+$/ {print int($9), $12}' | sort -rn | head -4)"
echo "$CHARGE" | sed 's/^/   /;s/ /% /'
XORG="$(echo "$CHARGE" | awk '$2 == "Xorg" {print $1; exit}')"
if [ -n "$XORG" ] && [ "$XORG" -ge 60 ]; then
  ko "Le serveur d'affichage est saturé (Xorg à ${XORG} %)." "Envoyez cette photo : c'est une piste pour la lenteur du petit écran."
else
  ok "Le serveur d'affichage n'est pas saturé (Xorg à ${XORG:-0} %)."
fi
FENETRES="$(xwininfo -root -tree 2>/dev/null | grep -iE 'prompteur(kiosque|menu)' | sed -n 's/.*("\([^"]*\)" "[^"]*").* \([0-9]\+x[0-9]\+[+-][0-9]\+[+-][0-9]\+\).*/\1 \2/p' | sort -u)"
[ -z "$FENETRES" ] || while read -r ligne; do echo "   fenêtre $ligne"; done <<<"$FENETRES"

if [ -n "$OUVERT_ICI" ]; then
  "$ICI/kiosk.sh" --stop >/dev/null 2>&1
  echo
  echo "Le prompteur a été refermé pour que vous puissiez lire ce résultat."
  echo "Rouvrez-le ensuite avec l'icône « Le Prompteur » du bureau."
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
