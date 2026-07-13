#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompteur — serveur du boîtier téléprompteur (Raspberry Pi).

Rôle :
  * Sert l'affichage du téléprompteur  ->  /display  (écran du boîtier, mode kiosque)
  * Sert la télécommande / import       ->  /        (ton téléphone, via le WiFi du boîtier)
  * Stocke le texte courant + les réglages dans state.json
  * Importe du texte depuis une clé USB branchée sur le boîtier

Aucune connexion internet n'est nécessaire : tout est local au boîtier.

Modèle d'accès : l'API n'a pas d'authentification applicative. C'est acceptable
UNIQUEMENT parce que le service est confiné au réseau du point d'accès WiFi isolé
du boîtier (voir le pare-feu posé par install/setup.sh qui limite le port au wlan0).

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
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# --------------------------------------------------------------------------
# Chemins et constantes
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"  # bibliothèque des textes enregistrés (.txt)
STATE_FILE = BASE_DIR / "state.json"  # texte courant + réglages + commandes
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
# Détection des clés USB (import de texte hors-ligne)
# --------------------------------------------------------------------------
USB_EXTS = (".txt", ".md", ".text", ".rtf")
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
    """Affichage du téléprompteur (écran du boîtier, mode kiosque)."""
    return render_template("display.html")


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
    """Sonde légère : l'affichage la lit toutes les 300 ms et ne télécharge le
    texte complet (/api/state) que si version ou cmdSeq a changé."""
    with _lock:
        return jsonify({"version": STATE["version"], "cmdSeq": STATE["control"]["cmdSeq"]})


@app.route("/api/text", methods=["POST"])
def api_text():
    data = request.get_json(force=True, silent=True) or {}
    with _lock:
        STATE["text"] = str(data.get("text", ""))
        if "title" in data:
            STATE["title"] = str(data.get("title") or "Sans titre")
        bump(STATE)
        _save_state_unlocked(STATE)
        version = STATE["version"]
    return jsonify({"ok": True, "version": version})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json(force=True, silent=True) or {}
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
    data = request.get_json(force=True, silent=True) or {}
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
    return jsonify({"ok": True, "cmdSeq": seq})


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
    data = request.get_json(force=True, silent=True) or {}
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


@app.route("/api/library/load")
def api_library_load():
    path = _library_path(request.args.get("name", ""))
    if path is None or not path.exists():
        return jsonify({"ok": False, "error": "introuvable"}), 404
    text = read_text_file(path)
    with _lock:
        STATE["text"] = text
        STATE["title"] = path.stem
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": path.stem})


@app.route("/api/library/delete", methods=["POST"])
def api_library_delete():
    data = request.get_json(force=True, silent=True) or {}
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
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("path", "")
    if not is_allowed_usb_file(path):
        return jsonify({"ok": False, "error": "fichier non autorisé"}), 400
    text = read_text_file(path)
    title = Path(path).stem
    with _lock:
        STATE["text"] = text
        STATE["title"] = title
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": title})


# --------------------------------------------------------------------------
# API — téléversement de fichier (.txt) depuis le téléphone
# --------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "aucun fichier"}), 400
    raw = file.read(MAX_FILE_SIZE)  # MAX_CONTENT_LENGTH a déjà borné le corps en amont
    text = raw.decode("utf-8", errors="replace")
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


@app.route("/api/info")
def api_info():
    return jsonify(
        {
            "addresses": local_ips(),
            "port": int(os.environ.get("PROMPTEUR_PORT", "5000")),
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
    port = int(os.environ.get("PROMPTEUR_PORT", "5000"))
    if os.environ.get("PROMPTEUR_DEBUG"):
        # mode développement uniquement (activé explicitement via PROMPTEUR_DEBUG)
        app.run(host=host, port=port, threaded=True, debug=True)  # nosec B201
    else:
        try:
            # serveur WSGI de production (robuste sur de longues sessions)
            from waitress import serve

            serve(app, host=host, port=port, threads=8, channel_timeout=60)
        except ImportError:
            # waitress absent (ex. poste de test) : repli sur le serveur Flask
            app.run(host=host, port=port, threaded=True)
