"""install/essai_pedales.py : l'essai des pédales que lance verifier-boitier.sh.

Un essai qui dirait « ✅ » à tort serait pire que pas d'essai. On le fait donc
tourner contre un faux boîtier dont la vue Journaliste obéit aux règles des trois
modes — et contre un boîtier en panne (pédale qui reste collée, pédale ignorée),
où il DOIT répondre « en échec ».
"""

import json
import os
import subprocess  # nosec B404 - programme du dépôt, arguments fixes
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ESSAI = Path(__file__).resolve().parent.parent / "install" / "essai_pedales.py"
VITESSE = 100.0  # px/s, à l'échelle du faux boîtier


class FauxBoitier:
    """Position du texte, pédales et commandes, comme la vue Journaliste."""

    def __init__(self, mode, panne=None):
        self.mode, self.panne = mode, panne
        self.pos, self.vel, self.depuis = 0.0, 0.0, time.monotonic()
        self.verrou = threading.Lock()

    def _avancer(self):
        maintenant = time.monotonic()
        self.pos += self.vel * (maintenant - self.depuis)
        self.depuis = maintenant

    def position(self):
        with self.verrou:
            self._avancer()
            return self.pos

    def commande(self, cmd):
        with self.verrou:
            self._avancer()
            if cmd == "restart":
                self.pos, self.vel = 0.0, 0.0

    def pedale(self, genre, cle):
        with self.verrou:
            self._avancer()
            if self.panne == "ignoree":
                return
            if cle == "ArrowDown":
                if self.mode == "hold":
                    if genre == "down":
                        self.vel = VITESSE
                    elif self.panne != "collee":
                        self.vel = 0.0
                elif self.mode == "tap" and genre == "down":
                    self.vel = 0.0 if self.vel else VITESSE
                elif self.mode == "dyn" and genre == "down":
                    self.vel = VITESSE
            elif cle == "ArrowRight" and self.mode == "dyn" and genre == "down" and self.panne != "collee":
                self.vel = 0.0


def serveur(boitier):
    class Gestion(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _repondre(self, corps):
            donnees = json.dumps(corps).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)

        def do_GET(self):
            if self.path == "/api/state":
                reglages = {"mode": boitier.mode, "keyForward": "ArrowDown", "keyCenter": "ArrowRight"}
                self._repondre({"settings": reglages})
            elif self.path == "/api/version":
                self._repondre({"veille": False})
            elif self.path == "/api/scroll":
                self._repondre({"pos": boitier.position()})
            else:
                self._repondre({})

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/command":
                boitier.commande(corps.get("cmd"))
            elif self.path == "/api/pedale":
                boitier.pedale(corps.get("type"), corps.get("key"))
            self._repondre({"ok": True})

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Gestion)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def essayer(mode, panne=None):
    httpd = serveur(FauxBoitier(mode, panne))
    try:
        env = dict(os.environ, PROMPTEUR_ESSAI_ECHELLE="0.2")
        r = subprocess.run(  # nosec B603 - programme du dépôt, arguments fixes
            [sys.executable, str(ESSAI), "relais", str(httpd.server_address[1])],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        httpd.shutdown()


@pytest.mark.parametrize("mode", ["hold", "tap", "dyn"])
def test_pedales_qui_marchent(mode):
    code, resultat = essayer(mode)
    assert code == 0, resultat
    assert resultat["avance"] and resultat["arret"] and resultat["mode"] == mode


@pytest.mark.parametrize("mode", ["hold", "tap", "dyn"])
def test_pedale_ignoree_signalee(mode):
    """Le texte ne bouge pas : l'essai DOIT échouer."""
    code, resultat = essayer(mode, panne="ignoree")
    assert code == 1 and not resultat["avance"]


@pytest.mark.parametrize("mode", ["hold", "dyn"])
def test_pedale_collee_signalee(mode):
    """Le texte part et ne s'arrête plus : l'essai DOIT échouer."""
    code, resultat = essayer(mode, panne="collee")
    assert code == 1 and resultat["avance"] and not resultat["arret"]
