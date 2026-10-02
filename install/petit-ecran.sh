#!/usr/bin/env bash
# =============================================================================
#  Prompteur — le petit écran tactile de 3,5 pouces, sur les broches du Raspberry
# =============================================================================
#  Deux familles d'écrans 3,5 pouces SPI (480 × 320, tactile résistif XPT2046),
#  qui ne se branchent PAS sur les mêmes broches et n'ont pas le même contrôleur :
#
#   ili9486 (d'usine) : la famille la plus répandue — Waveshare « 3.5inch RPi LCD
#       (A) » et « (C) », leurs copies (CUQI, cartes « 3.5 inch Display », cases
#       IPS/TN à cocher, « SPI 16MHz »…). Données sur GPIO 24, remise à zéro sur
#       GPIO 25. Pilote OFFICIEL du noyau : piscreen en mode drm (il comprend le
#       tactile).
#   st7796s : Waveshare « 3.5inch RPi LCD (G) » (contacts à ressort, IPS).
#       Données sur GPIO 22, remise à zéro sur GPIO 27. Pilote OFFICIEL
#       mipi-dbi-spi, avec la séquence d'allumage du ST7796S (install/st7796s.txt),
#       et ads7846 pour le tactile.
#
#  Rien n'est téléchargé, aucun pilote du vendeur n'est lancé, la ligne
#  vc4-kms-v3d n'est pas touchée : le grand écran HDMI continue de fonctionner.
#
#  Le petit écran a SON PROPRE serveur d'affichage (X « :1 », service
#  prompteur-petit-ecran-x), séparé du bureau du grand écran (« :0 ») qui ne le
#  touche plus. Partager un seul bureau entre les deux ne marche pas sur ce
#  matériel (mesuré sur le boîtier, voir PIEGES.md) : l'image n'arrivait au petit
#  écran que toutes les ~10 s. Et :1 n'a ni clavier ni pédalier : le petit écran
#  ne peut plus jamais prendre les pédales au grand. install/kiosk.sh y ouvre la
#  vue Settings, tout seul, à chaque démarrage.
#
#  Usage :
#      sudo ./install/petit-ecran.sh installer [--modele M] [--rotation R] [--tactile T]
#            M : ili9486 (d'usine) ou st7796s
#            R : normal (d'usine), left, right ou inverted
#            T : voir « tactile » ci-dessous ; sans option, les choix précédents
#                sont gardés
#      ./install/petit-ecran.sh tactile T        corrige le tactile TOUT DE SUITE,
#            sans redémarrer ni sudo. T : inverse-y (haut et bas inversés),
#            inverse-x (gauche et droite), echange (les deux axes croisés),
#            plusieurs à la fois (echange,inverse-x), ou normal
#      sudo ./install/petit-ecran.sh annuler     retire tout ce qui a été ajouté
#      ./install/petit-ecran.sh etat             dit ce qui est en place
#  Après installer ou annuler : sudo reboot
#
#  Retour arrière garanti : config.txt est sauvegardé avant toute modification
#  (config.txt.avant-petit-ecran), et nos lignes sont entre deux repères. Les
#  autres fichiers posés (serveur :1) sont tous à nous, et « annuler » les retire.
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
# Sans sudo, c'est simplement le compte courant et son $HOME.
UTILISATEUR="${SUDO_USER:-$(id -un)}"
MAISON="$HOME"
if [ -n "${SUDO_USER:-}" ]; then
  MAISON="$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6)"
  MAISON="${MAISON:-$HOME}"
fi
REGLAGE="$MAISON/.config/prompteur/petit-ecran.conf"

# Serveur d'affichage du petit écran (X :1). PROMPTEUR_RACINE ne sert qu'aux
# essais (tests/test_petit_ecran.py) ; sudo l'efface de toute façon.
RACINE="${PROMPTEUR_RACINE:-}"
XORG_GRAND="$RACINE/etc/X11/xorg.conf.d/60-prompteur-petit-ecran.conf"
DOSSIER_X="$RACINE/etc/prompteur"
XORG_PETIT="$DOSSIER_X/xorg-petit-ecran.conf"
XORG_VIDE="$DOSSIER_X/xorg-petit-ecran.d"
AVANT_X="$RACINE/usr/local/sbin/prompteur-petit-ecran-x"
SERVICE_X=prompteur-petit-ecran-x.service
UNITE_X="$RACINE/etc/systemd/system/$SERVICE_X"

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

# Valeur « cle=… » du réglage enregistré, si elle fait partie des valeurs permises.
reglage() {
  sed -n "s/^$1=\\($2\\)\$/\\1/p" "$REGLAGE" 2>/dev/null | tail -1
}

# « echange,inverse-x » -> forme rangée (echange, inverse-x, inverse-y), ou « » pour
# aucun. Les corrections sont appliquées par le bureau (kiosk.sh), avec des mots
# qui parlent de l'écran tel qu'on le voit. Code 2 si un mot est inconnu.
normaliser_tactile() {
  local choix c echange="" invx="" invy="" sortie=""
  [ -n "${1:-}" ] || { echo "Réglage du tactile manquant (normal, inverse-x, inverse-y, echange)" >&2; return 2; }
  IFS=',' read -r -a choix <<<"$1"
  for c in "${choix[@]}"; do
    case "$c" in
      inverse-x) invx=1 ;;
      inverse-y) invy=1 ;;
      echange) echange=1 ;;
      normal) ;;
      *) echo "Réglage du tactile inconnu : $c (normal, inverse-x, inverse-y ou echange)" >&2; return 2 ;;
    esac
  done
  [ -z "$echange" ] || sortie="$sortie,echange"
  [ -z "$invx" ] || sortie="$sortie,inverse-x"
  [ -z "$invy" ] || sortie="$sortie,inverse-y"
  echo "${sortie#,}"
}

ecrire_reglage() {
  mkdir -p "$(dirname "$REGLAGE")"
  printf 'modele=%s\nrotation=%s\ntactile=%s\n' "$1" "$2" "$3" >"$REGLAGE"
  chown -R "$UTILISATEUR:" "$(dirname "$REGLAGE")" 2>/dev/null || true
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

# Le serveur d'affichage du petit écran (X :1). Le bureau du grand écran (:0) ne
# prend plus ni la carte du petit écran ni sa dalle tactile ; :1 ne prend
# qu'elles. Tout est écrit d'un bloc à chaque installation (rien à fusionner).
installer_serveur_x() {
  case "$UTILISATEUR" in
    '' | *[!a-zA-Z0-9._-]*)
      echo "Compte inattendu : « $UTILISATEUR »." >&2
      exit 1
      ;;
  esac
  mkdir -p "$(dirname "$XORG_GRAND")" "$XORG_VIDE" "$(dirname "$AVANT_X")" "$(dirname "$UNITE_X")"

  cat >"$XORG_GRAND" <<'EOF'
# Prompteur (install/petit-ecran.sh) : le bureau du grand écran (:0) laisse le
# petit écran SPI et sa dalle tactile à leur propre serveur d'affichage (:1).
Section "ServerFlags"
  Option "AutoAddGPU" "false"
EndSection
Section "InputClass"
  Identifier "prompteur-tactile-du-petit-ecran"
  MatchProduct "ADS7846"
  Option "Ignore" "on"
EndSection
EOF

  # Modèle : @CARTE@ et @BUS@ sont remplis au lancement du serveur (les numéros
  # card2, event10… changent selon l'ordre de démarrage).
  cat >"$XORG_PETIT" <<'EOF'
# Prompteur (install/petit-ecran.sh) : serveur d'affichage du petit écran (X :1).
# Lu SEUL : :1 est lancé avec son propre dossier de réglages, pas celui du bureau.
Section "ServerFlags"
  Option "AutoAddGPU" "false"
  Option "AutoBindGPU" "false"
  Option "DontVTSwitch" "true"
  Option "BlankTime" "0"
  Option "StandbyTime" "0"
  Option "SuspendTime" "0"
  Option "OffTime" "0"
EndSection
# Un écran SPI annonce une fréquence factice (~0,01 Hz) : le navigateur caderait
# ses images dessus. Le mode à 60 Hz, de même taille, est pris d'office.
Section "Monitor"
  Identifier "petit-ecran"
  Modeline "480x320_60" 9.361 480 481 482 483 320 321 322 323
  Option "PreferredMode" "480x320_60"
EndSection
# Sans accélération : l'image est copiée par le processeur et envoyée à l'écran
# à chaque changement (c'est ce qui manquait quand le bureau partageait l'écran).
Section "Device"
  Identifier "petit-ecran"
  Driver "modesetting"
  BusID "@BUS@"
  Option "kmsdev" "@CARTE@"
  Option "AccelMethod" "none"
  Option "Monitor-Unknown19-1" "petit-ecran"
EndSection
Section "Screen"
  Identifier "petit-ecran"
  Device "petit-ecran"
  Monitor "petit-ecran"
  DefaultDepth 24
EndSection
# Entrées : la dalle tactile SEULEMENT. Clavier, pédalier, souris sont ignorés :
# ils restent au grand écran, toujours.
Section "InputClass"
  Identifier "prompteur-rien-que-le-tactile"
  NoMatchProduct "ADS7846"
  Option "Ignore" "on"
EndSection
Section "InputClass"
  Identifier "prompteur-tactile"
  MatchProduct "ADS7846"
  MatchDevicePath "/dev/input/event*"
  Driver "libinput"
EndSection
Section "ServerLayout"
  Identifier "petit-ecran"
  Screen "petit-ecran"
EndSection
EOF
  # Sans fichier, X signale une erreur (dossier « introuvable ») : un réglage vide.
  echo "# Volontairement vide : le petit écran ne lit que xorg-petit-ecran.conf." >"$XORG_VIDE/00-vide.conf"

  # Lancé par systemd juste avant le serveur, en root : attend le petit écran,
  # remplit le modèle, prépare le jeton d'accès (lisible par le compte du boîtier
  # seulement).
  sed -e "s|@UTILISATEUR@|$UTILISATEUR|g" -e "s|@MODELE@|$XORG_PETIT|g" >"$AVANT_X" <<'EOF'
#!/bin/sh
# Prompteur (install/petit-ecran.sh) : prépare le serveur d'affichage du petit
# écran (X :1), juste avant son lancement par systemd.
set -eu
ICI=/run/prompteur-petit-ecran
# La carte du petit écran : un écran sur le bus SPI. Son pilote peut n'arriver
# qu'après le bureau : on l'attend 30 s.
carte=""
i=0
while :; do
  for c in /dev/dri/by-path/*spi*-card; do
    if [ -e "$c" ]; then carte="$c"; break; fi
  done
  [ -z "$carte" ] || break
  i=$((i + 1))
  [ "$i" -le 30 ] || { echo "Petit écran introuvable (aucune carte graphique SPI)." >&2; exit 1; }
  sleep 1
done
bus="$(readlink -f "/sys/class/drm/$(basename "$(readlink -f "$carte")")/device")"
install -d -m 0755 "$ICI"
sed -e "s|@CARTE@|$carte|" -e "s|@BUS@|platform:$bus|" "@MODELE@" >"$ICI/xorg.conf"
A="$ICI/auth"
rm -f "$A"
(umask 077 && xauth -q -f "$A" add :1 . "$(mcookie)")
chown "@UTILISATEUR@:" "$A"
EOF
  chmod 755 "$AVANT_X"

  cat >"$UNITE_X" <<EOF
[Unit]
Description=Prompteur - affichage du petit écran (serveur X :1)
After=lightdm.service

[Service]
ExecStartPre=$AVANT_X
# vt7 -sharevts -novtswitch : il partage la console du bureau sans jamais la lui
# prendre (le grand écran reste affiché). -noreset : il ne se réinitialise pas
# quand la page du petit écran se ferme.
ExecStart=/usr/lib/xorg/Xorg :1 vt7 -sharevts -novtswitch -noreset -nolisten tcp -config /run/prompteur-petit-ecran/xorg.conf -configdir $XORG_VIDE -auth /run/prompteur-petit-ecran/auth
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
  if [ -z "${PROMPTEUR_ESSAI:-}" ]; then
    systemctl daemon-reload
    systemctl enable "$SERVICE_X" >/dev/null 2>&1
  fi
}

retirer_serveur_x() {
  if [ -z "${PROMPTEUR_ESSAI:-}" ]; then
    systemctl disable --now "$SERVICE_X" >/dev/null 2>&1 || true
  fi
  rm -f "$XORG_GRAND" "$XORG_PETIT" "$XORG_VIDE/00-vide.conf" "$AVANT_X" "$UNITE_X"
  rmdir "$XORG_VIDE" "$DOSSIER_X" 2>/dev/null || true
  if [ -z "${PROMPTEUR_ESSAI:-}" ]; then
    systemctl daemon-reload
  fi
}

installer() {
  # Sans option, on garde ce qui avait été choisi à l'installation précédente :
  # relancer pour changer la rotation ne doit pas défaire le réglage du tactile.
  local modele rotation tactile
  modele="$(reglage modele 'ili9486\|st7796s')"
  modele="${modele:-ili9486}"
  rotation="$(reglage rotation 'normal\|left\|right\|inverted')"
  rotation="${rotation:-normal}"
  tactile="$(reglage tactile '[a-z,-]*')"
  while [ $# -gt 0 ]; do
    case "$1" in
      --modele)
        case "${2:-}" in
          ili9486 | st7796s) modele="$2" ;;
          *) echo "Modèle inconnu : ${2:-} (ili9486 ou st7796s)" >&2; exit 2 ;;
        esac
        shift 2
        ;;
      --rotation)
        case "${2:-}" in
          normal | left | right | inverted) rotation="$2" ;;
          *) echo "Rotation inconnue : ${2:-} (normal, left, right ou inverted)" >&2; exit 2 ;;
        esac
        shift 2
        ;;
      --tactile)
        tactile="$(normaliser_tactile "${2:-}")" || exit 2
        shift 2
        ;;
      *) usage ;;
    esac
  done
  exiger_root installer
  [ -f "$CONFIG" ] || { echo "Fichier de démarrage introuvable ($CONFIG) : est-ce bien le boîtier ?" >&2; exit 1; }

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
  retirer_bloc
  # « [all] » d'abord : sans lui, nos lignes ne vaudraient que pour la dernière
  # section conditionnelle du fichier ([cm5], [pi4]…).
  if [ "$modele" = ili9486 ]; then
    # piscreen en mode drm = pilote ili9486 du noyau (« waveshare,rpi-lcd-35 »),
    # tactile compris. 16 MHz : la vitesse que ces cartes annoncent.
    cat >>"$CONFIG" <<EOF
$DEBUT
[all]
dtparam=spi=on
dtoverlay=piscreen,drm,speed=16000000
$FIN
EOF
  else
    [ -f "$SEQUENCE" ] || { echo "Séquence d'allumage introuvable : $SEQUENCE" >&2; exit 1; }
    command -v python3 >/dev/null 2>&1 || { echo "python3 introuvable." >&2; exit 1; }
    fabriquer_firmware
    cat >>"$CONFIG" <<EOF
$DEBUT
[all]
dtparam=spi=on
dtoverlay=mipi-dbi-spi,speed=48000000,write-only
dtparam=compatible=st7796s\\0panel-mipi-dbi-spi
dtparam=width=320,height=480,width-mm=49,height-mm=79
dtparam=reset-gpio=27,dc-gpio=22,backlight-gpio=18
dtoverlay=ads7846,speed=2000000,penirq=17,xmin=300,ymin=300,xmax=3900,ymax=3800,pmin=0,pmax=65535,xohms=400
extra_transpose_buffer=2
$FIN
EOF
  fi

  # Rotation et tactile se font par le bureau (kiosk.sh), pas au démarrage : ils
  # se changent sans toucher à config.txt.
  ecrire_reglage "$modele" "$rotation" "$tactile"
  installer_serveur_x

  echo "Petit écran préparé (modèle : $modele, rotation : $rotation, tactile : ${tactile:-normal})."
  echo "Sauvegarde de l'ancien fichier de démarrage : $SAUVEGARDE"
  echo "Redémarrez maintenant : sudo reboot"
}

# Corrige le tactile tout de suite : le réglage est gardé pour les démarrages
# suivants, et appliqué à l'instant par le bureau. Ni sudo, ni redémarrage.
tactile() {
  local t modele rotation
  t="$(normaliser_tactile "${1:-}")" || exit 2
  modele="$(reglage modele 'ili9486\|st7796s')"
  rotation="$(reglage rotation 'normal\|left\|right\|inverted')"
  ecrire_reglage "${modele:-ili9486}" "${rotation:-normal}" "$t"
  if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    "$ICI/kiosk.sh" --caler-tactile
  else
    echo "Réglage du tactile enregistré (${t:-normal}) : il s'appliquera au prochain démarrage."
  fi
}

annuler() {
  exiger_root annuler
  retirer_bloc
  retirer_serveur_x
  rm -f "$REGLAGE"
  echo "Petit écran retiré (lignes de $CONFIG, serveur d'affichage). Redémarrez : sudo reboot"
}

etat() {
  if grep -qF "$DEBUT" "$CONFIG" 2>/dev/null; then
    echo "Fichier de démarrage : lignes du petit écran EN PLACE :"
    sed -n "\\|^$DEBUT\$|,\\|^$FIN\$|p" "$CONFIG" | sed '1d;$d;s/^/    /'
  else
    echo "Fichier de démarrage : lignes du petit écran ABSENTES (sudo $0 installer)."
  fi
  if [ -f "$REGLAGE" ]; then echo "Réglage : $(tr '\n' ' ' <"$REGLAGE")"; fi
  # Toute carte graphique qui n'est pas celle du Raspberry (vc4, v3d) est celle
  # du petit écran.
  local pilote="" carte nom
  for carte in /sys/class/drm/card[0-9]; do
    [ -e "$carte/device/driver" ] || continue
    nom="$(basename "$(readlink -f "$carte/device/driver")")"
    case "$nom" in
      vc4* | v3d*) ;;
      *) pilote="$nom ($(basename "$carte"))" ;;
    esac
  done
  if [ -n "$pilote" ]; then
    echo "Pilote de l'écran : chargé, $pilote."
  else
    echo "Pilote de l'écran : NON chargé (redémarré depuis l'installation ?)."
  fi
  if grep -q "ADS7846" /proc/bus/input/devices 2>/dev/null; then
    echo "Tactile : reconnu (ADS7846)."
  else
    echo "Tactile : NON reconnu."
  fi
  if [ -f "$UNITE_X" ]; then
    echo "Affichage propre du petit écran (X :1) : $(systemctl is-active "$SERVICE_X" 2>/dev/null || true)."
  else
    echo "Affichage propre du petit écran (X :1) : non installé (sudo $0 installer)."
  fi
  echo "Écrans vus par le bureau :"
  "$ICI/kiosk.sh" --ecrans 2>&1 | sed 's/^/  /'
}

case "${1:-}" in
  installer) shift; installer "$@" ;;
  tactile) shift; tactile "$@" ;;
  annuler) annuler ;;
  etat) etat ;;
  *) usage ;;
esac
