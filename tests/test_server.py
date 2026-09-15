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
    server._presenter["holder"] = None
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


# ============================================================================
# Synchronisation de la bibliothèque
# ----------------------------------------------------------------------------
# Enregistrer ou supprimer un texte doit apparaître sur TOUS les appareils sans
# recharger la page. Le compteur est volontairement distinct de STATE["version"] :
# faire avancer la version générale obligerait les écrans de lecture à
# retélécharger le script pour rien, en pleine prise.
# ============================================================================


def _lib_seq(client):
    return client.get("/api/version").get_json()["libSeq"]


def test_version_expose_le_compteur_de_bibliotheque(client):
    assert "libSeq" in client.get("/api/version").get_json()


def test_enregistrement_fait_avancer_le_compteur(client):
    avant = _lib_seq(client)
    client.post("/api/library/save", json={"name": "Sujet", "text": "v1"})
    assert _lib_seq(client) == avant + 1


def test_suppression_fait_avancer_le_compteur(client):
    client.post("/api/library/save", json={"name": "Sujet", "text": "v1"})
    avant = _lib_seq(client)
    client.post("/api/library/delete", json={"name": "Sujet"})
    assert _lib_seq(client) == avant + 1


def test_suppression_d_un_texte_absent_ne_change_rien(client):
    avant = _lib_seq(client)
    client.post("/api/library/delete", json={"name": "jamais-existe"})
    assert _lib_seq(client) == avant


def test_collision_refusee_ne_change_rien(client):
    client.post("/api/library/save", json={"name": "Sujet", "text": "v1"})
    avant = _lib_seq(client)
    assert client.post("/api/library/save", json={"name": "Sujet", "text": "v2"}).status_code == 409
    assert _lib_seq(client) == avant


def test_envoyer_du_texte_ne_touche_pas_la_bibliotheque(client):
    """Les deux compteurs sont indépendants : un écran de lecture ne doit pas
    retélécharger son script parce qu'on a rangé un texte ailleurs."""
    avant_lib = _lib_seq(client)
    avant_ver = client.get("/api/version").get_json()["version"]
    client.post("/api/text", json={"text": "nouveau script"})
    assert _lib_seq(client) == avant_lib
    assert client.get("/api/version").get_json()["version"] > avant_ver


def test_ranger_un_texte_ne_touche_pas_l_antenne(client):
    avant_ver = client.get("/api/version").get_json()["version"]
    client.post("/api/library/save", json={"name": "Sujet", "text": "v1"})
    assert client.get("/api/version").get_json()["version"] == avant_ver


# ============================================================================
# Réglages résolus par surface (le miroir)
# ----------------------------------------------------------------------------
# Le miroir sert à lire à travers une vitre sans tain, face caméra. Sur un écran
# de régie, qu'on lit directement, il rend le texte illisible à l'envers. La
# décision est prise côté serveur, à un endroit nommé, pour que le jour où un
# autre réglage devra diverger il suffise de remplir la même fonction.
# ============================================================================


def test_miroir_actif_sur_l_ecran_principal(client):
    client.post("/api/settings", json={"mirrorH": True, "mirrorV": True})
    s = client.get("/api/state?surface=display").get_json()["settings"]
    assert s["mirrorH"] is True
    assert s["mirrorV"] is True


def test_miroir_neutralise_sur_l_ecran_secondaire(client):
    client.post("/api/settings", json={"mirrorH": True, "mirrorV": True})
    s = client.get("/api/state?surface=view").get_json()["settings"]
    assert s["mirrorH"] is False
    assert s["mirrorV"] is False


def test_etat_sans_parametre_inchange(client):
    """La télécommande lit les réglages BRUTS : elle doit refléter les
    interrupteurs tels qu'ils sont, et la refonte des pédales relit cette même
    route pour confirmer un enregistrement."""
    client.post("/api/settings", json={"mirrorH": True})
    assert client.get("/api/state").get_json()["settings"]["mirrorH"] is True


def test_surface_inconnue_se_comporte_comme_l_ecran_principal(client):
    """Un paramètre mal orthographié ne doit jamais laisser un écran noir."""
    client.post("/api/settings", json={"mirrorH": True})
    s = client.get("/api/state?surface=nawak").get_json()["settings"]
    assert s["mirrorH"] is True


def test_les_autres_reglages_ne_sont_pas_touches(client):
    client.post("/api/settings", json={"fontSize": 96, "speed": 150, "mirrorH": True})
    s = client.get("/api/state?surface=view").get_json()["settings"]
    assert s["fontSize"] == 96
    assert s["speed"] == 150


# ============================================================================
# Une seule police
# ============================================================================


def test_seule_la_police_sans_est_acceptee(client):
    for refusee in ("serif", "monospace", "cursive"):
        client.post("/api/settings", json={"font": refusee})
        assert client.get("/api/state").get_json()["settings"]["font"] == "sans-serif", refusee


def test_state_json_avec_une_ancienne_police_se_repare(client, tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"settings": {"font": "serif"}}), encoding="utf-8")
    server.STATE_FILE = tmp_path / "state.json"
    assert server.load_state()["settings"]["font"] == "sans-serif"


# ============================================================================
# Import : le texte ne part plus tout seul à l'écran
# ----------------------------------------------------------------------------
# « Lorsqu'un texte est importé, il est envoyé à l'écran sans avoir cliqué sur
# Envoyer à l'écran, c'est étrange. » L'import remplit désormais la zone de
# saisie ; l'envoi reste un geste explicite.
#
# Le défaut du serveur reste pourtant l'ANCIEN comportement : un téléphone resté
# sur une page ouverte avant la mise à jour continue de fonctionner comme avant,
# au lieu de sembler ne plus rien faire.
# ============================================================================


def test_import_fichier_sans_apply_envoie_a_l_ecran(client):
    """Compatibilité : un client qui ne dit rien obtient l'ancien comportement."""
    client.post("/api/text", json={"text": "a l'antenne"})
    r = _upload(client, "Nouveau script".encode("utf-8"), "sujet.txt")
    assert r.get_json()["applied"] is True
    assert client.get("/api/state").get_json()["text"] == "Nouveau script"


def test_import_fichier_avec_apply_false_ne_touche_pas_l_ecran(client):
    client.post("/api/text", json={"text": "a l'antenne"})
    r = client.post(
        "/api/upload",
        data={"file": (io.BytesIO("Nouveau script".encode("utf-8")), "sujet.txt"), "apply": "false"},
        content_type="multipart/form-data",
        headers={server.CLIENT_HEADER: "1"},
    )
    corps = r.get_json()
    assert corps["applied"] is False
    assert corps["text"] == "Nouveau script"  # le client remplira sa zone lui-même
    assert corps["title"] == "sujet"
    assert client.get("/api/state").get_json()["text"] == "a l'antenne"


def test_alignement_accepte_seulement_centre_et_droite():
    """« left » est deja le comportement normal : une marque de plus pour rien."""
    marques = server.sanitize_marks(
        [
            {"start": 0, "end": 4, "align": "center"},
            {"start": 4, "end": 8, "align": "right"},
            {"start": 8, "end": 12, "align": "left"},
            {"start": 12, "end": 16, "align": "<script>"},
            {"start": 16, "end": 20, "align": 7},
        ],
        20,
    )
    assert [m.get("align") for m in marques] == ["center", "right"]


def test_upload_refuse_un_fichier_qui_n_est_pas_un_document(client):
    """Choisir une photo par erreur depuis le telephone doit donner un message,
    pas une zone de texte remplie d octets illisibles."""
    r = _upload(client, bytes([255, 216, 255, 224]) + bytes(range(256)), "photo.jpg")
    assert r.status_code == 400
    assert "Formats acceptés" in r.get_json()["error"]


def test_import_usb_avec_apply_false_ne_touche_pas_l_ecran(client, tmp_path, monkeypatch):
    cle = tmp_path / "cle"
    cle.mkdir()
    fichier = cle / "sujet.txt"
    fichier.write_text("Texte de la cle", encoding="utf-8")
    monkeypatch.setattr(server, "_usb_bases", lambda: [cle])
    client.post("/api/text", json={"text": "a l'antenne"})

    corps = client.post("/api/usb/load", json={"path": str(fichier), "apply": False}).get_json()
    assert corps["applied"] is False
    assert corps["text"] == "Texte de la cle"
    assert client.get("/api/state").get_json()["text"] == "a l'antenne"


def test_import_usb_sans_apply_envoie_a_l_ecran(client, tmp_path, monkeypatch):
    cle = tmp_path / "cle"
    cle.mkdir()
    fichier = cle / "sujet.txt"
    fichier.write_text("Texte de la cle", encoding="utf-8")
    monkeypatch.setattr(server, "_usb_bases", lambda: [cle])

    assert client.post("/api/usb/load", json={"path": str(fichier)}).get_json()["applied"] is True
    assert client.get("/api/state").get_json()["text"] == "Texte de la cle"


def test_valeurs_acceptees_pour_apply(client):
    for valeur, attendu in (("false", False), ("0", False), ("non", False), ("true", True), ("", True)):
        client.post("/api/text", json={"text": "reference"})
        r = client.post(
            "/api/upload",
            data={"file": (io.BytesIO(b"x"), "s.txt"), "apply": valeur},
            content_type="multipart/form-data",
            headers={server.CLIENT_HEADER: "1"},
        )
        assert r.get_json()["applied"] is attendu, valeur


# ============================================================================
# Pédalier à trois pédales et trois modes
# ============================================================================


def test_les_trois_modes_sont_acceptes(client):
    for mode in ("hold", "tap", "dyn"):
        client.post("/api/settings", json={"mode": mode})
        assert client.get("/api/state").get_json()["settings"]["mode"] == mode, mode


def test_mode_inconnu_refuse(client):
    client.post("/api/settings", json={"mode": "dynamique"})
    assert client.get("/api/state").get_json()["settings"]["mode"] == "hold"


def test_touche_de_la_pedale_centrale(client):
    client.post("/api/settings", json={"keyCenter": "F13"})
    assert client.get("/api/state").get_json()["settings"]["keyCenter"] == "F13"


def test_duree_de_montee_bornee(client):
    client.post("/api/settings", json={"rampSeconds": 4})
    assert client.get("/api/state").get_json()["settings"]["rampSeconds"] == 4
    for aberrant in (0, 31, -5, "vite", True):
        client.post("/api/settings", json={"rampSeconds": aberrant})
        assert client.get("/api/state").get_json()["settings"]["rampSeconds"] == 4, aberrant


def test_valeurs_par_defaut_du_pedalier(client):
    s = client.get("/api/state").get_json()["settings"]
    assert s["mode"] == "hold"
    assert s["rampSeconds"] == 10  # le client a demandé 10 s pour aller au maximum
    assert s["keyForward"] == "ArrowDown"
    assert s["keyBackward"] == "ArrowUp"
    assert s["keyCenter"] == "ArrowRight"


def test_state_json_avec_un_mode_obsolete_se_repare(client, tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"settings": {"mode": "impulsion"}}), encoding="utf-8")
    server.STATE_FILE = tmp_path / "state.json"
    assert server.load_state()["settings"]["mode"] == "hold"


# ============================================================================
# Mise en forme : gras / italique / souligné
# ----------------------------------------------------------------------------
# Le texte reste une CHAÎNE BRUTE ; la mise en forme est une liste de plages
# posées dessus. Jamais d'HTML stocké : pas d'injection possible sur l'écran, et
# un texte sans plages s'affiche exactement comme avant.
# ============================================================================


def test_plages_conservees_et_renvoyees(client):
    client.post(
        "/api/text",
        json={"text": "Bonjour le monde", "marks": [{"start": 8, "end": 16, "b": True}]},
    )
    etat = client.get("/api/state").get_json()
    assert etat["marks"] == [{"start": 8, "end": 16, "b": True}]
    assert etat["text"][8:16] == "le monde"


def test_plages_hors_bornes_rognees(client):
    client.post("/api/text", json={"text": "court", "marks": [{"start": -5, "end": 999, "i": True}]})
    assert client.get("/api/state").get_json()["marks"] == [{"start": 0, "end": 5, "i": True}]


def test_plages_invalides_ecartees(client):
    """Une mise en forme abîmée ne doit jamais empêcher d'afficher le texte."""
    client.post(
        "/api/text",
        json={
            "text": "Un texte lisible",
            "marks": [
                {"start": 5, "end": 5, "b": True},  # vide
                {"start": 3, "end": 1, "b": True},  # inversée
                {"start": 0, "end": 4},  # sans style
                {"start": "a", "end": "b", "b": True},  # non numérique
                "pas un objet",
                {"start": 0, "end": 2, "b": True},  # la seule valable
            ],
        },
    )
    etat = client.get("/api/state").get_json()
    assert etat["marks"] == [{"start": 0, "end": 2, "b": True}]
    assert etat["text"] == "Un texte lisible"


def test_marks_non_liste_ignore(client):
    client.post("/api/text", json={"text": "Bonjour", "marks": "gras"})
    assert client.get("/api/state").get_json()["marks"] == []


def test_nombre_de_plages_borne(client):
    trop = [{"start": i, "end": i + 1, "b": True} for i in range(600)]
    client.post("/api/text", json={"text": "x" * 700, "marks": trop})
    assert len(client.get("/api/state").get_json()["marks"]) <= server.MAX_MARKS


def test_import_efface_les_plages(client):
    """Nouveau texte : les anciennes plages ne désignent plus rien."""
    client.post("/api/text", json={"text": "Ancien", "marks": [{"start": 0, "end": 6, "b": True}]})
    _upload(client, "Tout autre texte".encode("utf-8"), "neuf.txt")
    assert client.get("/api/state").get_json()["marks"] == []


def test_bibliotheque_conserve_la_mise_en_forme(client):
    client.post(
        "/api/library/save",
        json={"name": "Sujet", "text": "Bonjour le monde", "marks": [{"start": 0, "end": 7, "u": True}]},
    )
    client.post("/api/text", json={"text": "autre chose"})
    client.post("/api/library/load", json={"name": "Sujet"})
    etat = client.get("/api/state").get_json()
    assert etat["text"] == "Bonjour le monde"
    assert etat["marks"] == [{"start": 0, "end": 7, "u": True}]


def test_bibliotheque_sans_mise_en_forme_reste_compatible(client):
    """Un .txt deposé à la main, sans fichier de plages : il doit se charger."""
    (server.SCRIPTS_DIR / "ancien.txt").write_text("Texte venu d'avant", encoding="utf-8")
    client.post("/api/library/load", json={"name": "ancien"})
    etat = client.get("/api/state").get_json()
    assert etat["text"] == "Texte venu d'avant"
    assert etat["marks"] == []


def test_reenregistrer_sans_mise_en_forme_efface_le_fichier(client):
    client.post(
        "/api/library/save",
        json={"name": "Sujet", "text": "Bonjour", "marks": [{"start": 0, "end": 3, "b": True}]},
    )
    client.post("/api/library/save", json={"name": "Sujet", "text": "Bonjour", "overwrite": True})
    client.post("/api/library/load", json={"name": "Sujet"})
    assert client.get("/api/state").get_json()["marks"] == []


def test_suppression_emporte_le_fichier_de_plages(client):
    client.post(
        "/api/library/save",
        json={"name": "Sujet", "text": "Bonjour", "marks": [{"start": 0, "end": 3, "b": True}]},
    )
    client.post("/api/library/delete", json={"name": "Sujet"})
    assert not list(server.SCRIPTS_DIR.glob("*.json"))


def test_state_json_avec_des_plages_aberrantes_se_repare(client, tmp_path):
    poison = {"text": "court", "marks": [{"start": 0, "end": 9999, "b": True}]}
    (tmp_path / "state.json").write_text(json.dumps(poison), encoding="utf-8")
    server.STATE_FILE = tmp_path / "state.json"
    assert server.load_state()["marks"] == [{"start": 0, "end": 5, "b": True}]


def test_la_liste_de_la_bibliotheque_n_expose_pas_les_fichiers_de_plages(client):
    client.post(
        "/api/library/save",
        json={"name": "Sujet", "text": "Bonjour", "marks": [{"start": 0, "end": 3, "b": True}]},
    )
    noms = [item["name"] for item in client.get("/api/library").get_json()]
    assert noms == ["Sujet"]


def test_taille_et_couleur_par_passage(client):
    client.post(
        "/api/text",
        json={
            "text": "Titre puis texte",
            "marks": [{"start": 0, "end": 5, "size": "xl", "color": 1}],
        },
    )
    assert client.get("/api/state").get_json()["marks"] == [{"start": 0, "end": 5, "size": "xl", "color": 1}]


def test_tailles_et_couleurs_hors_palette_refusees(client):
    """Palette fermee : un choix libre permettrait d ecrire en bleu marine sur
    noir, donc de rendre un passage invisible en tournage."""
    client.post(
        "/api/text",
        json={
            "text": "Un texte",
            "marks": [
                {"start": 0, "end": 2, "size": "enorme"},
                {"start": 2, "end": 4, "color": 99},
                {"start": 4, "end": 6, "color": "#000000"},
                {"start": 6, "end": 8, "size": "l"},
            ],
        },
    )
    assert client.get("/api/state").get_json()["marks"] == [{"start": 6, "end": 8, "size": "l"}]


# ============================================================================
# Points de vigilance de l'audit
# ============================================================================


def test_reglage_refuse_repond_400(client):
    """Avant, la reponse etait « ok » meme quand rien n'avait ete accepte : la
    telecommande colorait le bouton et l'on croyait avoir change de mode."""
    r = client.post("/api/settings", json={"mode": "pirate"})
    assert r.status_code == 400
    assert r.get_json()["refused"] == ["mode"]


def test_reglage_inconnu_refuse(client):
    r = client.post("/api/settings", json={"couleurDuCiel": "bleu"})
    assert r.status_code == 400
    assert "couleurDuCiel" in r.get_json()["refused"]


def test_les_reglages_valides_du_meme_envoi_sont_appliques(client):
    """On ne punit pas les reglages corrects a cause d'un voisin invalide."""
    r = client.post("/api/settings", json={"fontSize": 90, "mode": "pirate"})
    assert r.status_code == 400
    assert client.get("/api/state").get_json()["settings"]["fontSize"] == 90


def test_lecture_pause_ne_fait_pas_reteledecharger_le_texte(client):
    """cmdSeq suffit a propager la commande. Faire avancer la version obligerait
    chaque ecran a retelecharger tout le script a chaque appui sur Lecture."""
    avant = client.get("/api/version").get_json()
    for commande in ("play", "pause", "toggle", "restart", "top"):
        client.post("/api/command", json={"cmd": commande})
    apres = client.get("/api/version").get_json()
    assert apres["version"] == avant["version"]
    assert apres["cmdSeq"] == avant["cmdSeq"] + 5


def test_changer_la_vitesse_fait_bien_avancer_la_version(client):
    """Celles-la modifient reellement un reglage : les ecrans doivent le voir."""
    avant = client.get("/api/version").get_json()["version"]
    client.post("/api/command", json={"cmd": "faster"})
    assert client.get("/api/version").get_json()["version"] > avant


def test_entetes_de_securite_du_contenu(client):
    r = client.get("/display")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_pas_de_script_en_ligne_dans_les_pages(client):
    """La politique interdit les scripts ecrits dans la page : il ne doit donc
    plus en rester, sinon l'ecran ne demarrerait pas du tout."""
    import re as _re

    for chemin in ("/", "/display", "/view"):
        html = client.get(chemin).get_data(as_text=True)
        for balise in _re.findall(r"<script[^>]*>(.*?)</script>", html, _re.S):
            assert balise.strip() == "", chemin


def test_liste_usb_mise_en_cache(client, monkeypatch):
    """Le parcours disque ne doit pas etre relancable en boucle par n'importe
    quel appareil du WiFi."""
    appels = {"n": 0}

    def compte():
        appels["n"] += 1
        return []

    monkeypatch.setattr(server, "find_usb_text_files", compte)
    server._usb_cache["files"] = None
    for _ in range(5):
        client.get("/api/usb")
    assert appels["n"] == 1
