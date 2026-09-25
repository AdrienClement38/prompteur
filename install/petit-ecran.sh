#!/usr/bin/env bash
# =============================================================================
#  Prompteur — le petit écran tactile de 3,5 pouces, sur les broches du Raspberry
# =============================================================================
#  Écran visé : Waveshare « 3.5inch RPi LCD (G) » — sa carte porte l'inscription
#  « 3.5 inch Display-G » : contrôleur ST7796S, 320 × 480, tactile résistif
#  XPT2046, relié en SPI par les broches (pas en HDMI).
#
#  Méthode : celle que le fabricant recommande depuis Bookworm — le pilote
#  OFFICIEL mipi-dbi-spi du noyau Raspberry Pi, avec la séquence d'allumage du
#  ST7796S (install/st7796s.txt), et le pilote officiel ads7846 pour le tactile
#  (le XPT2046 en est une copie). Rien n'est téléchargé, aucun pilote du vendeur
#  n'est lancé, la ligne vc4-kms-v3d n'est pas touchée : le grand écran HDMI
#  continue de fonctionner. Ensuite, install/kiosk.sh relie ce petit écran au
#  bureau et y ouvre la vue Settings, tout seul, à chaque démarrage.
#
#  Usage :
#      sudo ./install/petit-ecran.sh installer [--rotation R] [--tactile T]
#            R : normal (d'usine, en hauteur), left, right ou inverted
#            T : inverse-x, inverse-y, echange (si le doigt tombe à l'envers)
#                ou normal ; sans option, les choix précédents sont gardés
#      sudo ./install/petit-ecran.sh annuler     retire tout ce qui a été ajouté
#      ./install/petit-ecran.sh etat             dit ce qui est en place
#  Après installer ou annuler : sudo reboot
#
#  Retour arrière garanti : config.txt est sauvegardé avant toute modification
#  (config.txt.avant-petit-ecran), et nos lignes sont entre deux repères.
# =============================================================================
set -eu

ICI="$(cd "$(dirname "$0")" && pwd)"
SEQUENCE="$ICI/st7796s.txt"
# Les trois variables PROMPTEUR_* ne servent qu'aux essais (tests/test_petit_ecran.py).
FIRMWARE="${PROMPTEUR_FIRMWARE:-/lib/firmware/st7796s.bin}"
CONFIG="${PROMPTEUR_BOOT_CONFIG:-/boot/firmware/config.txt}"
[ -f "$CONFIG" ] || CONFIG="/boot/config.txt"
SAUVEGARDE="$CONFIG.avant-petit-ecran"
DEBUT="# >>> Prompteur : petit écran 3,5 pouces (lignes gérées par install/petit-ecran.sh)"
FIN="# <<< Prompteur : petit écran 3,5 pouces"

# Le compte qui ouvre la session graphique (celui qui a tapé sudo) : c'est lui
# qui lance kiosk.sh, donc lui qui lit la rotation choisie.
UTILISATEUR="${SUDO_USER:-$(id -un)}"
MAISON="$(getent passwd "$UTILISATEUR" 2>/dev/null | cut -d: -f6)"
REGLAGE="${MAISON:-$HOME}/.config/prompteur/petit-ecran.conf"

usage() {
  sed -n 's/^#  \{0,1\}//p' "$0" | sed -n '/^Usage/,/^Après/p'
  exit 2
}

exiger_root() {
  if [ "$(id -u)" -ne 0 ] && [ -z "${PROMPTEUR_ESSAI:-}" ]; then
    echo "À lancer avec sudo : sudo $0 $*" >&2
    exit 1
  fi
}

retirer_bloc() {
  # Tout ce qui est entre nos deux repères, repères compris. Rien d'autre.
  if grep -qF "$DEBUT" "$CONFIG"; then
    sed -i "\\|^$DEBUT\$|,\\|^$FIN\$|d" "$CONFIG"
  fi
}

# install/st7796s.txt -> /lib/firmware/st7796s.bin (format de mipi-dbi-cmd :
# « MIPI DBI » + 7 zéros, version 1, puis commande, nombre de paramètres,
# paramètres ; un délai est la commande 0 avec un paramètre en ms).
fabriquer_firmware() {
  python3 - "$SEQUENCE" "$FIRMWARE" <<'PY'
import sys

source, cible = sys.argv[1], sys.argv[2]
octets = bytearray(b"MIPI DBI" + bytes(7) + bytes([1]))
for numero, ligne in enumerate(open(source, encoding="utf-8"), 1):
    ligne = ligne.split("#", 1)[0].strip()
    if not ligne:
        continue
    mots = ligne.split()
    if mots[0] == "delay" and len(mots) == 2:
        octets += bytes([0, 1, int(mots[1])])
    elif mots[0] == "command" and len(mots) >= 2:
        valeurs = [int(m, 16) for m in mots[1:]]
        octets += bytes([valeurs[0], len(valeurs) - 1] + valeurs[1:])
    else:
        sys.exit("ligne %d illisible : %s" % (numero, ligne))
with open(cible, "wb") as f:
    f.write(octets)
PY
}

installer() {
  # Sans option, on garde ce qui avait été choisi à l'installation précédente :
  # relancer pour changer la rotation ne doit pas défaire le réglage du tactile.
  local rotation tactile
  rotation="$(sed -n 's/^rotation=\(normal\|left\|right\|inverted\)$/\1/p' "$REGLAGE" 2>/dev/null | tail -1)"
  rotation="${rotation:-normal}"
  tactile="$(sed -n "\\|^$DEBUT\$|,\\|^$FIN\$|s/^dtoverlay=ads7846,.*\\(,invx\\|,invy\\|,swapxy\\)\$/\\1/p" "$CONFIG" 2>/dev/null | tail -1)"
  while [ $# -gt 0 ]; do
    case "$1" in
      --rotation)
        case "${2:-}" in
          normal | left | right | inverted) rotation="$2" ;;
          *) echo "Rotation inconnue : ${2:-} (normal, left, right ou inverted)" >&2; exit 2 ;;
        esac
        shift 2
        ;;
      --tactile)
        case "${2:-}" in
          inverse-x) tactile=",invx" ;;
          inverse-y) tactile=",invy" ;;
          echange) tactile=",swapxy" ;;
          normal) tactile="" ;;
          *) echo "Réglage du tactile inconnu : ${2:-} (normal, inverse-x, inverse-y ou echange)" >&2; exit 2 ;;
        esac
        shift 2
        ;;
      *) usage ;;
    esac
  done
  exiger_root installer
  [ -f "$CONFIG" ] || { echo "Fichier de démarrage introuvable ($CONFIG) : est-ce bien le boîtier ?" >&2; exit 1; }
  [ -f "$SEQUENCE" ] || { echo "Séquence d'allumage introuvable : $SEQUENCE" >&2; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 introuvable." >&2; exit 1; }

  # Le pilote du vendeur (LCD-show) désactive le pilote graphique : sur un Pi 5,
  # plus d'image du tout. S'il est passé par là, on s'arrête et on le dit.
  if grep -qE '^[[:space:]]*dtoverlay=(tft35a|waveshare35|mhs35|Waveshare35g)' "$CONFIG"; then
    echo "Des lignes d'un pilote de vendeur sont déjà dans $CONFIG." >&2
    echo "Rien n'a été changé. Restaurez d'abord la sauvegarde de config.txt (voir ECRAN-TACTILE.md)." >&2
    exit 1
  fi
  if ! grep -qE '^[[:space:]]*dtoverlay=vc4-kms-v3d' "$CONFIG"; then
    echo "⚠ La ligne dtoverlay=vc4-kms-v3d est absente de $CONFIG : le grand écran en dépend." >&2
    echo "  Rien n'a été changé. Voir ECRAN-TACTILE.md." >&2
    exit 1
  fi

  [ -f "$SAUVEGARDE" ] || cp "$CONFIG" "$SAUVEGARDE"
  fabriquer_firmware
  retirer_bloc
  # « [all] » d'abord : sans lui, nos lignes ne vaudraient que pour la dernière
  # section conditionnelle du fichier ([cm5], [pi4]…).
  cat >>"$CONFIG" <<EOF
$DEBUT
[all]
dtparam=spi=on
dtoverlay=mipi-dbi-spi,speed=48000000
dtparam=compatible=st7796s\\0panel-mipi-dbi-spi
dtparam=width=320,height=480,width-mm=49,height-mm=79
dtparam=reset-gpio=27,dc-gpio=22,backlight-gpio=18
dtoverlay=ads7846,speed=2000000,penirq=17,xmin=300,ymin=300,xmax=3900,ymax=3800,pmin=0,pmax=65535,xohms=400${tactile}
extra_transpose_buffer=2
$FIN
EOF

  # La rotation se fait par le bureau (kiosk.sh), pas au démarrage : elle se
  # change sans toucher à config.txt.
  mkdir -p "$(dirname "$REGLAGE")"
  echo "rotation=$rotation" >"$REGLAGE"
  chown -R "$UTILISATEUR:" "$(dirname "$REGLAGE")" 2>/dev/null || true

  echo "Petit écran préparé (rotation : $rotation)."
  echo "Sauvegarde de l'ancien fichier de démarrage : $SAUVEGARDE"
  echo "Redémarrez maintenant : sudo reboot"
}

annuler() {
  exiger_root annuler
  retirer_bloc
  rm -f "$REGLAGE"
  echo "Lignes du petit écran retirées de $CONFIG. Redémarrez : sudo reboot"
}

etat() {
  if grep -qF "$DEBUT" "$CONFIG" 2>/dev/null; then
    echo "Fichier de démarrage : lignes du petit écran EN PLACE."
  else
    echo "Fichier de démarrage : lignes du petit écran ABSENTES (sudo $0 installer)."
  fi
  if [ -f "$FIRMWARE" ]; then echo "Séquence d'allumage : présente ($FIRMWARE)."; else echo "Séquence d'allumage : ABSENTE."; fi
  if [ -f "$REGLAGE" ]; then echo "Réglage : $(cat "$REGLAGE")"; fi
  local pilote=""
  for carte in /sys/class/drm/card*; do
    [ -e "$carte/device/driver" ] || continue
    case "$(basename "$(readlink -f "$carte/device/driver")")" in
      panel-mipi-dbi*) pilote="$(basename "$carte")" ;;
    esac
  done
  if [ -n "$pilote" ]; then
    echo "Pilote de l'écran : chargé ($pilote)."
  else
    echo "Pilote de l'écran : NON chargé (redémarré depuis l'installation ?)."
  fi
  if grep -q "ADS7846" /proc/bus/input/devices 2>/dev/null; then
    echo "Tactile : reconnu (ADS7846)."
  else
    echo "Tactile : NON reconnu."
  fi
  echo "Écrans vus par le bureau :"
  "$ICI/kiosk.sh" --ecrans 2>&1 | sed 's/^/  /'
}

case "${1:-}" in
  installer) shift; installer "$@" ;;
  annuler) annuler ;;
  etat) etat ;;
  *) usage ;;
esac
