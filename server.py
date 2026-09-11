#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompteur — serveur du boîtier téléprompteur (Raspberry Pi).

Rôle :
  * Sert l'affichage du téléprompteur  ->  /display  (écran meneur, mode kiosque)
  * Sert l'affichage spectateur        ->  /view     (régie… suit le meneur en direct)
  * Sert la télécommande / import       ->  /        (ton téléphone, via le WiFi du boîtier)
  * Stocke le texte courant + les réglages dans state.json
  * Importe du texte (.txt/.md/.doc/.docx/.odt/.rtf/.pdf) depuis un fichier ou une clé USB
  * Partage en temps réel la position de défilement (meneur -> écrans spectateurs)

Aucune connexion internet n'est nécessaire : tout est local au boîtier.

Modèle d'accès : l'API n'a pas d'authentification applicative. C'est acceptable
UNIQUEMENT parce que le service est confiné au réseau du point d'accès WiFi isolé
du boîtier (voir le pare-feu posé par install/setup.sh qui limite le port au wlan0).
Ce confinement ne suffit toutefois pas seul : il ne protège pas d'une requête émise
par le navigateur d'un appareil déjà connecté à ce WiFi. Voir la protection anti-CSRF
(Origin + Content-Type) plus bas, verrouillée par les tests de tests/test_server.py.

Lancement :
    python server.py
Par défaut : http://0.0.0.0:5000  (waitress en production, serveur Flask si PROMPTEUR_DEBUG)
"""

import copy
import json
import os
import platform
import re
import socket
import string
import subprocess  # nosec B404 - script local du projet, arguments fixes, sans shell
import threading
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request

import textextract

# --------------------------------------------------------------------------
# Chemins et constantes
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"  # bibliothèque des textes enregistrés (.txt)
STATE_FILE = BASE_DIR / "state.json"  # texte courant + réglages + commandes
KIOSK_SCRIPT = BASE_DIR / "install" / "kiosk.sh"  # ouverture/fermeture de l'écran
SCRIPTS_DIR.mkdir(exist_ok=True)

MAX_BODY = 6 * 1024 * 1024  # taille max d'un corps de requête (protège RAM/disque)
MAX_FILE_SIZE = 5 * 1024 * 1024  # taille max d'un texte importé

# Verrou global pour toute lecture/écriture cohérente de STATE et de state.json
_lock = threading.Lock()

# État par défaut si state.json n'existe pas encore
DEFAULT_STATE = {
    "version": 1,  # incrémenté à chaque changement -> l'affichage détecte les MAJ
    "title": "Bienvenue",
    "text": (
        "Bienvenue sur ton prompteur.\n\n"
        "Depuis ton téléphone connecté au WiFi du boîtier, "
        "colle ton texte ici, puis appuie sur « Envoyer à l'écran ».\n\n"
        "Utilise les pédales pour faire défiler :\n"
        "pédale droite = avancer, pédale gauche = reculer.\n\n"
        "Bon tournage."
    ),
    "settings": {
        "fontSize": 64,  # taille du texte en px
        "lineHeight": 1.6,  # interligne
        "speed": 70,  # vitesse de lecture en px/seconde
        "textColor": "#ffffff",
        "bgColor": "#000000",
        "margin": 10,  # marge latérale en % de la largeur
        "mirrorH": False,  # miroir horizontal (vitre sans tain face caméra)
        "mirrorV": False,  # miroir vertical
        "guide": True,  # ligne de repère de lecture
        "guidePos": 42,  # position de la ligne de repère en % depuis le haut
        "align": "left",  # left | center
        "font": "sans-serif",  # sans-serif | serif | monospace
        "mode": "hold",  # "hold" (maintien) | "tap" (impulsion)
        # Touches envoyées par les pédales (personnalisables)
        "keyForward": "ArrowDown",  # pédale droite -> avancer
        "keyBackward": "ArrowUp",  # pédale gauche -> reculer
    },
    "control": {
        "playing": False,  # défilement auto en cours (info seulement)
        "cmd": None,  # commande ponctuelle: play|pause|toggle|restart|top|faster|slower
        "cmdSeq": 0,  # numéro de séquence: l'affichage applique chaque commande une seule fois
    },
}

# --------------------------------------------------------------------------
# Validation des réglages (le serveur fait autorité — ne pas se fier au client)
# --------------------------------------------------------------------------
_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")


def _num(lo, hi):
    def check(v):
        # on rejette explicitement les booléens (isinstance(True, int) est vrai en Python)
        return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi

    return check


SETTING_VALIDATORS = {
    "fontSize": _num(8, 400),
    "lineHeight": _num(0.8, 4),
    "speed": _num(10, 600),
    "margin": _num(0, 45),
    "guidePos": _num(0, 100),
    "textColor": lambda v: isinstance(v, str) and bool(_HEX6.match(v)),
    "bgColor": lambda v: isinstance(v, str) and bool(_HEX6.match(v)),
    "mirrorH": lambda v: isinstance(v, bool),
    "mirrorV": lambda v: isinstance(v, bool),
    "guide": lambda v: isinstance(v, bool),
    "align": lambda v: v in ("left", "center"),
    "font": lambda v: v in ("sans-serif", "serif", "monospace"),
    "mode": lambda v: v in ("hold", "tap"),
    "keyForward": lambda v: isinstance(v, str) and 1 <= len(v) <= 20,
    "keyBackward": lambda v: isinstance(v, str) and 1 <= len(v) <= 20,
}

SPEED_MIN, SPEED_MAX, SPEED_STEP = 10, 600, 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY  # rejette (413) tout corps > 6 Mo avant bufferisation


# --------------------------------------------------------------------------
# Protection contre les requêtes déclenchées depuis un autre site (CSRF)
# --------------------------------------------------------------------------
# L'API n'a pas d'authentification : la sécurité repose sur le confinement réseau
# (pare-feu limitant le port au wlan0 + WPA2). Ce confinement ne protège PAS d'une
# requête émise par le NAVIGATEUR d'un appareil déjà connecté au WiFi du boîtier :
# une page web piégée ouverte sur le téléphone du cadreur peut viser 10.42.0.1 sans
# la moindre interaction. Le pare-feu n'y voit rien, la requête part de l'intérieur.
#
# Deux barrières, sans aucune dépendance supplémentaire :
#   1. Origin — toute modification venant d'une autre origine est refusée (403).
#      Les navigateurs envoient cet en-tête sur toute requête POST inter-origines,
#      y compris les « simple requests » (text/plain, multipart) qui échappent au
#      pré-vol CORS. C'est la barrière qui compte.
#   2. Content-Type — les routes JSON n'acceptent que application/json (415).
#      Exiger ce type force un pré-vol CORS, auquel nous ne répondons jamais.
#
# Un client non-navigateur (curl, tests) n'envoie pas d'Origin : il reste accepté,
# car la CSRF est par définition une attaque menée par un navigateur.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Routes de modification qui ne reçoivent pas du JSON (envoi de fichier multipart).
NON_JSON_ROUTES = frozenset({"/api/upload"})
# En-tête maison exigé sur l'envoi de fichier : un en-tête personnalisé ne peut pas
# être posé par une page tierce sans pré-vol, ce qui protège la seule route de
# modification que la barrière Content-Type ne couvre pas.
CLIENT_HEADER = "X-Prompteur-Client"


def _cross_origin(value):
    """Vrai si l'en-tête fourni (Origin ou Referer) désigne une autre origine."""
    if not value:
        return False
    try:
        netloc = urlsplit(value).netloc
    except ValueError:
        return True  # en-tête illisible : on refuse plutôt que de deviner
    return netloc != request.host


@app.before_request
def _guard_state_changing_requests():
    if request.method in SAFE_METHODS:
        return None

    # 1. Origine de la requête. Referer en secours quand Origin est absent.
    if _cross_origin(request.headers.get("Origin")) or _cross_origin(request.headers.get("Referer")):
        return jsonify({"ok": False, "error": "origine refusée"}), 403

    # 2. Type de contenu.
    if request.path in NON_JSON_ROUTES:
        if not request.headers.get(CLIENT_HEADER):
            return jsonify({"ok": False, "error": "en-tête client manquant"}), 403
    elif not request.is_json:
        return jsonify({"ok": False, "error": "Content-Type application/json requis"}), 415

    return None


# --------------------------------------------------------------------------
# Lecture / écriture de l'état
# --------------------------------------------------------------------------
def _sanitize_settings(settings):
    """Répare un state.json corrompu : toute valeur invalide retombe au défaut."""
    clean = copy.deepcopy(DEFAULT_STATE["settings"])
    for key, value in settings.items():
        chk = SETTING_VALIDATORS.get(key)
        if chk and chk(value):
            clean[key] = value
    return clean


_TRUNCATED_NOTE = "\n\n[Texte tronqué : il dépassait ce que le prompteur peut afficher.]"


def _truncate_text(text):
    """Ramène un texte trop volumineux dans les bornes, sans jamais échouer.

    Utilisé au CHARGEMENT de state.json uniquement : à ce moment-là, refuser
    reviendrait à empêcher le boîtier de démarrer. Sur les entrées (API, import),
    c'est textextract.check_size qui refuse proprement, avec un message.
    """
    if not isinstance(text, str):
        return ""
    lines = text.split("\n")
    if len(lines) > textextract.MAX_TEXT_LINES:
        text = "\n".join(lines[: textextract.MAX_TEXT_LINES]) + _TRUNCATED_NOTE
    if len(text) > textextract.MAX_TEXT_CHARS:
        text = text[: textextract.MAX_TEXT_CHARS] + _TRUNCATED_NOTE
    return text


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = copy.deepcopy(DEFAULT_STATE)
            for k, v in data.items():
                if k not in ("settings", "control"):
                    merged[k] = v
            merged["settings"] = _sanitize_settings(data.get("settings", {}))
            merged["control"].update(data.get("control", {}))
            # Filet de dernier recours : si un texte démesuré a malgré tout été
            # enregistré (version antérieure, fichier modifié à la main), on le
            # tronque au chargement. Sans cela l'écran resterait figé À CHAQUE
            # DÉMARRAGE, et il faudrait un clavier et un terminal pour s'en sortir.
            merged["text"] = _truncate_text(merged.get("text", ""))
            return merged
        except (json.JSONDecodeError, OSError, TypeError, AttributeError):
            pass
    return copy.deepcopy(DEFAULT_STATE)


def _save_state_unlocked(state):
    """Écrit state.json de façon atomique. Le verrou _lock DOIT être détenu."""
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_FILE)


def bump(state):
    """Incrémente la version pour signaler un changement à l'affichage."""
    state["version"] = int(state.get("version", 0)) + 1
    return state


# On charge l'état une fois au démarrage (mono-thread ici, pas de verrou nécessaire).
STATE = load_state()


# --------------------------------------------------------------------------
# Temps réel : position de défilement partagée (meneur -> spectateurs)
# --------------------------------------------------------------------------
# Position du MENEUR (écran /display), lue très fréquemment par les spectateurs
# (/view) qui la SUIVENT avec anticipation (ils connaissent la vitesse et prédisent
# le mouvement entre deux lectures -> retard imperceptible). Mise à jour par POST,
# lue par GET, sur /api/scroll.
SCROLL = {"pos": 0.0, "vel": 0.0, "playing": False, "seq": 0}


# --------------------------------------------------------------------------
# Détection des clés USB (import de texte hors-ligne)
# --------------------------------------------------------------------------
USB_EXTS = textextract.SUPPORTED_EXTS  # .txt/.md/.rtf/.docx/.doc/.odt/.pdf
USB_MAX_TXT = 200  # nombre max de fichiers texte listés
USB_MAX_ENTRIES = 8000  # nombre max de fichiers PARCOURUS (borne le coût sur grosse clé)
USB_MAX_DEPTH = 6  # profondeur max de descente


def _usb_bases():
    """Racines où chercher les clés USB montées."""
    bases = []
    if platform.system() == "Windows":
        # Test sur PC : lettres de lecteur amovibles (hors C:)
        for letter in string.ascii_uppercase:
            if letter == "C":
                continue
            root = Path(f"{letter}:/")
            if root.exists():
                bases.append(root)
    else:
        # Raspberry Pi / Linux : points de montage habituels
        for base in ("/media", "/mnt"):
            p = Path(base)
            if p.exists():
                bases.append(p)
    return bases


def _dedupe(items):
    seen, unique = set(), []
    for item in items:
        if item["path"] not in seen:
            seen.add(item["path"])
            unique.append(item)
    return unique


def find_usb_text_files():
    """Liste (bornée) des fichiers texte des supports amovibles.

    Parcours borné en profondeur ET en nombre d'entrées pour rester réactif même
    sur une grosse clé pleine de médias. Les liens symboliques ne sont pas suivis
    (followlinks=False) et sont ignorés (protection contre la lecture hors clé)."""
    results, seen = [], 0
    for base in _usb_bases():
        base_depth = str(base).rstrip(os.sep + "/").count(os.sep)
        for dirpath, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
            depth = dirpath.count(os.sep) - base_depth
            if depth >= USB_MAX_DEPTH:
                dirnames[:] = []
            # on élague les dossiers cachés / système
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                seen += 1
                if seen > USB_MAX_ENTRIES:
                    return _dedupe(results)
                if not fn.lower().endswith(USB_EXTS):
                    continue
                full = os.path.join(dirpath, fn)
                if os.path.islink(full):
                    continue
                try:
                    if not os.path.isfile(full):
                        continue
                    size = os.path.getsize(full)
                except OSError:
                    continue
                if size > MAX_FILE_SIZE:
                    continue
                results.append({"name": fn, "path": full, "size": size})
                if len(results) >= USB_MAX_TXT:
                    return _dedupe(results)
    return _dedupe(results)


def is_allowed_usb_file(path):
    """Valide un chemin donné par le client SANS re-scanner la clé.

    Résout le chemin (déréférence les liens) puis exige qu'il reste CONFINÉ sous
    une base USB autorisée : un lien symbolique pointant hors de la clé, ou un
    chemin arbitraire (ex. /etc/passwd), est donc rejeté."""
    if not isinstance(path, str) or not path:
        return False
    try:
        rp = Path(path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    bases = []
    for b in _usb_bases():
        try:
            bases.append(b.resolve())
        except OSError:
            continue
    if not any(rp == b or b in rp.parents for b in bases):
        return False
    if rp.suffix.lower() not in USB_EXTS:
        return False
    try:
        return rp.is_file() and rp.stat().st_size <= MAX_FILE_SIZE
    except OSError:
        return False


def read_text_file(path):
    """Lit un fichier texte en essayant plusieurs encodages."""
    p = Path(path)
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    try:
        return p.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.route("/")
def index():
    """Télécommande + import (ouverte depuis le téléphone)."""
    return render_template("remote.html")


@app.route("/display")
def display():
    """Écran MENEUR (boîtier, kiosque) : piloté aux pédales, diffuse sa position."""
    return render_template("display.html", mode="presenter")


@app.route("/view")
def view():
    """Écran SPECTATEUR (régie…) : suit le meneur en temps réel, en lecture seule."""
    return render_template("display.html", mode="viewer")


# --------------------------------------------------------------------------
# API — état
# --------------------------------------------------------------------------
@app.route("/api/state")
def api_state():
    # snapshot cohérent sous verrou (évite de sérialiser un état muté par un autre thread)
    with _lock:
        snap = copy.deepcopy(STATE)
    return jsonify(snap)


@app.route("/api/version")
def api_version():
    """Sonde légère : les écrans la lisent régulièrement et ne retéléchargent le
    texte complet (/api/state) que si version ou cmdSeq a changé."""
    with _lock:
        return jsonify({"version": STATE["version"], "cmdSeq": STATE["control"]["cmdSeq"]})


@app.route("/api/scroll", methods=["GET", "POST"])
def api_scroll():
    """Position de défilement du MENEUR.
    GET  : lue très fréquemment par les spectateurs (/view) qui la suivent.
    POST : le meneur (/display) y pousse sa position. pos en px, vel en px/s."""
    if request.method == "GET":
        with _lock:
            return jsonify(dict(SCROLL))
    data = request.get_json(silent=True) or {}
    try:
        pos = max(0.0, min(1e7, float(data.get("pos", 0) or 0)))
        vel = max(-5000.0, min(5000.0, float(data.get("vel", 0) or 0)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "valeurs invalides"}), 400
    with _lock:
        SCROLL["pos"] = pos
        SCROLL["vel"] = vel
        SCROLL["playing"] = bool(data.get("playing"))
        SCROLL["seq"] += 1
        seq = SCROLL["seq"]
    return jsonify({"ok": True, "seq": seq})


@app.route("/api/text", methods=["POST"])
def api_text():
    data = request.get_json(silent=True) or {}
    try:
        text = textextract.check_size(str(data.get("text", "")))
    except ValueError as e:
        # Un texte demesure fige l'affichage, et le gel survit au redemarrage.
        return jsonify({"ok": False, "error": str(e)}), 400
    with _lock:
        STATE["text"] = text
        if "title" in data:
            STATE["title"] = str(data.get("title") or "Sans titre")
        bump(STATE)
        _save_state_unlocked(STATE)
        version = STATE["version"]
    return jsonify({"ok": True, "version": version})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json(silent=True) or {}
    with _lock:
        changed = False
        for key, value in data.items():
            chk = SETTING_VALIDATORS.get(key)
            if chk and chk(value):
                STATE["settings"][key] = value
                changed = True
        if changed:
            bump(STATE)
            _save_state_unlocked(STATE)
        settings = copy.deepcopy(STATE["settings"])
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/command", methods=["POST"])
def api_command():
    """Commande ponctuelle envoyée depuis le téléphone (play/pause/restart/...).

    L'état de pilotage est TRANSITOIRE : on ne l'écrit pas sur la carte SD (usure)."""
    data = request.get_json(silent=True) or {}
    cmd = data.get("cmd")
    allowed = {"play", "pause", "toggle", "restart", "top", "faster", "slower"}
    if cmd not in allowed:
        return jsonify({"ok": False, "error": "commande inconnue"}), 400
    with _lock:
        if cmd in ("faster", "slower"):
            # la vitesse est la source de vérité unique, bornée, côté serveur
            step = SPEED_STEP if cmd == "faster" else -SPEED_STEP
            cur = STATE["settings"].get("speed", 70)
            STATE["settings"]["speed"] = max(SPEED_MIN, min(SPEED_MAX, int(round(float(cur))) + step))
        STATE["control"]["cmd"] = cmd
        STATE["control"]["cmdSeq"] = int(STATE["control"].get("cmdSeq", 0)) + 1
        if cmd in ("play", "pause"):
            STATE["control"]["playing"] = cmd == "play"
        bump(STATE)  # en mémoire seulement, pas d'écriture disque
        seq = STATE["control"]["cmdSeq"]
        speed = STATE["settings"]["speed"]
    return jsonify({"ok": True, "cmdSeq": seq, "speed": speed})


# --------------------------------------------------------------------------
# API — bibliothèque de textes
# --------------------------------------------------------------------------
def safe_name(name):
    keep = "-_.() " + string.ascii_letters + string.digits + "àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ"
    cleaned = "".join(c for c in name if c in keep).strip()
    # on neutralise les noms « . » / « .. » qui, une fois suffixés, restent confinés
    # mais prêtent à confusion ; safe_name a déjà retiré les séparateurs / et \.
    return cleaned or "sans-titre"


def _library_path(name):
    """Chemin d'un texte de la bibliothèque, confiné à SCRIPTS_DIR."""
    path = SCRIPTS_DIR / f"{safe_name(name)}.txt"
    root = SCRIPTS_DIR.resolve()
    if root != path.resolve().parent:
        return None
    return path


@app.route("/api/library")
def api_library():
    items = []
    for path in sorted(SCRIPTS_DIR.glob("*.txt")):
        items.append({"name": path.stem, "size": path.stat().st_size})
    return jsonify(items)


@app.route("/api/library/save", methods=["POST"])
def api_library_save():
    data = request.get_json(silent=True) or {}
    raw = str(data.get("name") or STATE.get("title") or "sans-titre")
    name = safe_name(raw)
    text = str(data.get("text", STATE.get("text", "")))
    overwrite = bool(data.get("overwrite"))
    path = _library_path(name)
    if path is None:
        return jsonify({"ok": False, "error": "nom invalide"}), 400
    if path.exists() and not overwrite:
        # collision : on demande confirmation au lieu d'écraser en silence
        return jsonify({"ok": False, "error": "exists", "name": name, "sanitized": name != raw.strip()}), 409
    path.write_text(text, encoding="utf-8")
    return jsonify({"ok": True, "name": name, "sanitized": name != raw.strip()})


@app.route("/api/library/load", methods=["POST"])
def api_library_load():
    # POST et non GET : cette route MODIFIE le texte à l'antenne. Tant qu'elle
    # répondait en GET, une simple balise <img src=".../api/library/load?name=..."/>
    # posée sur une page tierce suffisait à changer le texte affiché en plein
    # tournage, sans que le pare-feu ni WPA2 puissent l'empêcher.
    data = request.get_json(silent=True) or {}
    path = _library_path(str(data.get("name", "")))
    if path is None or not path.exists():
        return jsonify({"ok": False, "error": "introuvable"}), 404
    try:
        text = textextract.check_size(read_text_file(path))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    with _lock:
        STATE["text"] = text
        STATE["title"] = path.stem
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": path.stem})


@app.route("/api/library/delete", methods=["POST"])
def api_library_delete():
    data = request.get_json(silent=True) or {}
    path = _library_path(str(data.get("name", "")))
    if path and path.exists():
        path.unlink()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# API — import clé USB
# --------------------------------------------------------------------------
@app.route("/api/usb")
def api_usb():
    return jsonify(find_usb_text_files())


@app.route("/api/usb/load", methods=["POST"])
def api_usb_load():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    if not is_allowed_usb_file(path):
        return jsonify({"ok": False, "error": "fichier non autorisé"}), 400
    try:
        raw = Path(path).read_bytes()
        text = textextract.extract_text(path, raw)
    except (OSError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    title = Path(path).stem
    with _lock:
        STATE["text"] = text
        STATE["title"] = title
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": title})


# --------------------------------------------------------------------------
# API — téléversement de fichier depuis le téléphone (.txt/.doc/.docx/.odt/.rtf/.pdf)
# --------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "aucun fichier"}), 400
    raw = file.read(MAX_FILE_SIZE)  # MAX_CONTENT_LENGTH a déjà borné le corps en amont
    try:
        text = textextract.extract_text(file.filename, raw)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    title = Path(file.filename).stem or "Import"
    with _lock:
        STATE["text"] = text
        STATE["title"] = title
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": title})


# --------------------------------------------------------------------------
# API — adresse(s) du boîtier
# --------------------------------------------------------------------------
def local_ips():
    """Adresses IP du boîtier, à taper sur un PC/tablette pour afficher le
    prompteur. L'IP du point d'accès WiFi (10.42.0.1) est prioritaire."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.42.0.1", 80))  # ne fait sortir aucune donnée : sert au routage
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips.add("10.42.0.1")
    clean = [ip for ip in ips if not ip.startswith("127.")]
    clean.sort(key=lambda x: (x != "10.42.0.1", x))
    return clean


def current_port():
    """Port d'écoute : PROMPTEUR_PORT (boîtier), sinon PORT (assigné par l'hôte), sinon 5000."""
    return int(os.environ.get("PROMPTEUR_PORT") or os.environ.get("PORT") or "5000")


# --------------------------------------------------------------------------
# API — ouverture et fermeture de l'écran du prompteur
# --------------------------------------------------------------------------
# Le prompteur devient une application qu'on ouvre et qu'on ferme, au lieu d'un
# mode dans lequel la machine démarre : plus besoin de « sudo reboot » pour y
# revenir. install/kiosk.sh reste la source unique (démarrage automatique, icône
# de bureau, et ces routes).
#
# AUCUN privilège n'est nécessaire : le serveur et le navigateur du kiosque
# tournent sous le même utilisateur. Rien à voir avec l'extinction de la machine,
# qui reste le bouton physique du boîtier.
#
# Joignables depuis TOUS les appareils du WiFi du boîtier, téléphone compris :
# c'est le choix assumé, pour pouvoir refermer ou relancer l'écran sans avoir à
# aller toucher le boîtier. Les garde-fous restent le pare-feu (port limité au
# wlan0) et la protection anti-CSRF ci-dessus. Côté interface, la barre est
# repliée par défaut et « Fermer » demande confirmation : depuis un téléphone, un
# appui involontaire couperait l'écran en pleine prise.


def _kiosk_env():
    """Environnement nécessaire pour ouvrir une fenêtre depuis le service systemd.

    DISPLAY désigne l'écran, XAUTHORITY porte l'autorisation de s'y connecter.
    Sans XAUTHORITY, Chromium est refusé par le serveur graphique et le lancement
    échoue SANS message — c'est le piège classique d'un programme graphique
    démarré depuis un service. Le service tourne sous le même utilisateur que la
    session graphique : son fichier d'autorisation est donc le bon.
    """
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    if "XAUTHORITY" not in env:
        candidates = [Path.home() / ".Xauthority"]
        # os.getuid n'existe pas sous Windows (poste de développement) : ce chemin
        # n'a de sens que sur le boîtier.
        if hasattr(os, "getuid"):
            candidates.append(Path(f"/run/user/{os.getuid()}/gdm/Xauthority"))
        for candidate in candidates:
            try:
                if candidate.exists():
                    env["XAUTHORITY"] = str(candidate)
                    break
            except OSError:
                continue
    env["PROMPTEUR_PORT"] = str(current_port())
    return env


def _kiosk(*args):
    """Appelle install/kiosk.sh. Renvoie (ok, code de retour)."""
    if not KIOSK_SCRIPT.exists():
        return False, None
    env = _kiosk_env()
    try:
        proc = subprocess.run(  # nosec B603 - chemin fixe du projet, pas de shell
            ["/bin/bash", str(KIOSK_SCRIPT), *args],
            env=env,
            capture_output=True,
            timeout=20,
            check=False,
        )
        return True, proc.returncode
    except (OSError, subprocess.SubprocessError):
        return False, None


def _kiosk_launch():
    """Lance le prompteur sans attendre : le script patiente jusqu'à ce que le
    serveur réponde, ce qui bloquerait la requête en cours."""
    if not KIOSK_SCRIPT.exists():
        return False
    env = _kiosk_env()
    try:
        subprocess.Popen(  # nosec B603 - chemin fixe du projet, pas de shell
            ["/bin/bash", str(KIOSK_SCRIPT)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


@app.route("/api/kiosk")
def api_kiosk():
    """État de l'écran du prompteur. « available » dit à la télécommande s'il
    faut afficher les boutons : inutile de les montrer sur un téléphone."""
    if not KIOSK_SCRIPT.exists():
        return jsonify({"available": False})
    ok, code = _kiosk("--status")
    # running = None quand l'etat n'a PAS pu etre determine (script non executable
    # ici, poste de developpement...). On affiche quand meme la barre : cacher la
    # fonction en silence ferait disparaitre un bouton cense exister, sans indice.
    return jsonify({"available": True, "running": (code == 0) if ok else None})


@app.route("/api/kiosk/close", methods=["POST"])
def api_kiosk_close():
    ok, _ = _kiosk("--stop")
    if not ok:
        return jsonify({"ok": False, "error": "script du kiosque introuvable"}), 500
    return jsonify({"ok": True, "running": False})


@app.route("/api/kiosk/launch", methods=["POST"])
def api_kiosk_launch():
    if not _kiosk_launch():
        return jsonify({"ok": False, "error": "script du kiosque introuvable"}), 500
    return jsonify({"ok": True})


@app.route("/api/info")
def api_info():
    return jsonify(
        {
            "addresses": local_ips(),
            "port": current_port(),
        }
    )


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


# --------------------------------------------------------------------------
# Démarrage
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # bind sur toutes les interfaces VOLONTAIRE : le pare-feu (install/setup.sh)
    # confine le port au WiFi du boîtier (wlan0). D'où le nosec B104.
    host = os.environ.get("PROMPTEUR_HOST", "0.0.0.0")  # nosec
    port = current_port()
    if os.environ.get("PROMPTEUR_DEBUG"):
        app.run(host=host, port=port, threaded=True, debug=True)  # nosec B201
    else:
        try:
            # serveur WSGI de production (robuste sur de longues sessions, multi-clients)
            from waitress import serve

            serve(app, host=host, port=port, threads=16, channel_timeout=120)
        except ImportError:
            # waitress absent (ex. poste de test) : repli sur le serveur Flask
            app.run(host=host, port=port, threaded=True)
