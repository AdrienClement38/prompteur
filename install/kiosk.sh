#!/usr/bin/env bash
# Lance l'écran du prompteur en plein écran (mode kiosque) au démarrage.
# Attend que le serveur réponde, puis ouvre Chromium sur /display.

PORT="${PROMPTEUR_PORT:-5000}"
URL="http://localhost:${PORT}/display"

# Empêche la mise en veille de l'écran / l'économiseur
xset s off        2>/dev/null || true
xset -dpms        2>/dev/null || true
xset s noblank    2>/dev/null || true
# Masque le curseur au repos
unclutter -idle 0.5 -root 2>/dev/null &

# Attend que le serveur soit prêt (max ~30 s)
for i in $(seq 1 60); do
  if curl -s "http://localhost:${PORT}/api/state" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Choisit le binaire Chromium disponible
BROWSER="$(command -v chromium-browser || command -v chromium)"
if [ -z "$BROWSER" ]; then
  echo "Prompteur: Chromium introuvable (ni chromium-browser ni chromium). Installez le paquet chromium." >&2
  exit 1
fi

exec "$BROWSER" \
  --kiosk \
  --start-fullscreen \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --app="$URL"
