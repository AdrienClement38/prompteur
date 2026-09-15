#!/usr/bin/env bash
# =============================================================================
#  Prompteur — installation automatique sur Raspberry Pi (Raspberry Pi OS)
# =============================================================================
#  Ce script :
#    1. installe les dépendances (Flask, Chromium, unclutter)
#    2. crée un service qui lance le serveur au démarrage
#    3. configure le WiFi du boîtier (point d'accès "Prompteur", hors-ligne)
#    4. configure le démarrage automatique de l'écran en mode kiosque
#
#  À lancer sur le Raspberry Pi, depuis le dossier du projet :
#      chmod +x install/setup.sh
#      ./install/setup.sh
# =============================================================================
set -e

# --- Paramètres (modifiables) ------------------------------------------------
WIFI_SSID="Prompteur"
# Mot de passe UNIQUE par appareil s'il n'est pas fourni (ex: WIFI_PASS=monsecret ./setup.sh).
# On évite ainsi un secret par défaut partagé : le WPA2 est la seule barrière de l'API.
WIFI_PASS="${WIFI_PASS:-$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)}"
PORT="5000"
# Nom du boitier sur le reseau local : « prompteur.local » depuis un PC relie
# a la meme box. Modifiable : BOX_NAME=autre ./install/setup.sh
BOX_NAME="${BOX_NAME:-prompteur}"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(whoami)"
RUN_HOME="$HOME"

echo "==> Projet     : $PROJECT_DIR"
echo "==> Utilisateur: $RUN_USER"
echo

# --- 1. Dépendances ----------------------------------------------------------
echo "==> Installation des paquets (Flask, waitress, Chromium, antiword, unclutter, nftables)…"
sudo apt-get update
sudo apt-get install -y python3-flask python3-waitress antiword chromium-browser unclutter nftables || \
  sudo apt-get install -y python3-flask python3-waitress antiword chromium unclutter nftables
# Bibliothèques Python pour lire les PDF et RTF (pur Python, hors-ligne).
# antiword (ci-dessus) gère l'ancien format .doc.
sudo pip3 install --break-system-packages striprtf pypdf 2>/dev/null || \
  pip3 install --user striprtf pypdf || true

# --- 2. Service serveur (démarrage auto) -------------------------------------
echo "==> Création du service systemd 'prompteur'…"
sudo tee /etc/systemd/system/prompteur.service >/dev/null <<EOF
[Unit]
Description=Prompteur - serveur du boitier teleprompteur
After=network.target

[Service]
Type=simple
User=$RUN_USER
# Pas de guillemets ici : systemd ne les retire pas dans WorkingDirectory= et
# considererait le chemin comme non absolu ("bad unit file setting").
WorkingDirectory=$PROJECT_DIR
Environment=PROMPTEUR_PORT=$PORT
ExecStart=/usr/bin/python3 "$PROJECT_DIR/server.py"
Restart=always
RestartSec=2

# Durcissement. Sur Raspberry Pi OS, l'utilisateur cree a la premiere mise en
# route est generalement autorise a faire « sudo » sans mot de passe : sans ces
# lignes, tout code qui s'executerait dans le serveur pourrait donc devenir root.
# NoNewPrivileges ferme cette porte — le service n'a besoin d'aucun privilege, il
# ne fait que lire et ecrire dans son propre dossier et ouvrir un navigateur.
NoNewPrivileges=yes
# PAS de PrivateTmp : le service partage volontairement /tmp avec la session
# graphique, ou kiosk.sh ecrit son fichier PID. Un /tmp prive lui ferait perdre
# de vue le navigateur du kiosque, donc les boutons « afficher / fermer ».
ProtectSystem=full
ProtectControlGroups=yes
ProtectKernelModules=yes
ProtectKernelTunables=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable prompteur.service
# En cas d'echec, on affiche la vraie cause avant de sortir : sans cela, set -e
# coupe le script sur un message sibyllin et la suite de l'installation
# (WiFi, pare-feu, kiosque) n'est jamais executee.
if ! sudo systemctl restart prompteur.service; then
  echo
  echo "/!\\ Le service n'a pas demarre. Detail de l'erreur :"
  sudo systemctl status prompteur.service --no-pager --lines=20 || true
  sudo journalctl -u prompteur.service --no-pager --lines=20 || true
  exit 1
fi
echo "    Serveur actif sur le port $PORT."

# --- 3. Point d'accès WiFi (hors-ligne) --------------------------------------
echo "==> Configuration du WiFi du boîtier (point d'accès '$WIFI_SSID')…"
# NetworkManager (Raspberry Pi OS Bookworm et +)
if command -v nmcli >/dev/null 2>&1; then
  sudo nmcli connection delete Prompteur 2>/dev/null || true
  sudo nmcli connection add type wifi ifname wlan0 mode ap con-name Prompteur ssid "$WIFI_SSID"
  sudo nmcli connection modify Prompteur 802-11-wireless.band bg 802-11-wireless.channel 6
  sudo nmcli connection modify Prompteur wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$WIFI_PASS"
  sudo nmcli connection modify Prompteur ipv4.method shared ipv6.method disabled
  sudo nmcli connection modify Prompteur connection.autoconnect yes
  sudo nmcli connection up Prompteur || true
  echo "    Réseau '$WIFI_SSID' créé. Le boîtier sera joignable sur http://10.42.0.1:$PORT"
else
  echo "    /!\\ nmcli introuvable : configure le point d'accès manuellement (voir README)."
fi

# --- 3b. Pare-feu : port du prompteur limité au WiFi du boîtier ---------------
# L'API n'a pas d'authentification : on garantit qu'elle n'est joignable QUE depuis
# le point d'accès (wlan0) et en local, même si le Pi est un jour branché en Ethernet.
echo "==> Pare-feu : port $PORT restreint au point d'accès (wlan0) + local…"
if command -v nft >/dev/null 2>&1; then
  # Règles idempotentes (add+delete+define) dans un fichier rechargé à chaque boot.
  sudo tee /etc/nftables-prompteur.conf >/dev/null <<EOF
add table inet prompteur
delete table inet prompteur
table inet prompteur {
  chain input {
    type filter hook input priority 0; policy accept;
    iif "lo" accept
    iifname "wlan0" tcp dport $PORT accept
    tcp dport $PORT drop
  }
}
EOF
  sudo nft -f /etc/nftables-prompteur.conf || true
  # Service oneshot pour ré-appliquer les règles à chaque démarrage.
  sudo tee /etc/systemd/system/prompteur-firewall.service >/dev/null <<EOF
[Unit]
Description=Prompteur - pare-feu (port $PORT limite au wlan0)
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/nftables-prompteur.conf
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl enable prompteur-firewall.service 2>/dev/null || true
  echo "    Port $PORT accessible uniquement depuis le WiFi du boîtier."
else
  echo "    /!\\ nft introuvable : le port $PORT reste accessible sur toutes les interfaces."
fi

# --- 3c. Accès à distance (SSH) ----------------------------------------------
# Raspberry Pi OS livre SSH DÉSACTIVÉ. C'est la seule raison pour laquelle la
# première tentative de connexion au boîtier avait échoué : le pare-feu posé
# juste au-dessus ne ferme que le port du prompteur, jamais le port 22.
echo "==> Accès à distance : SSH + nom réseau du boîtier…"
sudo apt-get install -y openssh-server avahi-daemon >/dev/null 2>&1 || true
# Le service s'appelle « ssh » sur Debian, « sshd » ailleurs : on tente les deux.
sudo systemctl enable --now ssh >/dev/null 2>&1 ||
  sudo systemctl enable --now sshd >/dev/null 2>&1 || true
sudo systemctl enable --now avahi-daemon >/dev/null 2>&1 || true

# Nom stable sur le réseau. L'adresse distribuée par la box change d'un
# rebranchement à l'autre ; le nom, lui, ne change pas — et « prompteur.local »
# se résout depuis Windows, macOS et Linux sans rien installer.
ANCIEN_NOM="$(hostname)"
if [ "$ANCIEN_NOM" != "$BOX_NAME" ]; then
  sudo hostnamectl set-hostname "$BOX_NAME" >/dev/null 2>&1 || true
  # /etc/hosts doit suivre le changement. Sinon le nom de la machine ne se résout
  # plus localement, et CHAQUE « sudo » attend dix secondes avant de rendre la
  # main — une lenteur inexplicable qu'on met des heures à rattacher à sa cause.
  sudo sed -i "s/\b${ANCIEN_NOM}\b/${BOX_NAME}/g" /etc/hosts >/dev/null 2>&1 || true
  echo "    Nom du boîtier : $ANCIEN_NOM -> $BOX_NAME"
fi

if systemctl is-active --quiet ssh 2>/dev/null || systemctl is-active --quiet sshd 2>/dev/null; then
  echo "    SSH actif. Connexion : ssh $RUN_USER@$BOX_NAME.local"
else
  echo "    /!\\ SSH n'a pas démarré. Active-le à la main : sudo raspi-config"
  echo "        (Interface Options -> SSH -> Yes), puis relance ce script."
fi

# --- 4. Kiosque : Chromium plein écran au démarrage --------------------------
echo "==> Configuration du démarrage automatique de l'écran (kiosque)…"
KIOSK="$PROJECT_DIR/install/kiosk.sh"
chmod +x "$KIOSK" 2>/dev/null || true

# a) labwc (bureau par défaut Pi OS Bookworm sur Pi 4/5)
mkdir -p "$RUN_HOME/.config/labwc"
LABWC_AUTOSTART="$RUN_HOME/.config/labwc/autostart"
grep -q "kiosk.sh" "$LABWC_AUTOSTART" 2>/dev/null || echo "$KIOSK &" >> "$LABWC_AUTOSTART"

# b) LXDE / X (Pi OS plus anciens)
mkdir -p "$RUN_HOME/.config/lxsession/LXDE-pi"
LX_AUTOSTART="$RUN_HOME/.config/lxsession/LXDE-pi/autostart"
grep -q "kiosk.sh" "$LX_AUTOSTART" 2>/dev/null || echo "@$KIOSK" >> "$LX_AUTOSTART"

# c) Raccourci .desktop, posé à TROIS endroits depuis une seule définition :
#    le démarrage automatique, le menu des applications, et le bureau.
#    Le démarrage automatique reste en place : brancher le boîtier doit suffire à
#    afficher le prompteur, sans le moindre geste. L'icône ne le remplace pas,
#    elle permet de le RELANCER après l'avoir fermé, sans redémarrer la machine.
DESKTOP_ENTRY="$(mktemp)"
cat > "$DESKTOP_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Le Prompteur
Comment=Affiche le prompteur en plein ecran
Exec=$KIOSK
Icon=video-display
Terminal=false
Categories=AudioVideo;
X-GNOME-Autostart-enabled=true
EOF

for target in "$RUN_HOME/.config/autostart" "$RUN_HOME/.local/share/applications"; do
  mkdir -p "$target"
  install -m 755 "$DESKTOP_ENTRY" "$target/prompteur-kiosk.desktop"
done

# Bureau : le nom du dossier dépend de la langue du système (Desktop / Bureau).
# Le script tourne deja sous l'utilisateur visé : pas de su, qui réclamerait un
# mot de passe et bloquerait l'installation sur une invite que personne n'attend.
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[ -d "${DESKTOP_DIR:-}" ] || DESKTOP_DIR="$RUN_HOME/Bureau"
[ -d "$DESKTOP_DIR" ] || DESKTOP_DIR="$RUN_HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
  # Exécutable : sans cela le gestionnaire de fichiers demande confirmation
  # à chaque double-clic au lieu de lancer directement.
  install -m 755 "$DESKTOP_ENTRY" "$DESKTOP_DIR/prompteur-kiosk.desktop"
  echo "    Icône « Le Prompteur » posée sur le bureau ($DESKTOP_DIR)."
else
  echo "    /!\\ Dossier du bureau introuvable : icône non posée (sans conséquence)."
fi
rm -f "$DESKTOP_ENTRY"

echo
echo "============================================================"
echo " Installation terminée."
echo "  • Serveur     : http://localhost:$PORT/display (écran)"
echo "  • Téléphone   : connecte-toi au WiFi « $WIFI_SSID »"
echo "                  (mot de passe : $WIFI_PASS)"
echo "                  puis ouvre http://10.42.0.1:$PORT"
echo "  • À distance  : ssh $RUN_USER@$BOX_NAME.local   (boîtier relié en Ethernet)"
echo "                  ssh $RUN_USER@10.42.0.1       (via le WiFi du boîtier)"
echo "  • Icône        : « Le Prompteur » sur le bureau (pour le relancer"
echo "                   après l'avoir fermé, sans redémarrer)"
echo "  • Redémarre le Raspberry Pi pour tout activer :  sudo reboot"
echo "============================================================"
