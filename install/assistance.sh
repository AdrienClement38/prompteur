#!/usr/bin/env bash
# =============================================================================
#  Prompteur — assistance à distance (Raspberry Pi Connect)
# =============================================================================
#  Permet à la personne qui s'occupe du boîtier d'y accéder depuis n'importe où —
#  terminal ET écran, dans un simple navigateur — dès que le boîtier a internet.
#
#      assistance.sh on     active l'assistance
#      assistance.sh off    la coupe
#      assistance.sh etat   dit où on en est
#      assistance.sh installer   pose les deux icônes sur le bureau
#
#  POURQUOI UN SERVICE EXTÉRIEUR. Le boîtier et l'ordinateur de la personne qui
#  aide sont chacun derrière une box, et une box refuse les connexions qui
#  arrivent d'internet. Deux machines dans ce cas ne peuvent pas se joindre
#  directement : il faut que le boîtier appelle un relais, qui les met en
#  relation. Raspberry Pi Connect est ce relais, officiel, gratuit, déjà installé
#  sur Raspberry Pi OS avec bureau.
#
#  COUPÉ PAR DÉFAUT, ET ACTIVABLE SEULEMENT DEPUIS LE BOÎTIER. Assistance
#  activée, la personne qui aide voit l'écran — y compris le texte du
#  prompteur. C'est donc au journaliste de l'ouvrir, et de la refermer. Pour la
#  même raison, il n'existe volontairement AUCUN bouton dans la page web : tout
#  téléphone connecté au WiFi du boîtier pourrait l'actionner.
# =============================================================================
set -u

ACTION="${1:-etat}"

# L'action est vérifiée en premier : une faute de frappe doit donner l'aide,
# et non un message sur un logiciel manquant qui n'a rien à voir.
case "$ACTION" in
  on | off | etat | installer) ;;
  *)
    echo "Usage : $0 on | off | etat | installer"
    exit 2
    ;;
esac

# Raspberry Pi Connect fonctionne par utilisateur, dans sa session de bureau.
# Lancé en administrateur, il chercherait une session qui n'existe pas.
if [ "$(id -u)" -eq 0 ]; then
  echo "Ce script ne doit pas être lancé avec sudo."
  echo "Relancez simplement :  $0 $ACTION"
  exit 1
fi

# Lancé par une icône, le terminal se refermerait avant qu'on ait pu lire.
patienter() {
  if [ -t 0 ]; then
    echo
    read -r -p "Appuyez sur Entrée pour fermer cette fenêtre… " _
  fi
}

cadre() {
  echo
  echo "============================================================"
  for ligne in "$@"; do
    echo " $ligne"
  done
  echo "============================================================"
  echo
}

# Le format de « rpi-connect status » n'est pas décrit par la documentation
# officielle. Cette détection sert UNIQUEMENT à éviter de réafficher un lien
# inutile : aucun message ne conclut à un échec sur sa seule foi.
connecte() {
  rpi-connect status 2>/dev/null | grep -qiE "signed in[^a-z]*(yes|true)"
}

internet() {
  getent hosts connect.raspberrypi.com >/dev/null 2>&1
}

# Les icônes, posées AVANT la vérification de rpi-connect : on doit pouvoir les
# installer même si le paquet manque encore.
if [ "$ACTION" = "installer" ]; then
  SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  BUREAU="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
  [ -d "${BUREAU:-}" ] || BUREAU="$HOME/Bureau"
  [ -d "$BUREAU" ] || BUREAU="$HOME/Desktop"
  if [ ! -d "$BUREAU" ]; then
    echo "    (!) Dossier du bureau introuvable : icônes d'assistance non posées."
    exit 0
  fi
  for mode in on off; do
    if [ "$mode" = on ]; then
      libelle="Assistance à distance — activer"
    else
      libelle="Assistance à distance — couper"
    fi
    fichier="$BUREAU/prompteur-assistance-$mode.desktop"
    {
      echo "[Desktop Entry]"
      echo "Type=Application"
      echo "Name=$libelle"
      echo "Exec=$SCRIPT $mode"
      echo "Icon=preferences-desktop-remote-desktop"
      echo "Terminal=true"
    } > "$fichier"
    # Exécutable : sans cela le bureau demande confirmation à chaque double-clic.
    chmod 755 "$fichier"
  done
  echo "    Icônes « Assistance à distance » posées sur le bureau ($BUREAU)."
  exit 0
fi

if ! command -v rpi-connect >/dev/null 2>&1; then
  cadre "Raspberry Pi Connect n'est pas installé sur ce boîtier." \
    "" \
    "Avec le câble Ethernet branché, tapez :" \
    "   sudo apt install -y rpi-connect" \
    "puis redémarrez le boîtier et recommencez."
  patienter
  exit 1
fi

case "$ACTION" in
  on)
    if ! internet; then
      cadre "Le boîtier n'a pas internet." \
        "" \
        "Branchez le câble Ethernet sur la box, attendez" \
        "une minute, puis relancez l'assistance."
      patienter
      exit 1
    fi

    rpi-connect on >/dev/null 2>&1 || true
    # Terminal et écran : les deux, puisque c'est tout l'intérêt. Sans effet
    # s'ils étaient déjà autorisés.
    rpi-connect shell on >/dev/null 2>&1 || true
    rpi-connect vnc on >/dev/null 2>&1 || true

    if connecte; then
      cadre "ASSISTANCE ACTIVÉE" \
        "" \
        "La personne qui vous aide peut maintenant se connecter." \
        "Elle voit votre écran, y compris le texte du prompteur." \
        "" \
        "Quand elle a terminé, coupez l'assistance :" \
        "icône « Assistance à distance — couper » sur le bureau."
    else
      # Première fois seulement : il faut relier le boîtier au compte de la
      # personne qui aide. rpi-connect affiche lui-même le lien et attend
      # qu'il soit ouvert ; on ne réécrit pas sa sortie, pour ne pas dépendre
      # de sa formulation exacte.
      cadre "PREMIÈRE ACTIVATION" \
        "" \
        "Un lien va s'afficher juste en dessous." \
        "Envoyez-le à la personne qui vous aide (photo, SMS)." \
        "" \
        "Elle l'ouvre sur son ordinateur, et c'est terminé." \
        "Laissez cette fenêtre ouverte en attendant."
      rpi-connect signin
      echo
      echo "État du boîtier :"
      rpi-connect status 2>/dev/null || true
      cadre "Si la personne a validé le lien, c'est terminé :" \
        "elle voit le boîtier sur connect.raspberrypi.com." \
        "" \
        "Les prochaines fois, un double-clic sur l'icône suffira," \
        "sans lien à envoyer."
    fi
    patienter
    ;;

  off)
    # « rpi-connect off » n'est pas décrit par la documentation officielle ;
    # « vnc off » et « shell off » le sont. On fait les trois : même si la
    # première n'existait pas, écran et terminal sont fermés à coup sûr.
    rpi-connect vnc off >/dev/null 2>&1 || true
    rpi-connect shell off >/dev/null 2>&1 || true
    rpi-connect off >/dev/null 2>&1 || true
    cadre "ASSISTANCE COUPÉE" \
      "" \
      "Plus personne ne peut se connecter au boîtier à distance." \
      "Vous pouvez débrancher le câble Ethernet."
    patienter
    ;;

  etat)
    if ! internet; then
      echo "Internet : non (câble Ethernet débranché ?)"
    else
      echo "Internet : oui"
    fi
    if connecte; then
      echo "Boîtier relié à un compte d'assistance : oui"
    else
      echo "Boîtier relié à un compte d'assistance : non"
    fi
    echo
    rpi-connect status 2>/dev/null || true
    patienter
    ;;

esac
