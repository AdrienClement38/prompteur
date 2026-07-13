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
WorkingDirectory="$PROJECT_DIR"
Environment=PROMPTEUR_PORT=$PORT
ExecStart=/usr/bin/python3 "$PROJECT_DIR/server.py"
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable prompteur.service
sudo systemctl restart prompteur.service
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

# c) Entrée .desktop générique
mkdir -p "$RUN_HOME/.config/autostart"
cat > "$RUN_HOME/.config/autostart/prompteur-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Prompteur Kiosque
Exec=$KIOSK
X-GNOME-Autostart-enabled=true
EOF

echo
echo "============================================================"
echo " Installation terminée."
echo "  • Serveur     : http://localhost:$PORT/display (écran)"
echo "  • Téléphone   : connecte-toi au WiFi « $WIFI_SSID »"
echo "                  (mot de passe : $WIFI_PASS)"
echo "                  puis ouvre http://10.42.0.1:$PORT"
echo "  • Redémarre le Raspberry Pi pour tout activer :  sudo reboot"
echo "============================================================"
