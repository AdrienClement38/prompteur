#!/usr/bin/env bash
# =============================================================================
#  Prompteur — ce que montrent les écrans du boîtier
# =============================================================================
#  SOURCE UNIQUE : ce script sert à la fois
#    * au démarrage automatique de la session (le boîtier affiche le prompteur
#      tout seul quand on le branche — c'est la garantie à ne jamais perdre) ;
#    * à l'icône de bureau « Le Prompteur » ;
#    * aux boutons « Écran journaliste » et « Veille » de l'en-tête, via les
#      routes /api/kiosk/* et /api/veille du serveur ;
#    * au petit écran de la régie (le 7 pouces) : s'il est branché, il affiche
#      la vue Settings tout seul, sans passer par le WiFi.
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
#      kiosk.sh --menu            ouvre la vue Settings sur le PETIT écran (fait
#                                 d'office à chaque lancement du prompteur quand
#                                 deux écrans sont branchés)
#      kiosk.sh --menu-stop       la ferme
#      kiosk.sh --ecrans          dit quels écrans sont vus, lequel est le grand,
#                                 lequel le petit, et quelle dalle tactile
#      kiosk.sh --reprendre       rouvre la vue qu'un redémarrage du serveur a
#                                 fermée (appelé par le serveur à son démarrage)
#      kiosk.sh --miroir MODE     retourne tout le grand écran : normal, x
#                                 (gauche-droite), y (haut-bas) ou xy
#
#  Le miroir de la vitre : la vue Journaliste se retourne elle-même (c'est fluide
#  et éprouvé), le grand écran reste donc « normal » pendant qu'elle est affichée.
#  Pour la vue Settings et le bureau, c'est l'écran ENTIER qui est retourné,
#  pointeur de la souris compris, selon PROMPTEUR_MIROIR (donné par le serveur).
#
#  Utilisable aussi depuis une session SSH : l'écran du boîtier est désigné
#  d'office, et le navigateur est détaché de la session, pour ne pas se fermer
#  quand on se déconnecte.
# =============================================================================
set -u
ARGS=("$@")

# Lancé depuis SSH, aucun écran n'est désigné : celui du boîtier est « :0 ».
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  export DISPLAY=:0
  if [ -z "${XAUTHORITY:-}" ] && [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
  fi
fi

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
MENULOCK="/tmp/prompteur-menu-$(id -u).lock"

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

# --- Les deux écrans : le grand (la vitre) et le petit (la régie) --------------
# Sorties branchées ET allumées, une par ligne :
#   « NOM X Y LARGEUR HAUTEUR SURFACE_MM2 » (surface 0 si l'écran ne la dit pas).
sorties() {
  xrandr --query 2>/dev/null | awk '
    $2 == "connected" {
      geo = ""
      for (i = 3; i <= NF; i++) if ($i ~ /^[0-9]+x[0-9]+[+][0-9]+[+][0-9]+$/) { geo = $i; break }
      if (geo == "") next
      split(geo, g, /[x+]/)
      mm = 0
      if (match($0, /[0-9]+mm x [0-9]+mm/)) {
        split(substr($0, RSTART, RLENGTH), d, /mm x |mm/)
        mm = d[1] * d[2]
      }
      print $1, g[3], g[4], g[1], g[2], mm
    }'
}

# Toutes les sorties branchées, allumées ou non : un écran branché mais laissé
# éteint par le système n'a pas encore de position.
sorties_branchees() {
  xrandr --query 2>/dev/null | awk '$2 == "connected" { print $1 }'
}

# Le grand écran (celui qu'on lit) : la prise HDMI 0, la plus proche de
# l'alimentation — c'est celle que prescrivent toutes les procédures, et deux
# écrans de 7 pouces ne se distinguent pas autrement. À défaut, l'écran qui a le
# plus de pixels, puis le premier de la liste. PROMPTEUR_ECRAN permet de l'imposer.
sortie_grand_ecran() {
  if [ -n "${PROMPTEUR_ECRAN:-}" ]; then
    echo "$PROMPTEUR_ECRAN"
    return
  fi
  sorties | awk '
    $1 ~ /^HDMI-(A-)?1$/ { hdmi0 = $1 }
    {
      px = $4 * $5
      if (!choix || px > bestpx || (px == bestpx && $6 > bestmm)) { choix = $1; bestpx = px; bestmm = $6 }
    }
    END { if (hdmi0) print hdmi0; else if (choix) print choix }'
}

# Le petit écran : une autre sortie branchée. PROMPTEUR_PETIT_ECRAN l'impose.
sortie_petit_ecran() {
  if [ -n "${PROMPTEUR_PETIT_ECRAN:-}" ]; then
    echo "$PROMPTEUR_PETIT_ECRAN"
    return
  fi
  local grand
  grand="$(sortie_grand_ecran)"
  sorties_branchees | grep -vxF "${grand:-/}" | head -1
}

# « X Y LARGEUR HAUTEUR » d'une sortie allumée ; rien sinon.
geometrie() {
  sorties | awk -v s="$1" '$1 == s { print $2, $3, $4, $5 }'
}

# Vrai si les deux sorties ($1, $2) sont allumées et ne se recouvrent pas.
cote_a_cote() {
  local gx gy gw gh px py pw ph
  read -r gx gy gw gh <<<"$(geometrie "$1")"
  read -r px py pw ph <<<"$(geometrie "$2")"
  { [ -n "${gx:-}" ] && [ -n "${px:-}" ]; } || return 1
  ! { [ "$px" -lt $((gx + gw)) ] && [ "$gx" -lt $((px + pw)) ] &&
    [ "$py" -lt $((gy + gh)) ] && [ "$gy" -lt $((py + ph)) ]; }
}

# Les deux écrans doivent être CÔTE À CÔTE : en recopie, le petit répète le
# prompteur au lieu d'afficher la vue Settings. S'ils se recouvrent (ou si le
# petit est branché mais éteint), le petit est placé à droite du grand.
# Renvoie 1 s'il n'y a pas de petit écran, ou s'il n'a pas pu être placé : dans
# ce cas on n'ouvre RIEN, la fenêtre risquerait de couvrir le prompteur.
disposer_ecrans() {
  command -v xrandr >/dev/null 2>&1 || return 1
  local grand petit
  grand="$(sortie_grand_ecran)"
  petit="$(sortie_petit_ecran)"
  { [ -n "$grand" ] && [ -n "$petit" ]; } || return 1
  cote_a_cote "$grand" "$petit" && return 0
  xrandr --output "$petit" --auto --right-of "$grand" 2>/dev/null
  for _ in $(seq 1 10); do
    cote_a_cote "$grand" "$petit" && return 0
    sleep 0.3
  done
  return 1
}

# La dalle tactile doit viser le PETIT écran : sans cela, un appui est réparti
# sur la largeur des deux écrans réunis, et le doigt tombe à côté.
MOTS_TACTILES='touch|ft5x06|goodix|ilitek|egalax|ads7846|usb2iic|ctp|qdtech|waveshare'
caler_tactile() {
  command -v xinput >/dev/null 2>&1 || return 0
  local petit id
  petit="$(sortie_petit_ecran)"
  [ -n "$petit" ] || return 0
  for id in $(xinput list --short 2>/dev/null | grep -iE 'slave +pointer' | grep -iE "$MOTS_TACTILES" |
    sed -n 's/.*id=\([0-9]\+\).*/\1/p'); do
    xinput map-to-output "$id" "$petit" 2>/dev/null || true
  done
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

# $1 = normal | x | y | xy. Renvoie 0 si l'écran a bien été retourné.
miroir_ecran() {
  local sortie
  case "${1:-}" in
    normal | x | y | xy) ;;
    *) return 2 ;;
  esac
  command -v xrandr >/dev/null 2>&1 || return 1
  sortie="$(sortie_grand_ecran)"
  [ -n "$sortie" ] || return 1
  xrandr --output "$sortie" --reflect "$1"
}

trouver_navigateur() {
  command -v chromium-browser || command -v chromium || true
}

# Au démarrage du boîtier, le serveur met quelques secondes à répondre.
attendre_serveur() {
  for _ in $(seq 1 60); do
    curl -s "http://localhost:${PORT}/api/state" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

# Depuis SSH : on se détache de la session, sinon le navigateur se fermerait à
# la déconnexion. La copie détachée refait exactement la même demande.
detacher_si_ssh() {
  if [ -n "${SSH_CONNECTION:-}" ] && [ -z "${PROMPTEUR_DETACHE:-}" ] && command -v setsid >/dev/null 2>&1; then
    PROMPTEUR_DETACHE=1 setsid -f /bin/bash "$0" ${ARGS[@]+"${ARGS[@]}"} </dev/null >/dev/null 2>&1
    echo "$1"
    exit 0
  fi
}

# --- Sous-commandes ----------------------------------------------------------
ACTION=""
VUE="journaliste"
MIROIR_DEMANDE=""
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
    --restart | --stop | --status | --veille | --reveil | --menu | --menu-stop | --reprendre | --ecrans)
      ACTION="$1"
      shift
      ;;
    --miroir)
      ACTION="$1"
      MIROIR_DEMANDE="${2:-}"
      shift 2 || shift
      ;;
    *)
      echo "Usage : $(basename "$0") [--vue journaliste|settings] [--restart|--stop|--status|--veille|--reveil|--menu|--menu-stop|--ecrans|--reprendre|--miroir MODE]" >&2
      exit 2
      ;;
  esac
done

case "$ACTION" in
  --miroir)
    miroir_ecran "$MIROIR_DEMANDE"
    exit $?
    ;;
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
  --ecrans)
    echo "Écrans branchés et allumés (nom, x, y, largeur, hauteur, surface en mm²) :"
    sorties | sed 's/^/  /'
    echo "Grand écran (la vitre) : $(sortie_grand_ecran)"
    echo "Petit écran (la régie) : $(sortie_petit_ecran)"
    if command -v xinput >/dev/null 2>&1; then
      echo "Dalles tactiles reconnues :"
      xinput list --short 2>/dev/null | grep -iE 'slave +pointer' | grep -iE "$MOTS_TACTILES" | sed 's/^/  /'
    else
      echo "xinput absent : le tactile ne peut pas être calé sur le petit écran."
    fi
    if PID_MENU="$(menu_pid)"; then
      echo "Vue Settings du petit écran : affichée (PID $PID_MENU)."
    else
      echo "Vue Settings du petit écran : non affichée."
    fi
    exit 0
    ;;
  --menu)
    detacher_si_ssh "Vue Settings demandée sur le petit écran du boîtier."
    # Un seul petit écran à la fois, même si deux lancements se croisent : on
    # vérifie ET on réserve la place sous le même verrou.
    exec 8>"$MENULOCK"
    flock 8 2>/dev/null || true
    if menu_pid >/dev/null; then
      echo "Petit écran déjà affiché."
      exit 0
    fi
    if [ -z "$(sortie_petit_ecran)" ]; then
      echo "Un seul écran branché : pas de petit écran à remplir."
      exit 0
    fi
    if ! disposer_ecrans; then
      echo "Le petit écran n'a pas pu être placé à côté du grand : rien n'est ouvert (voir kiosk.sh --ecrans)." >&2
      exit 1
    fi
    BROWSER="$(trouver_navigateur)"
    if [ -z "$BROWSER" ]; then
      echo "Prompteur: Chromium introuvable." >&2
      exit 1
    fi
    echo $$ >"$MENUPID"
    flock -u 8 2>/dev/null || true
    exec 8>&-
    caler_tactile
    attendre_serveur || true
    # Position et taille réelles du petit écran ; PROMPTEUR_MENU_POS (« 1920,0 »)
    # et PROMPTEUR_MENU_TAILLE (« 1024,600 ») permettent de les imposer.
    read -r GX GY GW GH <<<"$(geometrie "$(sortie_petit_ecran)")"
    POS="${PROMPTEUR_MENU_POS:-${GX:-0},${GY:-0}}"
    TAILLE="${PROMPTEUR_MENU_TAILLE:-${GW:-800},${GH:-480}}"
    # Plein écran (--kiosk) sur le petit écran, avec son propre profil : c'est
    # un second navigateur, indépendant de celui du grand écran.
    exec "$BROWSER" \
      --password-store=basic \
      --kiosk \
      --no-first-run \
      --no-default-browser-check \
      --noerrdialogs \
      --disable-infobars \
      --disable-session-crashed-bubble \
      --disable-features=Translate \
      --check-for-update-interval=31536000 \
      --overscroll-history-navigation=0 \
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
  --reprendre)
    # Le navigateur a disparu SANS avoir été fermé volontairement : --stop
    # efface le fichier de vue, un arrêt brutal (redémarrage du service, dont il
    # était l'enfant) le laisse. On ne fait rien non plus tant que la session
    # graphique n'est pas prête : au démarrage du boîtier, c'est le lancement
    # automatique de la session qui s'en charge.
    if kiosk_pid >/dev/null || [ ! -f "$VUEFILE" ]; then
      exit 0
    fi
    if ! xset q >/dev/null 2>&1 && [ -z "${WAYLAND_DISPLAY:-}" ]; then
      exit 0
    fi
    VUE="$(kiosk_vue)"
    ;;
esac

detacher_si_ssh "Prompteur relancé sur l'écran du boîtier."

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

attendre_serveur || true

# --- Petit écran ---------------------------------------------------------------
# Un second écran branché (le 7 pouces de la régie) affiche la vue Settings,
# directement sur le boîtier : pas besoin du WiFi. Les deux écrans sont d'abord
# mis côte à côte, puis la fenêtre du petit est lancée à part : elle vit sa vie,
# fermer ou changer la vue du grand écran ne la touche pas.
if disposer_ecrans && ! menu_pid >/dev/null && command -v setsid >/dev/null 2>&1; then
  PROMPTEUR_DETACHE=1 setsid -f /bin/bash "$0" --menu </dev/null >/dev/null 2>&1 || true
fi

# --- Miroir de l'écran entier -------------------------------------------------
# Vue Journaliste : l'écran reste normal, elle se retourne elle-même. Vue
# Settings : c'est l'écran entier qui suit le réglage « Miroir » (et donc le
# pointeur de la souris, qui se déplace alors dans le bon sens à travers la vitre).
if [ "$VUE" = settings ]; then
  miroir_ecran "${PROMPTEUR_MIROIR:-normal}" 2>/dev/null || true
else
  miroir_ecran normal 2>/dev/null || true
fi

# --- Navigateur --------------------------------------------------------------
BROWSER="$(trouver_navigateur)"
if [ -z "$BROWSER" ]; then
  echo "Prompteur: Chromium introuvable (ni chromium-browser ni chromium). Installez le paquet chromium." >&2
  rm -f "$PIDFILE" "$VUEFILE"
  exit 1
fi

# exec remplace le shell en conservant le PID : le fichier désigne désormais le
# navigateur lui-même.
# --password-store=basic : sans lui, Chromium réclame le trousseau de mots de
# passe du système, verrouillé quand la session s'ouvre toute seule. Une fenêtre
# « Unlock Keyring » s'affichait à chaque allumage, par-dessus le prompteur — et
# prenait le clavier : les pédales ne répondaient plus tant qu'on ne l'avait pas
# fermée à la souris. Le kiosque n'enregistre aucun mot de passe : rien à perdre.
# --window-position : le plein écran se fait sur l'écran où s'ouvre la fenêtre ;
# avec deux écrans, c'est ce qui la met sur le GRAND.
read -r GX GY _ _ <<<"$(geometrie "$(sortie_grand_ecran)")"
exec "$BROWSER" \
  --password-store=basic \
  --kiosk \
  --start-fullscreen \
  --window-position="${GX:-0},${GY:-0}" \
  --no-first-run \
  --no-default-browser-check \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --class=PrompteurKiosque \
  --app="http://localhost:${PORT}/${VUE}"
