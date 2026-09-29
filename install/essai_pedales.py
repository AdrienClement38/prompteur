#!/usr/bin/env python3
"""Essai des pédales SUR LE BOÎTIER, lancé par install/verifier-boitier.sh.

Joue le geste du journaliste et regarde si le texte du grand écran avance, puis
s'arrête — en lisant la position que la vue Journaliste envoie au boîtier.

Deux façons d'appuyer :
  relais   : comme le petit écran transmet une pédale (POST /api/pedale).
  clavier  : comme le VRAI pédalier — un clavier virtuel (uinput) : la touche va
             à la fenêtre qui a la main, exactement comme le pédalier. Demande
             sudo (accès à /dev/uinput).

Le geste dépend du mode des pédales (maintien, impulsion, dynamique). À la fin,
le texte revient au début, à l'arrêt. Sortie : une ligne JSON ; code 0 si le
texte a avancé PUIS s'est arrêté, 1 sinon, 2 si l'essai n'a pas pu se faire.
"""

import json
import os
import struct
import sys
import time
import urllib.request

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
# Pour les essais automatiques (tests/test_essai_pedales.py) : attentes raccourcies.
ECHELLE = float(os.environ.get("PROMPTEUR_ESSAI_ECHELLE", "1"))


def attendre(secondes):
    time.sleep(secondes * ECHELLE)


# 127.0.0.1 et non « localhost » : ce nom essaie d'abord l'IPv6, que le serveur
# n'écoute pas — deux secondes perdues par requête sur certains systèmes.
BASE = "http://127.0.0.1:%d" % PORT

# Codes des touches (noyau Linux) : seulement celles qui ne dépendent pas de la
# disposition du clavier (AZERTY ou QWERTY), pour appuyer à coup sûr la bonne.
CODES = {
    "ArrowUp": 103,
    "ArrowLeft": 105,
    "ArrowRight": 106,
    "ArrowDown": 108,
    "PageUp": 104,
    "PageDown": 109,
    " ": 57,
    "Enter": 28,
    "Tab": 15,
}


def lire(chemin):
    # Adresse fixe du boîtier lui-même (localhost) : pas d'URL venue de l'extérieur.
    with urllib.request.urlopen(BASE + chemin, timeout=5) as r:  # nosec B310
        return json.load(r)


def poster(chemin, corps):
    requete = urllib.request.Request(
        BASE + chemin, data=json.dumps(corps).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requete, timeout=5) as r:  # nosec B310
        return json.load(r)


def position():
    return float(lire("/api/scroll").get("pos", 0))


class ClavierVirtuel:
    """Un clavier USB imaginaire, déclaré au noyau par /dev/uinput."""

    UI_SET_EVBIT, UI_SET_KEYBIT, UI_DEV_CREATE, UI_DEV_DESTROY = 0x40045564, 0x40045565, 0x5501, 0x5502
    EV_SYN, EV_KEY = 0, 1

    def __init__(self):
        import fcntl  # Linux seulement : chargé ici, l'essai « relais » s'en passe

        self.ioctl = fcntl.ioctl
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        self.ioctl(self.fd, self.UI_SET_EVBIT, self.EV_KEY)
        for code in CODES.values():
            self.ioctl(self.fd, self.UI_SET_KEYBIT, code)
        # struct uinput_user_dev : nom, identité (bus USB), puis 4 × 64 entiers.
        identite = struct.pack("=80sHHHHI", b"prompteur-essai-pedales", 0x03, 0x1209, 0x0001, 1, 0)
        os.write(self.fd, identite + struct.pack("=256i", *([0] * 256)))
        self.ioctl(self.fd, self.UI_DEV_CREATE)
        attendre(2.0)  # le temps que le bureau découvre ce « clavier »

    def _evenement(self, genre, code, valeur):
        os.write(self.fd, struct.pack("llHHi", 0, 0, genre, code, valeur))

    def touche(self, cle, enfoncee):
        self._evenement(self.EV_KEY, CODES[cle], 1 if enfoncee else 0)
        self._evenement(self.EV_SYN, 0, 0)

    def fermer(self):
        self.ioctl(self.fd, self.UI_DEV_DESTROY)
        os.close(self.fd)


def main():
    moyen = sys.argv[1] if len(sys.argv) > 1 else "relais"
    try:
        etat = lire("/api/state")
        if lire("/api/version").get("veille"):
            print(json.dumps({"erreur": "le boîtier est en veille : rallumez-le d'abord"}))
            return 2
    except OSError as e:
        print(json.dumps({"erreur": "boîtier injoignable (%s)" % e}))
        return 2
    s = etat.get("settings", {})
    mode = s.get("mode", "hold")
    avant, centrale = s.get("keyForward", "ArrowDown"), s.get("keyCenter", "ArrowRight")

    clavier = None
    if moyen == "clavier":
        if avant not in CODES or (mode == "dyn" and centrale not in CODES):
            print(json.dumps({"erreur": "touches de pédale inhabituelles (%s) : essai au clavier impossible" % avant}))
            return 2
        try:
            clavier = ClavierVirtuel()
        except OSError as e:
            print(json.dumps({"erreur": "clavier virtuel impossible (%s) — lancer avec sudo" % e}))
            return 2

    def appui(cle, enfoncee):
        if clavier:
            clavier.touche(cle, enfoncee)
        else:
            poster("/api/pedale", {"type": "down" if enfoncee else "up", "key": cle})

    try:
        poster("/api/command", {"cmd": "restart"})  # texte au début, à l'arrêt
        attendre(2.5)
        p0 = position()
        if mode == "tap":
            appui(avant, True)
            appui(avant, False)
            attendre(1.5)
            p1 = position()
            appui(avant, True)  # seconde pression sur la même pédale = pause
            appui(avant, False)
        elif mode == "dyn":
            appui(avant, True)
            attendre(1.5)
            appui(avant, False)
            attendre(0.8)
            p1 = position()
            appui(centrale, True)  # la centrale = pause
            appui(centrale, False)
        else:  # maintien
            appui(avant, True)
            attendre(1.5)
            p1 = position()
            appui(avant, False)
        attendre(2.5)
        p2 = position()
        attendre(2.0)
        p3 = position()
    finally:
        if clavier:
            clavier.fermer()
        try:
            poster("/api/command", {"cmd": "restart"})
        except OSError:
            pass
    resultat = {
        "mode": mode,
        "positions": [round(p, 1) for p in (p0, p1, p2, p3)],
        "avance": p1 - p0 > 10,
        "arret": abs(p3 - p2) < 3,
    }
    print(json.dumps(resultat))
    return 0 if resultat["avance"] and resultat["arret"] else 1


if __name__ == "__main__":
    sys.exit(main())
