# -*- coding: utf-8 -*-
"""Tests de l'API du prompteur.

Ils exercent le fonctionnement nominal ET verrouillent les correctifs de l'audit
sécurité (validation des réglages, traversée de chemin, limite de taille, 409…),
pour empêcher toute régression.
"""

import copy
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client de test isolé : stockage dans un dossier temporaire, état réinitialisé."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    monkeypatch.setattr(server, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(server, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(server, "STATE", copy.deepcopy(server.DEFAULT_STATE))
    server.app.config.update(TESTING=True)
    return server.app.test_client()


# --- Fonctionnement de base --------------------------------------------------
def test_pages_repondent(client):
    for path in ("/", "/display", "/api/state", "/api/version", "/api/info", "/api/usb", "/api/library"):
        assert client.get(path).status_code == 200, path


def test_entetes_securite(client):
    r = client.get("/api/state")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_envoi_texte_incremente_version(client):
    v0 = client.get("/api/version").get_json()["version"]
    assert client.post("/api/text", json={"text": "Bonjour", "title": "T"}).status_code == 200
    st = client.get("/api/state").get_json()
    assert st["text"] == "Bonjour"
    assert st["version"] > v0


def test_accents_utf8_preserves(client):
    txt = "Événement spécial : caféçàü — ligne accentuée"
    client.post("/api/text", json={"text": txt})
    assert client.get("/api/state").get_json()["text"] == txt


# --- Validation des réglages (correctifs audit #4 / #11) ---------------------
def test_reglages_valides_acceptes(client):
    client.post("/api/settings", json={"fontSize": 48, "textColor": "#112233", "mode": "tap"})
    s = client.get("/api/state").get_json()["settings"]
    assert s["fontSize"] == 48
    assert s["textColor"] == "#112233"
    assert s["mode"] == "tap"


def test_reglages_aberrants_rejetes(client):
    client.post(
        "/api/settings", json={"fontSize": 10**9, "bgColor": "javascript:alert(1)", "mode": "pirate", "speed": "abc"}
    )
    s = client.get("/api/state").get_json()["settings"]
    assert s["fontSize"] == 64  # défaut conservé
    assert s["bgColor"] == "#000000"  # couleur invalide rejetée
    assert s["mode"] == "hold"  # enum invalide rejeté
    assert s["speed"] == 70  # type invalide rejeté


def test_booleen_refuse_comme_nombre(client):
    client.post("/api/settings", json={"fontSize": True})
    assert client.get("/api/state").get_json()["settings"]["fontSize"] == 64


# --- Commandes de pilotage (correctif audit #8) ------------------------------
def test_vitesse_cumulative_et_bornee(client):
    client.post("/api/settings", json={"speed": 100})
    r = None
    for _ in range(3):
        r = client.post("/api/command", json={"cmd": "faster"})
    assert r.get_json()["speed"] == 130  # le serveur renvoie la nouvelle vitesse (pour la barre)
    assert client.get("/api/state").get_json()["settings"]["speed"] == 130
    for _ in range(100):
        client.post("/api/command", json={"cmd": "faster"})
    assert client.get("/api/state").get_json()["settings"]["speed"] == 600  # borne haute


def test_commande_inconnue_refusee(client):
    assert client.post("/api/command", json={"cmd": "rm -rf /"}).status_code == 400


# --- Bibliothèque (correctif audit #10) --------------------------------------
def test_bibliotheque_collision_et_ecrasement(client):
    assert client.post("/api/library/save", json={"name": "Sujet", "text": "v1"}).status_code == 200
    assert client.post("/api/library/save", json={"name": "Sujet", "text": "v2"}).status_code == 409
    assert client.post("/api/library/save", json={"name": "Sujet", "text": "v2", "overwrite": True}).status_code == 200
    client.get("/api/library/load?name=Sujet")
    assert client.get("/api/state").get_json()["text"] == "v2"


def test_bibliotheque_traversee_confinee(client):
    # un nom cherchant à sortir de scripts/ est nettoyé -> reste confiné
    client.post("/api/library/save", json={"name": "../../evil", "text": "x", "overwrite": True})
    assert not (server.SCRIPTS_DIR.parent / "evil.txt").exists()
    assert list(server.SCRIPTS_DIR.glob("*.txt"))  # créé, mais dans scripts/


# --- Import USB (correctif audit #9) -----------------------------------------
def test_usb_load_refuse_chemin_arbitraire(client):
    for p in ("/etc/passwd", "C:/Windows/win.ini", "../server.py", ""):
        assert client.post("/api/usb/load", json={"path": p}).status_code == 400, p


# --- Limite de taille (correctif audit #1) -----------------------------------
def test_corps_trop_gros_refuse(client):
    big = "x" * (7 * 1024 * 1024)
    r = client.post("/api/text", data=json.dumps({"text": big}), content_type="application/json")
    assert r.status_code == 413
    assert len(client.get("/api/state").get_json()["text"]) < 1000  # non stocké


# --- Téléversement -----------------------------------------------------------
def test_upload_txt(client):
    r = client.post(
        "/api/upload",
        data={"file": (io.BytesIO("Réunion".encode("utf-8")), "note.txt")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert client.get("/api/state").get_json()["text"] == "Réunion"


# --- Robustesse : un state.json corrompu se répare au chargement -------------
def test_state_corrompu_se_repare(client, tmp_path):
    bad = {"settings": {"fontSize": 10**9, "bgColor": "nope", "align": "diagonal"}}
    (tmp_path / "state.json").write_text(json.dumps(bad), encoding="utf-8")
    monkey_file = tmp_path / "state.json"
    server.STATE_FILE = monkey_file
    st = server.load_state()
    assert st["settings"]["fontSize"] == 64
    assert st["settings"]["bgColor"] == "#000000"
    assert st["settings"]["align"] == "left"


# --- Écrans meneur / spectateur ----------------------------------------------
def test_routes_ecrans(client):
    assert client.get("/display").status_code == 200
    assert client.get("/view").status_code == 200


# --- Synchro : position de défilement ----------------------------------------
def test_scroll_get_post_et_bornes(client):
    r0 = client.get("/api/scroll").get_json()
    assert {"pos", "vel", "playing", "seq"} <= set(r0)
    seq0 = r0["seq"]
    client.post("/api/scroll", json={"pos": 42.5, "vel": 100, "playing": True})
    s = client.get("/api/scroll").get_json()
    assert s["pos"] == 42.5
    assert s["vel"] == 100.0
    assert s["playing"] is True
    assert s["seq"] == seq0 + 1  # chaque point incrémente la séquence
    # bornes de sécurité (valeurs aberrantes plafonnées)
    client.post("/api/scroll", json={"pos": 1e12, "vel": 999999})
    s2 = client.get("/api/scroll").get_json()
    assert s2["pos"] <= 1e7
    assert s2["vel"] <= 5000


# --- Import de formats bureautiques (correctif : .docx & nettoyage) ----------
def _docx_bytes(paragraphs):
    xml = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
    for para in paragraphs:
        xml += f"<w:p><w:r><w:t>{para}</w:t></w:r></w:p>"
    xml += "</w:body></w:document>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_upload_docx_extrait_et_nettoie(client):
    data = _docx_bytes(["Titre", "Corps du   texte."])  # espaces multiples -> nettoyés
    r = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(data), "note.docx")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert client.get("/api/state").get_json()["text"] == "Titre\nCorps du texte."


def test_upload_fichier_illisible_erreur_claire(client):
    r = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"ceci n'est pas un docx"), "faux.docx")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "error" in r.get_json()
