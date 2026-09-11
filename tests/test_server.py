# -*- coding: utf-8 -*-
"""Tests de l'API du prompteur.

Ils exercent le fonctionnement nominal ET verrouillent les correctifs de l'audit
sécurité (validation des réglages, traversée de chemin, limite de taille, 409,
protection anti-CSRF…), pour empêcher toute régression.
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


def _upload(client, data, name, headers=None):
    """Envoi de fichier, avec l'en-tête client que le serveur exige (anti-CSRF)."""
    return client.post(
        "/api/upload",
        data={"file": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
        headers={server.CLIENT_HEADER: "1"} if headers is None else headers,
    )


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
    client.post("/api/library/load", json={"name": "Sujet"})
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
    r = _upload(client, "Réunion".encode("utf-8"), "note.txt")
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
    r = _upload(client, data, "note.docx")
    assert r.status_code == 200
    assert client.get("/api/state").get_json()["text"] == "Titre\nCorps du texte."


def test_upload_fichier_illisible_erreur_claire(client):
    r = _upload(client, b"ceci n'est pas un docx", "faux.docx")
    assert r.status_code == 400
    assert "error" in r.get_json()


# ============================================================================
# Anti-CSRF
# ----------------------------------------------------------------------------
# Le confinement réseau (pare-feu + WPA2) ne protège pas du NAVIGATEUR d'un
# appareil déjà connecté au WiFi du boîtier : une page piégée ouverte sur le
# téléphone du cadreur peut viser 10.42.0.1 sans aucune interaction. Ces tests
# verrouillent les deux barrières posées dans server.py.
# ============================================================================

# Toutes les routes qui MODIFIENT l'état, avec un corps par ailleurs valide.
ROUTES_ECRITURE = [
    ("/api/text", {"text": "injecté par un tiers"}),
    ("/api/settings", {"fontSize": 8, "textColor": "#000000"}),
    ("/api/command", {"cmd": "restart"}),
    ("/api/scroll", {"pos": 10, "vel": 1, "playing": True}),
    ("/api/library/save", {"name": "x", "text": "y", "overwrite": True}),
    ("/api/library/load", {"name": "x"}),
    ("/api/library/delete", {"name": "x"}),
    ("/api/usb/load", {"path": "/tmp/x.txt"}),
]


@pytest.mark.parametrize("path,payload", ROUTES_ECRITURE)
def test_csrf_content_type_non_json_refuse(client, path, payload):
    """text/plain est une « simple request » : sans cette barrière, elle passerait."""
    r = client.post(path, data=json.dumps(payload), content_type="text/plain")
    assert r.status_code == 415, path


@pytest.mark.parametrize("path,payload", ROUTES_ECRITURE)
def test_csrf_origine_etrangere_refusee(client, path, payload):
    """Même avec le bon Content-Type, une autre origine est refusée."""
    r = client.post(path, json=payload, headers={"Origin": "http://pub.example"})
    assert r.status_code == 403, path


@pytest.mark.parametrize("path,payload", ROUTES_ECRITURE)
def test_csrf_referer_etranger_refuse(client, path, payload):
    """Secours quand Origin est absent."""
    r = client.post(path, json=payload, headers={"Referer": "http://pub.example/page"})
    assert r.status_code == 403, path


def test_csrf_attaque_ne_modifie_rien(client):
    """Le scénario réel, de bout en bout : rien ne doit bouger à l'antenne."""
    client.post("/api/text", json={"text": "script du jour"})
    avant = client.get("/api/state").get_json()
    for content_type in ("text/plain", "application/x-www-form-urlencoded"):
        client.post("/api/text", data='{"text": "PIRATE"}', content_type=content_type)
        client.post("/api/settings", data='{"fontSize": 8}', content_type=content_type)
    pirate = {"Origin": "http://pub.example"}
    client.post("/api/text", json={"text": "PIRATE"}, headers=pirate)
    client.post("/api/settings", json={"fontSize": 8}, headers=pirate)
    client.post("/api/library/delete", json={"name": "Sujet"}, headers=pirate)
    apres = client.get("/api/state").get_json()
    assert apres["text"] == "script du jour"
    assert apres["settings"]["fontSize"] == avant["settings"]["fontSize"]


def test_meme_origine_toujours_acceptee(client):
    """La télécommande légitime ne doit surtout pas être gênée."""
    r = client.post("/api/text", json={"text": "ok"}, headers={"Origin": "http://localhost"})
    assert r.status_code == 200
    assert client.get("/api/state").get_json()["text"] == "ok"


def test_library_load_refuse_le_get(client):
    """Route qui change le texte à l'antenne : injoignable par <img src=...>."""
    client.post("/api/library/save", json={"name": "Sujet", "text": "v1"})
    assert client.get("/api/library/load?name=Sujet").status_code == 405


def test_upload_sans_entete_client_refuse(client):
    """multipart échappe au Content-Type : l'en-tête maison prend le relais."""
    r = _upload(client, "texte pirate".encode("utf-8"), "note.txt", headers={})
    assert r.status_code == 403
    assert client.get("/api/state").get_json()["text"] != "texte pirate"


def test_upload_origine_etrangere_refusee(client):
    r = _upload(
        client,
        "texte pirate".encode("utf-8"),
        "note.txt",
        headers={server.CLIENT_HEADER: "1", "Origin": "http://pub.example"},
    )
    assert r.status_code == 403


def test_lectures_non_genees_par_le_garde_fou(client):
    """Les GET restent libres : une origine tierce ne peut pas lire la réponse (CORS)."""
    for path in ("/api/state", "/api/version", "/api/scroll", "/api/library", "/api/info"):
        r = client.get(path, headers={"Origin": "http://pub.example"})
        assert r.status_code == 200, path
