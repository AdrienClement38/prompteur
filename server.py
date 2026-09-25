#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompteur — serveur du boîtier téléprompteur (Raspberry Pi).

Rôle — trois vues, nommées d'après la personne qui les regarde :
  * Journaliste  ->  /journaliste  (écran meneur, piloté aux pédales, mode kiosque)
  * Spectateur   ->  /spectateur   (régie… suit le meneur en direct, lecture seule)
  * Settings     ->  /settings     (texte, réglages, commandes : téléphone, petit écran, PC)
  (les anciennes adresses /, /display, /view et /menu redirigent vers celles-ci)

Et aussi :
  * Stocke le texte courant + les réglages dans state.json
  * Importe du texte (.txt/.md/.doc/.docx/.odt/.rtf/.pdf) depuis un fichier ou une clé USB
  * Partage en temps réel la position de défilement (meneur -> écrans spectateurs)
  * Commande le grand écran du boîtier (vue affichée, veille)

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
import ipaddress
import json
import os
import platform
import socket
import string
import subprocess  # nosec B404 - script local du projet, arguments fixes, sans shell
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, redirect, render_template, request

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

# Compteur de modifications de la bibliothèque, DISTINCT de STATE["version"].
# Enregistrer ou supprimer un texte ne change ni le texte à l'antenne ni les
# réglages : faire avancer la version générale obligerait tous les écrans de
# lecture à retélécharger le script pour rien, en pleine prise. Les télécommandes
# surveillent donc ce compteur-là, et les écrans l'ignorent.
LIBRARY = {"seq": 0}

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
    # Mise en forme : des PLAGES sur le texte, jamais du HTML stocké.
    # Le texte reste une chaîne brute — c'est lui qui part dans les .txt de la
    # bibliothèque, qui borne la taille, et qui s'affiche si les marques sont
    # absentes ou invalides. Aucune régression possible sur un texte existant, et
    # aucun risque d'injection : l'écran construit ses éléments un par un.
    "marks": [],
    "settings": {
        "fontSize": 64,  # taille du texte en px
        "lineHeight": 1.6,  # interligne
        "speed": 70,  # vitesse de lecture en px/seconde
        # Plus de couleur de texte ni de fond : c'est TOUJOURS blanc sur noir, et
        # la couleur d'un passage se pose avec l'éditeur (plages « color »). Un
        # state.json portant encore textColor/bgColor est nettoyé au chargement.
        "margin": 10,  # marge latérale en % de la largeur
        "mirrorH": False,  # miroir horizontal (vitre sans tain face caméra)
        "mirrorV": False,  # miroir vertical
        "guide": True,  # ligne de repère de lecture
        "guidePos": 42,  # position de la ligne de repère en % depuis le haut
        "align": "left",  # left | center
        "font": "sans-serif",  # sans-serif | serif | monospace
        # "hold" (maintien) | "tap" (impulsion) | "dyn" (dynamique, 3 pédales)
        "mode": "hold",
        # Secondes d'appui continu pour atteindre la vitesse maximale, en mode
        # dynamique. C'est le seul réglage qui donne la sensation au pied : il
        # doit pouvoir s'ajuster sans toucher au code.
        "rampSeconds": 10,
        # Touches envoyées par les pédales (personnalisables)
        "keyForward": "ArrowDown",  # pédale droite -> avancer
        "keyBackward": "ArrowUp",  # pédale gauche -> reculer
        "keyCenter": "ArrowRight",  # pédale centrale -> lecture/pause (mode dynamique)
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
    "mirrorH": lambda v: isinstance(v, bool),
    "mirrorV": lambda v: isinstance(v, bool),
    "guide": lambda v: isinstance(v, bool),
    "align": lambda v: v in ("left", "center"),
    # Une seule police : les deux autres etaient illisibles sur un prompteur.
    # Un state.json portant encore "serif" ou "monospace" retombe au defaut.
    "font": lambda v: v == "sans-serif",
    "mode": lambda v: v in ("hold", "tap", "dyn"),
    "rampSeconds": _num(1, 30),
    "keyForward": lambda v: isinstance(v, str) and 1 <= len(v) <= 20,
    "keyBackward": lambda v: isinstance(v, str) and 1 <= len(v) <= 20,
    "keyCenter": lambda v: isinstance(v, str) and 1 <= len(v) <= 20,
}

SPEED_MIN, SPEED_MAX, SPEED_STEP = 10, 600, 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY  # rejette (413) tout corps > 6 Mo avant bufferisation
TROP_GROS = "Fichier trop volumineux : 5 Mo au maximum. Enregistrez-le en .docx, sans images."


@app.errorhandler(413)
def _trop_gros(_erreur):
    """Au-delà de 6 Mo, Flask répondait une page HTML : le téléphone ne pouvait
    afficher qu'« Import impossible ». On répond en JSON, avec la raison."""
    return jsonify({"ok": False, "error": TROP_GROS}), 413


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


def _corps():
    """Corps JSON de la requête, TOUJOURS un dictionnaire.

    « [1, 2] » ou « "texte" » sont du JSON valide : sans ce garde-fou, le premier
    .get() levait une exception, et le client recevait une erreur 500 muette.
    """
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# Noms sous lesquels on joint le boîtier. Le rebond DNS (« DNS rebinding ») fait
# pointer un nom de domaine d'Internet vers 10.42.0.1 : la page piégée devient alors
# « de la même origine » que le boîtier, et la barrière Origin ne voit plus rien.
# Ce nom-là, en revanche, reste dans l'en-tête Host. On n'accepte donc qu'une
# adresse IP, un nom sans point (localhost, prompteur) ou un nom de réseau local.
_SUFFIXES_LOCAUX = (".local", ".lan", ".home", ".home.arpa", ".internal")


def _hote_de_confiance(host):
    try:
        nom = (urlsplit("//" + host).hostname or "").lower()
    except ValueError:
        return False
    if not nom:
        return False
    try:
        ipaddress.ip_address(nom)
        return True
    except ValueError:
        pass
    return "." not in nom or nom.endswith(_SUFFIXES_LOCAUX)


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

    # 0. Le nom sous lequel on a joint le boîtier (voir _hote_de_confiance).
    if not _hote_de_confiance(request.host):
        return jsonify({"ok": False, "error": "adresse du boîtier inattendue"}), 403

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
MAX_MARKS = 500  # au-delà, c'est un document, pas une mise en évidence

# Tailles RELATIVES et non en pixels : un passage mis en avant doit le rester
# quand on change la taille générale du texte pour s'éloigner de l'écran.
MARK_SIZES = ("s", "l", "xl")
# Palette FERMÉE, toutes lisibles sur fond sombre. Un choix libre permettrait
# d'écrire en bleu marine sur noir, donc de rendre un passage invisible en
# tournage — au moment précis où l'on comptait sur lui.
MARK_COLORS = (1, 2, 3, 4, 5)
# L'alignement vient des documents importes. Il porte sur la LIGNE entiere, pas sur
# des caracteres : l'ecran le lit au premier caractere de la ligne. « left » n'est pas
# de la liste, c'est deja le comportement normal — une marque de plus pour rien.
MARK_ALIGNS = ("center", "right")


def sanitize_marks(marks, length):
    """Ne garde que des plages valides et confinées au texte.

    Une plage hors bornes, vide, mal formée ou sans style est simplement écartée :
    l'écran doit toujours pouvoir afficher le texte, même si la mise en forme qui
    l'accompagne est abîmée.
    """
    if not isinstance(marks, list):
        return []
    clean = []
    for mark in marks[:MAX_MARKS]:
        if not isinstance(mark, dict):
            continue
        try:
            start = int(mark.get("start", -1))
            end = int(mark.get("end", -1))
        except (TypeError, ValueError):
            continue
        start = max(0, min(length, start))
        end = max(0, min(length, end))
        if end <= start:
            continue
        styles = {key: True for key in ("b", "i", "u") if mark.get(key) is True}
        taille = mark.get("size")
        if taille in MARK_SIZES:
            styles["size"] = taille
        try:
            couleur = int(mark.get("color"))
        except (TypeError, ValueError):
            couleur = None
        if couleur in MARK_COLORS:
            styles["color"] = couleur
        if mark.get("align") in MARK_ALIGNS:
            styles["align"] = mark["align"]
        if not styles:
            continue
        clean.append({"start": start, "end": end, **styles})
    return clean


def longueur_js(texte):
    """Longueur du texte telle que la compte JavaScript (unités UTF-16).

    Les plages sont des indices JAVASCRIPT : c'est l'éditeur du téléphone et
    l'écran de lecture qui les posent et les appliquent. Un emoji y compte pour
    deux, contre un seul en Python.
    """
    return len(texte) + sum(1 for c in texte if ord(c) > 0xFFFF)


def plages_en_unites_js(texte, marques):
    """Plages calculées en Python (import) -> plages en unités JavaScript.

    Sans cette conversion, chaque emoji placé avant un passage décalait sa mise en
    forme d'une lettre à l'écran.
    """
    if not marques or all(ord(c) <= 0xFFFF for c in texte):
        return marques
    cumul = [0] * (len(texte) + 1)
    for i, c in enumerate(texte):
        cumul[i + 1] = cumul[i] + (2 if ord(c) > 0xFFFF else 1)
    return [{**m, "start": cumul[m["start"]], "end": cumul[m["end"]]} for m in marques]


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
            merged["marks"] = sanitize_marks(merged.get("marks"), longueur_js(merged["text"]))
            return merged
        # ValueError couvre aussi un octet non UTF-8 (UnicodeDecodeError) : sans lui,
        # une seule lettre abîmée par une coupure de courant empêchait le service
        # de démarrer, et le boîtier restait noir à chaque allumage.
        except (ValueError, OSError, TypeError, AttributeError):
            pass
    return copy.deepcopy(DEFAULT_STATE)


def _save_state_unlocked(state):
    """Écrit state.json de façon atomique. Le verrou _lock DOIT être détenu.

    flush + fsync AVANT le renommage : le renommage est atomique, mais sans cette
    synchronisation les données du fichier temporaire peuvent n'être pas encore
    sur la carte au moment d'une coupure de courant. On retrouve alors un JSON
    tronqué, que load_state() écarte EN SILENCE — le journaliste rallume et
    retrouve le texte de bienvenue, sans la moindre explication.
    """
    tmp = STATE_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(STATE_FILE)
    except OSError as e:
        # On ne bloque pas le direct pour autant (le texte reste en mémoire), mais
        # l'échec doit laisser une trace : carte pleine ou en lecture seule.
        print(f"Prompteur : impossible d'enregistrer {STATE_FILE.name} : {e}", file=sys.stderr, flush=True)


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
SCROLL = {
    "pos": 0.0,
    "vel": 0.0,
    "playing": False,
    "seq": 0,
    "ligne": None,
    "frac": 0.0,
    "h": 0.0,
    "largeur": 0,
    "hauteur": 0,
}

# Veille du système : tous les écrans passent au noir, le grand écran est éteint.
# État TRANSITOIRE, jamais écrit sur la carte : un boîtier qu'on rallume doit
# toujours se réveiller allumé, jamais noir sans raison apparente.
VEILLE = {"on": False}


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
                # « ._Sujet.docx » (Mac) et « ~$Sujet.docx » (Word ouvert) ne sont
                # pas des documents : ils s'affichaient à côté du vrai, et leur
                # chargement échouait.
                if fn.startswith((".", "~$")):
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
                # Trop lourd : listé quand même, et signalé. Le faire disparaître en
                # silence faisait croire que la clé n'était pas lue.
                results.append({"name": fn, "path": full, "size": size, "tropGros": size > MAX_FILE_SIZE})
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
@app.route("/settings")
def settings_page():
    """Settings : texte, réglages et commandes (téléphone, petit écran, PC de régie)."""
    return render_template("remote.html")


@app.route("/journaliste")
def journaliste():
    """Vue JOURNALISTE (grand écran, kiosque) : pilotée aux pédales, diffuse sa position."""
    return render_template("display.html", mode="presenter")


@app.route("/spectateur")
def spectateur():
    """Vue SPECTATEUR (régie…) : suit le journaliste en temps réel, en lecture seule."""
    return render_template("display.html", mode="viewer")


# Anciennes adresses : elles restent valables. Un favori, une adresse notée sur
# une fiche, ou un kiosque lancé avant la mise à jour ne doivent jamais tomber
# sur une erreur. Redirection TEMPORAIRE (302) : un navigateur ne la mémorise
# pas, on reste libre de changer d'avis. La chaîne de requête suit.
ANCIENNES_ADRESSES = {
    "/": "/settings",
    "/menu": "/settings",  # l'ancien « tableau de bord », remplacé par Settings
    "/display": "/journaliste",
    "/view": "/spectateur",
}


def _ancienne_adresse():
    cible = ANCIENNES_ADRESSES[request.path]
    requete = request.query_string.decode("utf-8", "replace")
    return redirect(cible + ("?" + requete if requete else ""), code=302)


for _chemin in ANCIENNES_ADRESSES:
    app.add_url_rule(_chemin, "ancienne" + _chemin.replace("/", "_"), _ancienne_adresse)


# --------------------------------------------------------------------------
# API — état
# --------------------------------------------------------------------------
@app.route("/api/state")
def api_state():
    # snapshot cohérent sous verrou (évite de sérialiser un état muté par un autre thread)
    with _lock:
        snap = copy.deepcopy(STATE)
    # Sans paramètre, la réponse reste EXACTEMENT celle d'avant : c'est ce que lit
    # la télécommande, qui doit voir les réglages bruts pour les refléter.
    surface = request.args.get("surface", "")
    if surface:
        snap["settings"] = effective_settings(snap["settings"], surface)
    return jsonify(snap)


@app.route("/api/version")
def api_version():
    """Sonde légère : les écrans la lisent régulièrement et ne retéléchargent le
    texte complet (/api/state) que si version ou cmdSeq a changé."""
    with _lock:
        return jsonify(
            {
                "version": STATE["version"],
                "cmdSeq": STATE["control"]["cmdSeq"],
                "libSeq": LIBRARY["seq"],
                "veille": VEILLE["on"],
            }
        )


@app.route("/api/scroll", methods=["GET", "POST"])
def api_scroll():
    """Position de défilement du MENEUR.
    GET  : lue très fréquemment par les spectateurs (/spectateur) qui la suivent.
    POST : la vue Journaliste y pousse sa position. pos en px, vel en px/s.

    ligne / frac / h : la même position, exprimée dans le TEXTE — la ligne qui
    passe sous la ligne rouge, la fraction de cette ligne déjà passée, et sa
    hauteur en pixels. C'est elle que suit la vue Spectateur : sur un écran d'une
    autre taille, les lignes ne se coupent pas au même endroit, et une position
    en pixels désignait un autre passage."""
    if request.method == "GET":
        with _lock:
            return jsonify(dict(SCROLL))
    data = _corps()
    try:
        pos = max(0.0, min(1e7, float(data.get("pos", 0) or 0)))
        vel = max(-5000.0, min(5000.0, float(data.get("vel", 0) or 0)))
        ligne = data.get("ligne")
        ligne = (
            max(0, min(10**6, int(ligne))) if isinstance(ligne, (int, float)) and not isinstance(ligne, bool) else None
        )
        frac = max(-1000.0, min(1000.0, float(data.get("frac", 0) or 0)))
        hauteur = max(0.0, min(1e5, float(data.get("h", 0) or 0)))
        # Dimensions de l'écran du journaliste : la vue Spectateur en fait une
        # réplique à l'échelle. 0 = inconnues (écran d'une version antérieure).
        ecran_l = int(max(0.0, min(20000.0, float(data.get("largeur", 0) or 0))))
        ecran_h = int(max(0.0, min(20000.0, float(data.get("hauteur", 0) or 0))))
    except (TypeError, ValueError, OverflowError):
        return jsonify({"ok": False, "error": "valeurs invalides"}), 400
    with _lock:
        SCROLL["pos"] = pos
        SCROLL["vel"] = vel
        SCROLL["ligne"] = ligne
        SCROLL["frac"] = frac
        SCROLL["h"] = hauteur
        SCROLL["largeur"] = ecran_l
        SCROLL["hauteur"] = ecran_h
        SCROLL["playing"] = bool(data.get("playing"))
        SCROLL["seq"] += 1
        seq = SCROLL["seq"]
    return jsonify({"ok": True, "seq": seq})


@app.route("/api/text", methods=["POST"])
def api_text():
    data = _corps()
    if "text" not in data:
        # Une requête sans texte ne doit JAMAIS vider l'écran à l'antenne.
        return jsonify({"ok": False, "error": "texte manquant"}), 400
    try:
        text = textextract.check_size(str(data.get("text", "")))
    except ValueError as e:
        # Un texte demesure fige l'affichage, et le gel survit au redemarrage.
        return jsonify({"ok": False, "error": str(e)}), 400
    marks = sanitize_marks(data.get("marks"), longueur_js(text))
    with _lock:
        STATE["text"] = text
        STATE["marks"] = marks
        if "title" in data:
            STATE["title"] = str(data.get("title") or "Sans titre")
        bump(STATE)
        _save_state_unlocked(STATE)
        version = STATE["version"]
    return jsonify({"ok": True, "version": version})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = _corps()
    with _lock:
        changed = False
        refuses = []
        for key, value in data.items():
            chk = SETTING_VALIDATORS.get(key)
            if chk and chk(value):
                STATE["settings"][key] = value
                changed = True
            else:
                refuses.append(key)
        if changed:
            bump(STATE)
            _save_state_unlocked(STATE)
        settings = copy.deepcopy(STATE["settings"])
    # Un réglage refusé DOIT le dire. Jusqu'ici la réponse était « ok » même quand
    # rien n'avait été accepté : la télécommande colorait le bouton, et l'on
    # croyait avoir change de mode alors que rien n'avait bouge. Les reglages
    # valides du meme envoi sont quand meme appliques — on ne punit pas le reste.
    if changed and ("mirrorH" in data or "mirrorV" in data):
        with _kiosk_lock:
            _miroir_hors_prompteur()
    if refuses:
        return jsonify({"ok": False, "error": "réglage refusé", "refused": refuses, "settings": settings}), 400
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/command", methods=["POST"])
def api_command():
    """Commande ponctuelle envoyée depuis le téléphone (play/pause/restart/...).

    L'état de pilotage est TRANSITOIRE : on ne l'écrit pas sur la carte SD (usure)."""
    data = _corps()
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
        # On ne fait avancer la version QUE si un réglage a réellement changé.
        # cmdSeq suffit à propager la commande ; faire avancer la version
        # obligerait chaque écran à retélécharger TOUT le script à chaque appui
        # sur Lecture ou Pause — plusieurs mégaoctets sur le WiFi du boîtier, pour
        # rien, au moment précis où l'on a besoin de réactivité.
        if cmd in ("faster", "slower"):
            # La vitesse est un réglage comme les autres : elle doit survivre à
            # l'extinction, comme celle posée au curseur ou au pied. Un appui
            # de temps en temps, ce n'est pas ce qui use une carte mémoire.
            bump(STATE)
            _save_state_unlocked(STATE)
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


def _library_marks_path(path):
    """Fichier des plages, frere du .txt. Hors du glob *.txt de la bibliotheque,
    donc invisible dans la liste et sans effet sur les anciens textes."""
    return path.with_suffix(".marks.json")


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
    data = _corps()
    raw = str(data.get("name") or STATE.get("title") or "sans-titre")
    name = safe_name(raw)
    try:
        # La même borne qu'au chargement : sinon on enregistrait un texte que
        # « Charger » refusait ensuite.
        text = textextract.check_size(str(data.get("text", STATE.get("text", ""))))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    overwrite = bool(data.get("overwrite"))
    path = _library_path(name)
    if path is None:
        return jsonify({"ok": False, "error": "nom invalide"}), 400
    if path.exists() and not overwrite:
        # collision : on demande confirmation au lieu d'écraser en silence
        return jsonify({"ok": False, "error": "exists", "name": name, "sanitized": name != raw.strip()}), 409
    path.write_text(text, encoding="utf-8")
    marques = sanitize_marks(data.get("marks"), longueur_js(text))
    chemin_marques = _library_marks_path(path)
    if marques:
        chemin_marques.write_text(json.dumps(marques), encoding="utf-8")
    elif chemin_marques.exists():
        chemin_marques.unlink()  # texte reenregistre sans mise en forme
    with _lock:
        LIBRARY["seq"] += 1
    return jsonify({"ok": True, "name": name, "sanitized": name != raw.strip()})


@app.route("/api/library/load", methods=["POST"])
def api_library_load():
    # POST et non GET : cette route MODIFIE le texte à l'antenne. Tant qu'elle
    # répondait en GET, une simple balise <img src=".../api/library/load?name=..."/>
    # posée sur une page tierce suffisait à changer le texte affiché en plein
    # tournage, sans que le pare-feu ni WPA2 puissent l'empêcher.
    data = _corps()
    path = _library_path(str(data.get("name", "")))
    if path is None or not path.exists():
        return jsonify({"ok": False, "error": "introuvable"}), 404
    try:
        text = textextract.check_size(read_text_file(path))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not text and path.stat().st_size > 0:
        # Lecture ratée (carte abîmée) : surtout ne pas mettre un écran VIDE à
        # l'antenne en répondant « ok ».
        return jsonify({"ok": False, "error": "lecture du texte impossible"}), 500
    marques = []
    chemin_marques = _library_marks_path(path)
    if chemin_marques.exists():
        try:
            marques = sanitize_marks(json.loads(chemin_marques.read_text(encoding="utf-8")), longueur_js(text))
        except (OSError, ValueError):
            marques = []  # mise en forme abimee : on affiche le texte quand meme
    with _lock:
        STATE["text"] = text
        STATE["marks"] = marques
        STATE["title"] = path.stem
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": path.stem})


@app.route("/api/library/delete", methods=["POST"])
def api_library_delete():
    data = _corps()
    path = _library_path(str(data.get("name", "")))
    if path and path.exists():
        path.unlink()
        marques = _library_marks_path(path)
        if marques.exists():
            marques.unlink()
        with _lock:
            LIBRARY["seq"] += 1
    return jsonify({"ok": True})


def _mise_en_forme_tronquee(marques):
    """La mise en forme d'un très long document a-t-elle été écrêtée ?

    Le plafond de 500 plages protège l'affichage : le calcul du style est quadratique
    en nombre de plages, et un Pi n'y survivrait pas au-delà. Mais un plafond qui
    s'applique en SILENCE ferait croire que la fin du document n'était pas mise en
    forme. On le dit donc, plutôt que de laisser conclure à un import raté.
    """
    return len(marques) >= MAX_MARKS


def _wants_apply(value):
    """Faut-il envoyer le texte importé directement à l'écran ?

    Par défaut OUI, et ce défaut est capital : un téléphone resté sur l'ancienne
    page pendant une mise à jour continuerait de fonctionner comme avant, au lieu
    de sembler ne plus rien faire. Les clients à jour demandent explicitement
    apply=false et remplissent leur zone de texte.
    """
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "non", "no")


# --------------------------------------------------------------------------
# API — import clé USB
# --------------------------------------------------------------------------
# Le parcours des clés USB visite jusqu'à 8 000 entrées sur six niveaux. La route
# n'a pas d'authentification : sans garde-fou, n'importe quel appareil du WiFi
# peut la rappeler en boucle et occuper le disque du boîtier en pleine lecture.
# Un résultat de quelques secondes suffit largement : on branche une clé, on
# appuie sur « Clé USB », on charge.
_usb_cache = {"at": 0.0, "files": None}
USB_CACHE_TTL = 3.0


@app.route("/api/usb")
def api_usb():
    maintenant = time.monotonic()
    with _lock:
        frais = _usb_cache["files"] is not None and maintenant - _usb_cache["at"] < USB_CACHE_TTL
        if frais:
            return jsonify(_usb_cache["files"])
    files = find_usb_text_files()
    with _lock:
        _usb_cache["at"] = time.monotonic()
        _usb_cache["files"] = files
    return jsonify(files)


@app.route("/api/usb/load", methods=["POST"])
def api_usb_load():
    data = _corps()
    path = data.get("path", "")
    try:
        trop_gros = isinstance(path, str) and os.path.getsize(path) > MAX_FILE_SIZE
    except (OSError, ValueError):
        trop_gros = False
    if trop_gros:
        return jsonify({"ok": False, "error": TROP_GROS}), 400
    if not is_allowed_usb_file(path):
        return jsonify({"ok": False, "error": "fichier non autorisé"}), 400
    try:
        raw = Path(path).read_bytes()
        text, marques = textextract.extract_rich(path, raw)
    except (OSError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    marques = plages_en_unites_js(text, sanitize_marks(marques, len(text)))
    title = Path(path).stem
    if not _wants_apply(data.get("apply")):
        # Le client remplira lui-même sa zone de texte : rien ne part à l'écran.
        return jsonify(
            {
                "ok": True,
                "title": title,
                "text": text,
                "marks": marques,
                "applied": False,
                "marksTruncated": _mise_en_forme_tronquee(marques),
            }
        )
    with _lock:
        STATE["text"] = text
        STATE["title"] = title
        STATE["marks"] = marques  # le gras du document importé suit le texte
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": title, "applied": True})


# --------------------------------------------------------------------------
# API — téléversement de fichier depuis le téléphone (.txt/.doc/.docx/.odt/.rtf/.pdf)
# --------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "aucun fichier"}), 400
    raw = file.read(MAX_FILE_SIZE + 1)
    if len(raw) > MAX_FILE_SIZE:
        # On lisait les 5 premiers Mo et l'on continuait : la fin du texte
        # disparaissait sans un mot. Mieux vaut refuser en le disant.
        return jsonify({"ok": False, "error": TROP_GROS}), 400
    try:
        text, marques = textextract.extract_rich(file.filename, raw)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    marques = plages_en_unites_js(text, sanitize_marks(marques, len(text)))
    title = Path(file.filename).stem or "Import"
    if not _wants_apply(request.form.get("apply")):
        # Le client remplira lui-meme sa zone de texte : rien ne part a l'ecran.
        return jsonify(
            {
                "ok": True,
                "title": title,
                "text": text,
                "marks": marques,
                "applied": False,
                "marksTruncated": _mise_en_forme_tronquee(marques),
            }
        )
    with _lock:
        STATE["text"] = text
        STATE["title"] = title
        STATE["marks"] = marques  # le gras du document importé suit le texte
        bump(STATE)
        _save_state_unlocked(STATE)
    return jsonify({"ok": True, "title": title, "applied": True})


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
# Réglages résolus selon la surface d'affichage
# --------------------------------------------------------------------------
# Certains réglages n'ont de sens que sur l'écran principal. Le miroir en est le
# premier cas : il sert à lire à travers une vitre sans tain, face caméra. Sur un
# écran de régie, qu'on lit directement, il rend le texte illisible à l'envers.
#
# La décision est prise ICI, à un endroit nommé, et non dans un « if » noyé au
# milieu du rendu. Le jour où un deuxième réglage devra diverger — le client parle
# déjà de tailles et de couleurs — il suffira de remplir cette fonction, sans
# toucher aux écrans. C'est ce que le client appelle « futur proof ».
#
# Les surfaces inconnues retombent sur le comportement de l'écran principal : un
# paramètre mal orthographié ne doit jamais laisser un écran noir.
SURFACE_OVERRIDES = {
    "view": {"mirrorH": False, "mirrorV": False},
}


def effective_settings(settings, surface):
    """Réglages tels que la surface demandée doit les appliquer."""
    overrides = SURFACE_OVERRIDES.get(surface)
    if not overrides:
        return settings
    resolved = dict(settings)
    resolved.update(overrides)
    return resolved


# --------------------------------------------------------------------------
# Réservation de l'écran principal (un seul meneur à la fois)
# --------------------------------------------------------------------------
# Deux écrans principaux se disputeraient le pilotage : chacun pousse sa position
# de défilement sur /api/scroll, et le texte sauterait d'un endroit à l'autre en
# pleine lecture.
#
# BAIL À RENOUVELER, et non verrou. Un verrou qu'on oublie de rendre — onglet
# fermé brutalement, WiFi coupé, boîtier redémarré — condamnerait le prompteur,
# c'est-à-dire exactement l'inverse du but recherché. Ici le bail expire tout seul
# au bout de PRESENTER_TTL secondes sans signe de vie, et une reprise en main
# forcée reste TOUJOURS possible. On ne doit jamais pouvoir s'enfermer dehors.
PRESENTER_TTL = 12.0  # secondes sans battement avant de considérer la place libre
# La cle s'appelle « holder » et non « token » : bandit signale toute cle nommee
# token/password/secret comme un mot de passe en dur, et il sort en erreur des la
# moindre alerte, meme de severite faible. Renommer supprime le faux positif a la
# source, ce qui vaut mieux que de museler le controle.
_presenter = {"holder": None, "seen": 0.0, "kiosk": False}


def _depuis_le_boitier():
    """Vrai si la requête vient du boîtier lui-même (kiosque, petit écran)."""
    return request.remote_addr in ("127.0.0.1", "::1")


def _prendre_la_place(token):
    """Donne la place de meneur à ce jeton. Verrou requis.

    On retient si le meneur est le kiosque du boîtier : c'est le seul que le
    serveur ferme lui-même (changement de vue du grand écran), et il doit alors
    rendre la place aussitôt. Sinon le kiosque relancé trouverait la place prise
    par son propre fantôme, et afficherait « écran déjà en cours » à sa place.
    """
    _presenter["holder"] = token
    _presenter["seen"] = time.monotonic()
    _presenter["kiosk"] = _depuis_le_boitier()


def _liberer_la_place_du_kiosque():
    """Rend la place si c'est le kiosque qui la tient. Verrou requis."""
    if _presenter["kiosk"]:
        _presenter["holder"] = None
        _presenter["seen"] = 0.0
        _presenter["kiosk"] = False


def _presenter_holder():
    """Jeton du meneur en place, ou None si la place est libre. Verrou requis."""
    token = _presenter["holder"]
    if not token:
        return None
    if time.monotonic() - _presenter["seen"] > PRESENTER_TTL:
        return None
    return token


@app.route("/api/presenter")
def api_presenter():
    """Qui tient l'écran principal ? Le jeton n'est jamais divulgué : on répond
    seulement si la place est prise, et si c'est celui qui demande."""
    mine = request.args.get("token", "")
    with _lock:
        holder = _presenter_holder()
    return jsonify({"taken": holder is not None, "mine": bool(holder) and holder == mine})


@app.route("/api/presenter/claim", methods=["POST"])
def api_presenter_claim():
    data = _corps()
    token = str(data.get("token") or "")[:64]
    if not token:
        return jsonify({"ok": False, "error": "jeton manquant"}), 400
    force = bool(data.get("force"))
    with _lock:
        holder = _presenter_holder()
        # Le boîtier n'a qu'un kiosque : quand la place est tenue depuis le
        # boîtier et qu'une demande arrive du boîtier, c'est le kiosque relancé
        # qui remplace son ancien navigateur, pas un second meneur. Sans cette
        # règle, l'ancienne page, pas encore tout à fait fermée, pouvait reprendre
        # la place au dernier battement et la garder 12 secondes.
        remplace_son_fantome = _presenter["kiosk"] and _depuis_le_boitier()
        if holder and holder != token and not force and not remplace_son_fantome:
            return jsonify({"ok": False, "taken": True}), 409
        _prendre_la_place(token)
    return jsonify({"ok": True, "taken": False, "mine": True})


@app.route("/api/presenter/ping", methods=["POST"])
def api_presenter_ping():
    """Battement de cœur du meneur. Renvoie ok=False s'il a perdu la place
    (quelqu'un a repris la main) : l'écran le saura et cessera de piloter."""
    data = _corps()
    token = str(data.get("token") or "")[:64]
    with _lock:
        holder = _presenter_holder()
        if holder and holder == token:
            _presenter["seen"] = time.monotonic()
            return jsonify({"ok": True})
        if holder is None and token:
            # Place libérée entre-temps : on la reprend sans discuter. L'écran
            # apprend ainsi qu'il pilote de nouveau et retire son voile.
            _prendre_la_place(token)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "taken": True})


@app.route("/api/presenter/release", methods=["POST"])
def api_presenter_release():
    data = _corps()
    token = str(data.get("token") or "")[:64]
    with _lock:
        if _presenter["holder"] == token:
            _presenter["holder"] = None
            _presenter["seen"] = 0.0
            _presenter["kiosk"] = False
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# API — ce que montre le grand écran du boîtier (section « Vue du journaliste »)
# --------------------------------------------------------------------------
# Trois choix : la vue Journaliste (le prompteur), la vue Settings, ou le bureau
# (navigateur fermé). install/kiosk.sh reste la source unique (démarrage
# automatique, icône de bureau, et ces routes).
#
# AUCUN privilège n'est nécessaire : le serveur et le navigateur du kiosque
# tournent sous le même utilisateur. Rien à voir avec l'extinction de la machine,
# qui reste le bouton physique du boîtier.
#
# Joignables depuis TOUS les appareils du WiFi du boîtier, téléphone compris :
# c'est le choix assumé, pour pouvoir refermer ou relancer l'écran sans avoir à
# aller toucher le boîtier. Les garde-fous restent le pare-feu (port limité au
# wlan0) et la protection anti-CSRF ci-dessus. Côté interface, quitter la vue
# Journaliste demande confirmation : depuis un téléphone, un appui involontaire
# couperait l'écran en pleine prise.


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
    """Appelle install/kiosk.sh. Renvoie (ok, code de retour, sortie).

    ok est faux quand le script n'a pas pu être exécuté du tout (poste de
    développement, bash absent) : l'état est alors inconnu, pas « arrêté »."""
    if not KIOSK_SCRIPT.exists():
        return False, None, ""
    env = _kiosk_env()
    try:
        proc = subprocess.run(  # nosec B603 - chemin fixe du projet, pas de shell
            ["/bin/bash", str(KIOSK_SCRIPT), *args],
            env=env,
            capture_output=True,
            timeout=20,
            check=False,
        )
        return True, proc.returncode, proc.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return False, None, ""


def _reflet():
    """Retournement du grand écran demandé par l'onglet Affichage : normal, x, y ou xy."""
    s = STATE["settings"]
    h, v = bool(s.get("mirrorH")), bool(s.get("mirrorV"))
    return {(False, False): "normal", (True, False): "x", (False, True): "y", (True, True): "xy"}[(h, v)]


def _miroir_hors_prompteur():
    """Applique le miroir à l'écran ENTIER quand il n'affiche pas le prompteur.

    La vue Journaliste se retourne elle-même (CSS, fluide) : l'écran reste alors
    normal. Mais la vue Settings affichée sur le grand écran, ou le bureau,
    doivent eux aussi se lire à travers la vitre — c'est l'écran entier qu'on
    retourne, pointeur de la souris compris.
    """
    affiche, vue = _etat_grand_ecran()
    if affiche is None or (affiche and vue == "journaliste"):
        return
    _kiosk("--miroir", _reflet())


def _kiosk_launch(vue):
    """Lance le prompteur sans attendre : le script patiente jusqu'à ce que le
    serveur réponde, ce qui bloquerait la requête en cours."""
    if not KIOSK_SCRIPT.exists():
        return False
    env = _kiosk_env()
    env["PROMPTEUR_MIROIR"] = _reflet()  # appliqué à l'écran entier pour la vue Settings
    try:
        subprocess.Popen(  # nosec B603 - chemin fixe du projet, pas de shell
            ["/bin/bash", str(KIOSK_SCRIPT), "--vue", vue],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _kiosk_reprendre():
    """Rouvre le grand écran s'il a été fermé par le redémarrage du service.

    Un navigateur ouvert depuis Settings (« Vue du journaliste », Échap) est un
    enfant du service : un redémarrage du service (mise à jour, plantage) le
    fermait, et le grand écran retombait sur le bureau. kiosk.sh --reprendre le
    rouvre sur la même vue — et ne fait rien s'il tourne encore, ou s'il avait été
    fermé volontairement.
    """
    if not KIOSK_SCRIPT.exists():
        return
    env = _kiosk_env()
    env["PROMPTEUR_MIROIR"] = _reflet()
    try:
        subprocess.Popen(  # nosec B603 - chemin fixe du projet, pas de shell
            ["/bin/bash", str(KIOSK_SCRIPT), "--reprendre"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        pass


# Ce que le grand écran peut montrer. « bureau » n'est pas une page : c'est le
# navigateur fermé, donc le bureau du Raspberry.
VUES_GRAND_ECRAN = ("journaliste", "settings")


def _etat_grand_ecran():
    """(affiché ?, vue) — affiché vaut None quand l'état n'a pas pu être lu."""
    ok, code, sortie = _kiosk("--status")
    if not ok:
        return None, None
    if code != 0:
        return False, None
    mots = sortie.split()
    vue = mots[1] if len(mots) > 1 and mots[1] in VUES_GRAND_ECRAN else "journaliste"
    return True, vue


@app.route("/api/kiosk")
def api_kiosk():
    """Ce que montre le grand écran du boîtier : la vue Journaliste, la vue
    Settings, ou le bureau (navigateur fermé)."""
    if not KIOSK_SCRIPT.exists():
        return jsonify({"available": False})
    affiche, vue = _etat_grand_ecran()
    # running = None quand l'etat n'a PAS pu etre determine (script non executable
    # ici, poste de developpement...). On affiche quand meme la section : cacher la
    # fonction en silence ferait disparaitre un bouton cense exister, sans indice.
    return jsonify({"available": True, "running": affiche, "vue": vue})


# Un seul changement de vue à la fois : deux appuis rapprochés (ou deux appareils)
# lanceraient sinon deux navigateurs l'un par-dessus l'autre.
_kiosk_lock = threading.Lock()


@app.route("/api/kiosk/close", methods=["POST"])
def api_kiosk_close():
    with _kiosk_lock:
        ok, _, _ = _kiosk("--stop")
        if not ok:
            return jsonify({"ok": False, "error": "script du kiosque introuvable"}), 500
        with _lock:
            _liberer_la_place_du_kiosque()
        # Le bureau aussi se lit à travers la vitre : il suit le réglage Miroir.
        _kiosk("--miroir", _reflet())
    return jsonify({"ok": True, "running": False})


@app.route("/api/kiosk/launch", methods=["POST"])
def api_kiosk_launch():
    data = _corps()
    vue = data.get("vue", "journaliste")
    if vue not in VUES_GRAND_ECRAN:
        return jsonify({"ok": False, "error": "vue inconnue"}), 400
    with _kiosk_lock:
        affiche, vue_actuelle = _etat_grand_ecran()
        if affiche and vue_actuelle == vue:
            return jsonify({"ok": True, "vue": vue})  # déjà affichée : rien à faire
        # Le navigateur du kiosque va être fermé (ou l'était déjà) : sa place de
        # meneur doit être rendue tout de suite, sans attendre qu'elle expire.
        with _lock:
            _liberer_la_place_du_kiosque()
        if not _kiosk_launch(vue):
            return jsonify({"ok": False, "error": "script du kiosque introuvable"}), 500
    return jsonify({"ok": True, "vue": vue})


# --------------------------------------------------------------------------
# API — veille du système
# --------------------------------------------------------------------------
# Veille = le grand écran s'éteint (plus de signal HDMI : le moniteur se met en
# veille de lui-même), le petit écran aussi, et toutes les pages affichent un
# fond noir avec un bouton « Rallumer ». Le texte, la position et les réglages
# ne bougent pas.
#
# L'extinction réelle passe par install/kiosk.sh (--veille / --reveil). Si elle
# échoue — poste de développement, session graphique inattendue —, les pages
# restent noires : la veille marche quand même, l'écran reste simplement allumé.
# La réponse le dit, pour que cela ne passe pas inaperçu.
_veille_lock = threading.Lock()


@app.route("/api/veille", methods=["POST"])
def api_veille():
    data = _corps()
    on = data.get("on")
    if not isinstance(on, bool):
        return jsonify({"ok": False, "error": "on doit valoir true ou false"}), 400
    # Sérialisé : une mise en veille et un réveil croisés pourraient sinon
    # éteindre l'écran APRÈS le réveil, et le laisser noir alors que tout
    # annonce un système allumé.
    with _veille_lock:
        with _lock:
            VEILLE["on"] = on
        ok, code, _ = _kiosk("--veille" if on else "--reveil")
    return jsonify({"ok": True, "veille": on, "ecran": bool(ok and code == 0)})


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
    # Filet de dernier recours depuis que le prompteur affiche du contenu mis en
    # forme : même si une faille laissait passer du balisage, rien d'extérieur ne
    # pourrait être chargé ni exécuté. Tout vient du boîtier, qui est hors-ligne.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'"
    )
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


# Un manifeste par vue : c'est lui qui décide de la page qu'ouvre le raccourci
# posé sur l'écran d'accueil. Avec un seul manifeste, le raccourci de la page
# Settings du téléphone ouvrait la vue Journaliste — et tombait sur « déjà
# ouverte ailleurs », puisque c'est le boîtier qui la tient.
#          nom complet, nom court, affichage, orientation
MANIFESTES = {
    "journaliste": ("Le Prompteur", "Prompteur", "fullscreen", "landscape"),
    "spectateur": ("Prompteur — Spectateur", "Spectateur", "fullscreen", "landscape"),
    "settings": ("Prompteur — Settings", "Settings", "standalone", "any"),
}


@app.route("/manifest.webmanifest")
def api_manifest():
    """Manifeste d'application web de la vue demandée (?vue=…, Journaliste par défaut).

    C'est le SEUL moyen, sur un appareil quelconque, d'obtenir un écran sans barre
    d'adresse ni onglets : une fois la page « installée » (« Installer
    l'application » sur ordinateur, « Ajouter à l'écran d'accueil » sur téléphone
    ou tablette), le navigateur l'ouvre sans le moindre mobilier. Sur le boîtier la
    question ne se pose pas : le kiosque Chromium tourne déjà ainsi.

    Journaliste et Spectateur : display=fullscreen, on en sort par Échap. Settings :
    standalone, la barre d'état du téléphone reste visible.
    """
    vue = request.args.get("vue", "journaliste")
    if vue not in MANIFESTES:
        vue = "journaliste"
    nom, court, affichage, orientation = MANIFESTES[vue]
    return jsonify(
        {
            "name": nom,
            "short_name": court,
            "description": "Téléprompteur à pédales du boîtier, hors-ligne.",
            "start_url": "/" + vue,
            "scope": "/",
            "display": affichage,
            "display_override": [affichage, "standalone"],
            "orientation": orientation,
            "background_color": "#000000",
            "theme_color": "#000000",
            "lang": "fr",
        }
    )


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
    _kiosk_reprendre()
    if os.environ.get("PROMPTEUR_DEBUG"):
        app.run(host=host, port=port, threaded=True, debug=True)  # nosec B201
    else:
        try:
            # serveur WSGI de production (robuste sur de longues sessions, multi-clients)
            from waitress import serve

            # max_request_body_size : sans lui, waitress met en mémoire jusqu'à 1 Go
            # avant que la borne de Flask ne s'applique.
            serve(app, host=host, port=port, threads=16, channel_timeout=120, max_request_body_size=MAX_BODY)
        except ImportError:
            # waitress absent (ex. poste de test) : repli sur le serveur Flask
            app.run(host=host, port=port, threaded=True)
