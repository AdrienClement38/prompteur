#!/usr/bin/env bash
# =============================================================================
#  Prompteur — lancement / arrêt de l'écran du prompteur (mode kiosque)
# =============================================================================
#  SOURCE UNIQUE : ce script sert à la fois
#    * au démarrage automatique de la session (le boîtier affiche le prompteur
#      tout seul quand on le branche — c'est la garantie à ne jamais perdre) ;
#    * à l'icône de bureau « Le Prompteur » ;
#    * aux boutons de la télécommande, via /api/kiosk/* du serveur.
#  Un seul comportement à maintenir, donc, au lieu de trois.
#
#  Usage :
#      kiosk.sh              lance le prompteur (sans effet s'il tourne déjà)
#      kiosk.sh --restart    le ferme puis le relance
#      kiosk.sh --stop       le ferme et revient au bureau
#      kiosk.sh --status     affiche « running » ou « stopped » (code 0 / 1)
#      kiosk.sh --menu       ouvre le tableau de bord sur le SECOND écran
#      kiosk.sh --menu-stop  le ferme
# =============================================================================
set -u

PORT="${PROMPTEUR_PORT:-5000}"
URL="http://localhost:${PORT}/display"
# Chemin VOLONTAIREMENT indépendant de l'environnement : le prompteur est lancé
# par la session graphique (qui a XDG_RUNTIME_DIR et HOME) mais interrogé par le
# service systemd (qui ne les a pas forcément identiques). Un chemin dérivé de
# l'un ou de l'autre donnerait deux fichiers différents, et un état faux.
PIDFILE="/tmp/prompteur-kiosk-$(id -u).pid"
# Fichier PID distinct pour le tableau de bord : les deux fenêtres vivent leur
# vie, fermer le prompteur ne doit pas faire disparaître le menu du technicien.
MENUPID="/tmp/prompteur-menu-$(id -u).pid"

# --- État --------------------------------------------------------------------
kiosk_pid() {
  # Le PID est écrit avant l'exec, et exec conserve le PID : le fichier pointe
  # donc bien sur le processus du navigateur, pas sur un shell disparu.
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null)"
  case "$pid" in
    '' | *[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  echo "$pid"
}

stop_kiosk() {
  local pid
  if pid="$(kiosk_pid)"; then
    # TERM d'abord (Chromium ferme proprement sa session), KILL en dernier recours.
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
}

# --- Tableau de bord (second écran) ------------------------------------------
# Position de la fenêtre : le petit écran est à droite du grand dans le bureau
# étendu. On lit sa position réelle avec xrandr plutôt que de la deviner ; à
# défaut, PROMPTEUR_MENU_POS permet de l'imposer (« 1024,0 »).
menu_geometry() {
  if [ -n "${PROMPTEUR_MENU_POS:-}" ]; then
    echo "$PROMPTEUR_MENU_POS"
    return
  fi
  # Sortie connectée la plus à droite : c'est le second écran.
  xrandr --query 2>/dev/null |
    sed -n 's/^[^ ]* connected[^0-9]*\([0-9]\+\)x\([0-9]\+\)+\([0-9]\+\)+\([0-9]\+\).*/\3 \1 \4/p' |
    sort -rn | head -1 | awk '{print $1 "," $3}'
}

menu_pid() {
  [ -f "$MENUPID" ] || return 1
  local pid
  pid="$(cat "$MENUPID" 2>/dev/null)"
  case "$pid" in
    '' | *[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  echo "$pid"
}

stop_menu() {
  local pid
  if pid="$(menu_pid)"; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$MENUPID"
}

# --- Sous-commandes ----------------------------------------------------------
case "${1:-}" in
  --menu-stop)
    stop_menu
    echo "Tableau de bord ferme."
    exit 0
    ;;
  --menu)
    if menu_pid >/dev/null; then
      echo "Tableau de bord deja affiche."
      exit 0
    fi
    BROWSER="$(command -v chromium-browser || command -v chromium || true)"
    if [ -z "$BROWSER" ]; then
      echo "Prompteur: Chromium introuvable." >&2
      exit 1
    fi
    POS="$(menu_geometry)"
    POS="${POS:-0,0}"
    echo $$ >"$MENUPID"
    exec "$BROWSER" \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --disable-features=Translate \
      --check-for-update-interval=31536000 \
      --window-position="${POS}" \
      --window-size=480,320 \
      --user-data-dir="/tmp/prompteur-menu-profil-$(id -u)" \
      --class=PrompteurMenu \
      --app="http://localhost:${PORT}/menu"
    ;;
  --status)
    if kiosk_pid >/dev/null; then echo running; exit 0; else echo stopped; exit 1; fi
    ;;
  --stop)
    stop_kiosk
    echo "Prompteur fermé."
    exit 0
    ;;
  --restart)
    stop_kiosk
    ;;
  '')
    # Lancement simple : sans effet si le prompteur est déjà affiché. C'est ce
    # qui rend l'icône de bureau inoffensive en cas de double-clic.
    if kiosk_pid >/dev/null; then
      echo "Prompteur déjà affiché."
      exit 0
    fi
    ;;
  *)
    echo "Usage : $(basename "$0") [--restart|--stop|--status|--menu|--menu-stop]" >&2
    exit 2
    ;;
esac

# --- Confort d'affichage -----------------------------------------------------
# Empêche la mise en veille de l'écran / l'économiseur
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true
# Masque le curseur au repos (une seule instance)
pgrep -u "$(id -u)" -x unclutter >/dev/null 2>&1 || unclutter -idle 0.5 -root 2>/dev/null &

# --- Attente du serveur ------------------------------------------------------
# Au démarrage du boîtier, le service met quelques secondes à répondre.
for _ in $(seq 1 60); do
  if curl -s "http://localhost:${PORT}/api/state" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# --- Navigateur --------------------------------------------------------------
BROWSER="$(command -v chromium-browser || command -v chromium || true)"
if [ -z "$BROWSER" ]; then
  echo "Prompteur: Chromium introuvable (ni chromium-browser ni chromium). Installez le paquet chromium." >&2
  exit 1
fi

# On note le PID AVANT l'exec : exec remplace le shell en conservant le PID,
# si bien que le fichier désigne ensuite le navigateur lui-même.
echo $$ >"$PIDFILE"

exec "$BROWSER" \
  --kiosk \
  --start-fullscreen \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --class=PrompteurKiosque \
  --app="$URL"
