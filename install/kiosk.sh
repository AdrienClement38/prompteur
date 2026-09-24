#!/usr/bin/env bash
# =============================================================================
#  Prompteur — ce que montrent les écrans du boîtier
# =============================================================================
#  SOURCE UNIQUE : ce script sert à la fois
#    * au démarrage automatique de la session (le boîtier affiche le prompteur
#      tout seul quand on le branche — c'est la garantie à ne jamais perdre) ;
#    * à l'icône de bureau « Le Prompteur » ;
#    * à la section « Vue du journaliste » et au bouton « Veille », via les
#      routes /api/kiosk/* et /api/veille du serveur.
#  Un seul comportement à maintenir, donc, au lieu de trois.
#
#  Usage :
#      kiosk.sh                   affiche la vue Journaliste sur le grand écran
#      kiosk.sh --vue settings    y affiche la vue Settings à la place
#                                 (sans effet si cette vue est déjà affichée ;
#                                 remplace l'autre vue sinon)
#      kiosk.sh --restart         ferme puis relance (même option --vue)
#      kiosk.sh --stop            ferme le navigateur : le bureau réapparaît
#      kiosk.sh --status          « running <vue> » ou « stopped » (code 0 / 1)
#      kiosk.sh --veille          éteint les écrans (veille du système)
#      kiosk.sh --reveil          les rallume
#      kiosk.sh --menu            ouvre la vue Settings sur le PETIT écran
#      kiosk.sh --menu-stop       la ferme
# =============================================================================
set -u

PORT="${PROMPTEUR_PORT:-5000}"
# Chemins VOLONTAIREMENT indépendants de l'environnement : le prompteur est lancé
# par la session graphique (qui a XDG_RUNTIME_DIR et HOME) mais interrogé par le
# service systemd (qui ne les a pas forcément identiques). Un chemin dérivé de
# l'un ou de l'autre donnerait deux fichiers différents, et un état faux.
PIDFILE="/tmp/prompteur-kiosk-$(id -u).pid"
VUEFILE="/tmp/prompteur-kiosk-$(id -u).vue"
LOCKFILE="/tmp/prompteur-kiosk-$(id -u).lock"
# Fichier PID distinct pour le petit écran : les deux fenêtres vivent leur vie,
# fermer le grand écran ne doit pas faire disparaître celle du technicien.
MENUPID="/tmp/prompteur-menu-$(id -u).pid"

# --- État --------------------------------------------------------------------
kiosk_pid() {
  # Le PID est celui du script, écrit AVANT l'attente du serveur ; exec le
  # conserve, si bien qu'il désigne ensuite le navigateur lui-même.
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null)"
  case "$pid" in
    '' | *[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  echo "$pid"
}

kiosk_vue() {
  local vue
  vue="$(cat "$VUEFILE" 2>/dev/null)"
  case "$vue" in
    settings) echo settings ;;
    *) echo journaliste ;;
  esac
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
  rm -f "$PIDFILE" "$VUEFILE"
}

# --- Veille ------------------------------------------------------------------
# Session Wayland (labwc, wayfire) ou X11 ? Les guides font choisir X11, mais un
# boîtier resté en Wayland doit s'éteindre aussi.
session_wayland() {
  [ -n "${WAYLAND_DISPLAY:-}" ] && return 0
  pgrep -u "$(id -u)" -x labwc >/dev/null 2>&1 && return 0
  pgrep -u "$(id -u)" -x wayfire >/dev/null 2>&1 && return 0
  return 1
}

# $1 = off | on. Renvoie 0 si la commande a été acceptée par le système.
ecrans() {
  local etat="$1"
  if session_wayland; then
    # Le service systemd n'a ni XDG_RUNTIME_DIR ni WAYLAND_DISPLAY : on les
    # retrouve à partir de l'utilisateur.
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    if [ -z "${WAYLAND_DISPLAY:-}" ]; then
      for sock in "$XDG_RUNTIME_DIR"/wayland-[0-9]; do
        [ -S "$sock" ] && WAYLAND_DISPLAY="$(basename "$sock")" && break
      done
      export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
    fi
    command -v wlopm >/dev/null 2>&1 || return 1
    wlopm --"$etat" '*'
    return
  fi
  command -v xset >/dev/null 2>&1 || return 1
  if [ "$etat" = off ]; then
    # Plus de signal HDMI : le moniteur se met en veille de lui-même. Un contact
    # sur le petit écran ou une pédale le rallume aussitôt (le serveur graphique
    # réveille les écrans à la moindre action) ; la page affiche alors un fond
    # noir et le bouton « Rallumer ».
    xset +dpms && xset dpms force off
  else
    # Au réveil, on remet ce que le démarrage du prompteur avait posé : jamais de
    # mise en veille automatique en pleine prise.
    xset dpms force on
    xset -dpms
    xset s off
    xset s noblank
    xset s reset
  fi
}

# --- Petit écran (vue Settings pour le technicien) ---------------------------
# Position et taille de la fenêtre : le petit écran est à droite du grand dans
# le bureau étendu. On lit sa géométrie réelle avec xrandr plutôt que de la
# deviner ; à défaut, PROMPTEUR_MENU_POS (« 1920,0 ») et PROMPTEUR_MENU_TAILLE
# (« 800,480 ») permettent de l'imposer.
menu_geometry() {
  # Sortie connectée la plus à droite : c'est le second écran.
  # Sortie : « X Y LARGEUR HAUTEUR ».
  xrandr --query 2>/dev/null |
    sed -n 's/^[^ ]* connected[^0-9]*\([0-9]\+\)x\([0-9]\+\)+\([0-9]\+\)+\([0-9]\+\).*/\3 \4 \1 \2/p' |
    sort -rn | head -1
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

trouver_navigateur() {
  command -v chromium-browser || command -v chromium || true
}

# --- Sous-commandes ----------------------------------------------------------
ACTION=""
VUE="journaliste"
while [ $# -gt 0 ]; do
  case "$1" in
    --vue)
      case "${2:-}" in
        journaliste | settings) VUE="$2" ;;
        *)
          echo "Vue inconnue : ${2:-} (journaliste ou settings)" >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    --restart | --stop | --status | --veille | --reveil | --menu | --menu-stop)
      ACTION="$1"
      shift
      ;;
    *)
      echo "Usage : $(basename "$0") [--vue journaliste|settings] [--restart|--stop|--status|--veille|--reveil|--menu|--menu-stop]" >&2
      exit 2
      ;;
  esac
done

case "$ACTION" in
  --veille)
    ecrans off
    exit $?
    ;;
  --reveil)
    ecrans on
    exit $?
    ;;
  --menu-stop)
    stop_menu
    echo "Petit écran fermé."
    exit 0
    ;;
  --menu)
    if menu_pid >/dev/null; then
      echo "Petit écran déjà affiché."
      exit 0
    fi
    BROWSER="$(trouver_navigateur)"
    if [ -z "$BROWSER" ]; then
      echo "Prompteur: Chromium introuvable." >&2
      exit 1
    fi
    read -r GX GY GW GH <<<"$(menu_geometry)"
    POS="${PROMPTEUR_MENU_POS:-${GX:-0},${GY:-0}}"
    TAILLE="${PROMPTEUR_MENU_TAILLE:-${GW:-800},${GH:-480}}"
    echo $$ >"$MENUPID"
    exec "$BROWSER" \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --disable-features=Translate \
      --check-for-update-interval=31536000 \
      --window-position="${POS}" \
      --window-size="${TAILLE}" \
      --user-data-dir="/tmp/prompteur-menu-profil-$(id -u)" \
      --class=PrompteurMenu \
      --app="http://localhost:${PORT}/settings"
    ;;
  --status)
    if kiosk_pid >/dev/null; then
      echo "running $(kiosk_vue)"
      exit 0
    fi
    echo stopped
    exit 1
    ;;
  --stop)
    stop_kiosk
    echo "Prompteur fermé."
    exit 0
    ;;
esac

# --- Lancement (avec ou sans --restart) --------------------------------------
# Verrou : deux lancements simultanés (démarrage automatique inscrit à deux
# endroits, double appui sur un bouton) ouvriraient deux navigateurs l'un sur
# l'autre, dont un seul serait suivi. On vérifie ET on réserve la place sous le
# même verrou.
exec 9>"$LOCKFILE"
flock 9 2>/dev/null || true
if [ "$ACTION" = "--restart" ]; then
  stop_kiosk
elif kiosk_pid >/dev/null; then
  if [ "$(kiosk_vue)" = "$VUE" ]; then
    # Sans effet si la vue demandée est déjà affichée : c'est ce qui rend
    # l'icône de bureau inoffensive en cas de double-clic.
    echo "Vue $VUE déjà affichée."
    exit 0
  fi
  stop_kiosk # l'autre vue laisse la place
fi
# La place est réservée TOUT DE SUITE, avant l'attente du serveur : un second
# lancement arrivé pendant cette attente la trouve prise.
echo $$ >"$PIDFILE"
echo "$VUE" >"$VUEFILE"
flock -u 9 2>/dev/null || true
exec 9>&- # le navigateur n'a pas à garder le verrou

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
BROWSER="$(trouver_navigateur)"
if [ -z "$BROWSER" ]; then
  echo "Prompteur: Chromium introuvable (ni chromium-browser ni chromium). Installez le paquet chromium." >&2
  rm -f "$PIDFILE" "$VUEFILE"
  exit 1
fi

# exec remplace le shell en conservant le PID : le fichier désigne désormais le
# navigateur lui-même.
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
  --app="http://localhost:${PORT}/${VUE}"
