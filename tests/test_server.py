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
import textextract  # noqa: E402

LF = chr(10)  # saut de ligne, nommé pour la lisibilité des cas de test


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


# ============================================================================
# Bornes de taille du texte
# ----------------------------------------------------------------------------
# display.js crée un <div> par ligne dans une page qui anime un transform à
# 60 images/s : quelques dizaines de milliers de lignes figent l'écran. Et comme
# le texte est persisté dans state.json, le gel SURVIVRAIT AU REDÉMARRAGE.
# Mesuré avant correctif : un .docx de 35 Ko -> 7,7 Mo de texte, 40 000 lignes.
# Ce n'est pas qu'une attaque : un gros PDF importé par erreur fait la même chose.
# ============================================================================


def _docx_bombe(paragraphes=40000, taille=200):
    """Un .docx parfaitement valide, mais dont le XML se décompresse énormément."""
    para = "<w:p><w:r><w:t>" + ("A" * taille) + "</w:t></w:r></w:p>"
    xml = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>' + para * paragraphes + "</w:body></w:document>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_docx_bombe_refuse_et_etat_intact(client):
    client.post("/api/text", json={"text": "script du jour"})
    bombe = _docx_bombe()
    assert len(bombe) < 200 * 1024  # le fichier envoyé est minuscule
    r = _upload(client, bombe, "piege.docx")
    assert r.status_code == 400
    assert "error" in r.get_json()
    assert client.get("/api/state").get_json()["text"] == "script du jour"


def test_texte_trop_long_refuse(client):
    client.post("/api/text", json={"text": "script du jour"})
    r = client.post("/api/text", json={"text": "x" * (textextract.MAX_TEXT_CHARS + 1)})
    assert r.status_code == 400
    assert client.get("/api/state").get_json()["text"] == "script du jour"


def test_trop_de_lignes_refuse(client):
    trop = LF.join("l" for _ in range(textextract.MAX_TEXT_LINES + 10))
    assert client.post("/api/text", json={"text": trop}).status_code == 400


def test_txt_trop_long_refuse_a_l_import(client):
    gros = ("x" * (textextract.MAX_TEXT_CHARS + 1)).encode("utf-8")
    assert _upload(client, gros, "enorme.txt").status_code == 400


def test_bibliotheque_texte_trop_long_refuse(client):
    """Un .txt démesuré déposé à la main dans scripts/ ne part pas à l'antenne."""
    gros = "x" * (textextract.MAX_TEXT_CHARS + 1)
    (server.SCRIPTS_DIR / "enorme.txt").write_text(gros, encoding="utf-8")
    assert client.post("/api/library/load", json={"name": "enorme"}).status_code == 400


def test_state_json_empoisonne_se_tronque_au_demarrage(client, tmp_path):
    """Filet de dernier recours : le boîtier doit redémarrer, pas rester figé."""
    poison = LF.join("l" for _ in range(textextract.MAX_TEXT_LINES * 2))
    (tmp_path / "state.json").write_text(json.dumps({"text": poison}), encoding="utf-8")
    server.STATE_FILE = tmp_path / "state.json"
    st = server.load_state()
    assert st["text"].count(LF) + 1 <= textextract.MAX_TEXT_LINES + 3
    assert "tronqué" in st["text"]


def test_document_normal_toujours_accepte(client):
    """Non-régression : un script de tournage réaliste passe sans encombre."""
    normal = LF.join("Ligne de script numéro %d." % i for i in range(500))
    assert client.post("/api/text", json={"text": normal}).status_code == 200
    r = _upload(client, _docx_bytes(["Titre", "Corps du texte."]), "normal.docx")
    assert r.status_code == 200


# ============================================================================
# Ouverture / fermeture de l'écran du prompteur
# ----------------------------------------------------------------------------
# Joignables depuis TOUS les appareils du WiFi du boîtier, téléphone compris :
# on doit pouvoir refermer ou relancer l'écran sans aller toucher le boîtier.
# Les garde-fous sont le pare-feu et la protection anti-CSRF.
# ============================================================================

DEPUIS_UN_TELEPHONE = {"REMOTE_ADDR": "10.42.0.57"}


def test_kiosque_propose_depuis_un_telephone(client):
    r = client.get("/api/kiosk", environ_base=DEPUIS_UN_TELEPHONE)
    assert r.status_code == 200
    assert r.get_json()["available"] is True


def test_kiosque_commandes_acceptees_depuis_un_telephone(client):
    for route in ("/api/kiosk/close", "/api/kiosk/launch"):
        r = client.post(route, json={}, environ_base=DEPUIS_UN_TELEPHONE)
        assert r.status_code != 403, route


def test_kiosque_etat_indetermine_plutot_que_barre_cachee(client):
    """Là où le script ne peut pas tourner, on l'annonce au lieu de tout cacher :
    sinon la fonction disparaîtrait sans le moindre indice."""
    r = client.get("/api/kiosk")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert "running" in body  # bool sur le boîtier, None ailleurs


def test_kiosque_protege_aussi_par_l_anti_csrf(client):
    """Une page tierce ne doit pas pouvoir fermer le prompteur."""
    pirate = {"Origin": "http://pub.example"}
    assert client.post("/api/kiosk/close", json={}, headers=pirate).status_code == 403
    assert client.post("/api/kiosk/launch", json={}, headers=pirate).status_code == 403
    r = client.post("/api/kiosk/close", data="{}", content_type="text/plain")
    assert r.status_code == 415


# ============================================================================
# Réservation de l'écran principal
# ----------------------------------------------------------------------------
# Un seul meneur à la fois : deux écrans principaux pousseraient chacun leur
# position de défilement et le texte sauterait en pleine lecture. Mais le bail
# doit TOUJOURS pouvoir être repris : un verrou bloqué condamnerait le prompteur,
# soit exactement l'inverse du but recherché.
# ============================================================================


@pytest.fixture(autouse=True)
def _place_libre():
    """Chaque test part d'une place de meneur libre."""
    server._presenter["token"] = None
    server._presenter["seen"] = 0.0
    yield


def test_premier_arrive_obtient_la_place(client):
    r = client.post("/api/presenter/claim", json={"token": "ecran-A"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert client.get("/api/presenter").get_json()["taken"] is True


def test_second_ecran_refuse(client):
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    r = client.post("/api/presenter/claim", json={"token": "ecran-B"})
    assert r.status_code == 409
    assert r.get_json()["taken"] is True


def test_le_meme_ecran_peut_reprendre_sa_place(client):
    """Un rechargement de page ne doit pas se verrouiller dehors tout seul."""
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    assert client.post("/api/presenter/claim", json={"token": "ecran-A"}).status_code == 200


def test_reprise_en_main_forcee_toujours_possible(client):
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    r = client.post("/api/presenter/claim", json={"token": "ecran-B", "force": True})
    assert r.status_code == 200
    # L'évincé l'apprend à son prochain battement et cesse de piloter.
    assert client.post("/api/presenter/ping", json={"token": "ecran-A"}).get_json()["ok"] is False
    assert client.post("/api/presenter/ping", json={"token": "ecran-B"}).get_json()["ok"] is True


def test_bail_expire_tout_seul(client):
    """Onglet ferme brutalement, WiFi coupe, boitier redemarre : la place se
    libère sans intervention. C'est ce qui empêche de condamner le prompteur."""
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    server._presenter["seen"] -= server.PRESENTER_TTL + 1
    assert client.get("/api/presenter").get_json()["taken"] is False
    assert client.post("/api/presenter/claim", json={"token": "ecran-B"}).status_code == 200


def test_liberation_explicite(client):
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    client.post("/api/presenter/release", json={"token": "ecran-A"})
    assert client.get("/api/presenter").get_json()["taken"] is False


def test_liberation_par_un_autre_sans_effet(client):
    client.post("/api/presenter/claim", json={"token": "ecran-A"})
    client.post("/api/presenter/release", json={"token": "ecran-B"})
    assert client.get("/api/presenter").get_json()["taken"] is True


def test_le_jeton_du_meneur_n_est_jamais_divulgue(client):
    client.post("/api/presenter/claim", json={"token": "secret-A"})
    corps = client.get("/api/presenter").get_json()
    assert "secret-A" not in json.dumps(corps)
    assert corps["mine"] is False
    assert client.get("/api/presenter?token=secret-A").get_json()["mine"] is True


def test_claim_sans_jeton_refuse(client):
    assert client.post("/api/presenter/claim", json={}).status_code == 400
