# -*- coding: utf-8 -*-
"""Extraction et nettoyage du texte de divers formats de fichiers.

Formats gérés : .txt/.md, .docx, .odt (pur Python, dézippage), .rtf, .pdf,
et .doc (ancien format binaire, via l'outil système « antiword » si présent).

On garde l'ESSENTIEL de la présentation — titres, paragraphes, sauts de ligne —
et on retire seulement la mise en page (polices, couleurs, marges, caractères
invisibles/parasites). Les titres sont marqués par des dièses en début de ligne
(« # Titre »), que le prompteur affiche ensuite en gros/gras.
"""

import html
import io
import os
import re
import subprocess  # nosec B404 - usage local, arguments fixes, sans shell
import tempfile
import unicodedata
import zipfile
from pathlib import Path

SUPPORTED_EXTS = (".txt", ".md", ".text", ".rtf", ".docx", ".doc", ".odt", ".pdf")

# --------------------------------------------------------------------------
# Bornes de sécurité
# --------------------------------------------------------------------------
# Un texte démesuré ne fait pas que ralentir : display.js crée un <div> par ligne
# dans une page qui anime un transform à 60 images/s. Quelques dizaines de milliers
# de lignes suffisent à figer l'écran du prompteur. Et comme le texte est persisté
# dans state.json, LE GEL SURVIT AU REDÉMARRAGE : la seule sortie serait un clavier
# et un terminal, ce qui, en tournage, revient à un boîtier mort.
#
# Deux façons d'y arriver, toutes deux mesurées :
#   * un .docx de 35 Ko dont le XML se décompresse en 8,9 Mo (ratio 256:1) donne
#     7,7 Mo de texte et 40 000 lignes ; à la limite de 5 Mo par fichier, on
#     atteindrait ~1,3 Go en mémoire, avant même le nettoyage caractère par caractère ;
#   * un simple copier-coller très long envoyé à /api/text.
# Ce n'est pas qu'un scénario d'attaque : un PDF de catalogue importé par erreur
# produit le même effet.
MAX_ZIP_ENTRY = 40 * 1024 * 1024  # XML décompressé accepté dans un .docx / .odt
MAX_TEXT_CHARS = 300_000  # ~100 pages : très au-delà d'un script de tournage
MAX_TEXT_LINES = 20_000


class TextTooLarge(ValueError):
    """Le document dépasse ce que le prompteur peut afficher sans se figer."""


def check_size(text):
    """Refuse un texte qui figerait l'affichage. Renvoie le texte inchangé sinon."""
    if len(text) > MAX_TEXT_CHARS:
        raise TextTooLarge(
            f"Document trop volumineux pour le prompteur : {len(text):,} caractères "
            f"(maximum {MAX_TEXT_CHARS:,}). Découpez-le en plusieurs séquences.".replace(",", " ")
        )
    lines = text.count("\n") + 1
    if lines > MAX_TEXT_LINES:
        raise TextTooLarge(
            f"Document trop long pour le prompteur : {lines:,} lignes "
            f"(maximum {MAX_TEXT_LINES:,}). Découpez-le en plusieurs séquences.".replace(",", " ")
        )
    return text


def _read_zip_entry(z, name):
    """Lit une entrée de zip APRÈS avoir vérifié sa taille décompressée.

    ZipInfo.file_size se lit dans l'en-tête, sans rien décompresser : c'est ce qui
    permet de refuser une « bombe de décompression » avant qu'elle n'occupe la RAM.
    """
    if z.getinfo(name).file_size > MAX_ZIP_ENTRY:
        raise TextTooLarge(
            "Ce document est trop volumineux une fois décompressé pour être lu "
            "par le prompteur. Réenregistrez-le en texte ou découpez-le."
        )
    return z.read(name)


# --------------------------------------------------------------------------
# Nettoyage du texte
# --------------------------------------------------------------------------
def clean_text(s):
    """Ne conserve que le texte lisible : normalise Unicode, supprime les
    caractères de contrôle/invisibles, réduit les espaces et lignes vides."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ch in s:
        if ch == "\n":
            out.append("\n")
        elif ch == "\t":
            out.append(" ")
        else:
            cat = unicodedata.category(ch)
            if cat in ("Zl", "Zp"):  # séparateurs ligne / paragraphe -> saut de ligne
                out.append("\n")
            elif cat == "Zs":  # espaces Unicode (nbsp, cadratin…) -> espace normal
                out.append(" ")
            elif cat[0] == "C":  # caractères de contrôle / format (zéro-largeur, BOM…) -> supprimés
                continue
            else:
                out.append(ch)
    # espaces multiples -> simple, et on enlève les espaces en bord de ligne
    lines = [re.sub(r" {2,}", " ", ln).strip() for ln in "".join(out).split("\n")]
    # 3 sauts de ligne ou plus -> un seul saut de paragraphe
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --------------------------------------------------------------------------
# Décodage texte brut
# --------------------------------------------------------------------------
def _decode(data):
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Formats basés sur un ZIP + XML (docx, odt) — pur Python, aucune dépendance
#
# On PRÉSERVE la structure (paragraphes, sauts de ligne) et on marque les TITRES
# avec des dièses en début de ligne (« # Titre », « ## Sous-titre »), que le
# prompteur affiche ensuite en gros/gras. On retire seulement la mise en page.
# --------------------------------------------------------------------------
def _para_body(p_xml):
    """Texte d'un paragraphe : sauts de ligne manuels et tabulations préservés,
    toutes les autres balises (mise en forme) retirées."""
    p_xml = re.sub(r"<w:br\b[^>]*/?>|<w:cr\b[^>]*/?>|<text:line-break\b[^>]*/?>", "\n", p_xml)
    p_xml = re.sub(r"<w:tab\b[^>]*/?>|<text:tab\b[^>]*/?>", " ", p_xml)
    return html.unescape(re.sub(r"<[^>]+>", "", p_xml))


def _docx_heading_level(p_xml):
    """Niveau de titre d'un paragraphe .docx (0 = corps de texte)."""
    m = re.search(r'<w:pStyle\b[^>]*\bw:val="([^"]*)"', p_xml)
    if not m:
        return 0
    style = m.group(1).lower()
    if "subtitle" in style:
        return 2
    if "title" in style:
        return 1
    m2 = re.search(r"(?:heading|titre|title)[ _-]?(\d+)", style)
    if m2:
        return max(1, min(3, int(m2.group(1))))
    if "heading" in style or style.startswith("titre"):
        return 1
    return 0


def _mark(level, text):
    text = text.strip()
    return ("#" * level + " " + text) if (level and text) else text


def _from_docx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "word/document.xml").decode("utf-8", "replace")
    lines = []
    for m in re.finditer(r"<w:p\b(?:[^>]*/>|[^>]*>.*?</w:p>)", xml, flags=re.S):
        p = m.group(0)
        lines.append(_mark(_docx_heading_level(p), _para_body(p)))
    return "\n".join(lines)


def _from_odt(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "content.xml").decode("utf-8", "replace")
    lines = []
    for m in re.finditer(r"<text:(p|h)\b([^>]*)>(.*?)</text:\1>", xml, flags=re.S):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        level = 0
        if tag == "h":
            lvl = re.search(r'text:outline-level="(\d+)"', attrs)
            level = max(1, min(3, int(lvl.group(1)))) if lvl else 1
        lines.append(_mark(level, _para_body(inner)))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# RTF
# --------------------------------------------------------------------------
def _from_rtf(data):
    text = _decode(data)
    try:
        from striprtf.striprtf import rtf_to_text

        return rtf_to_text(text)
    except ImportError:
        # repli minimal : retire les échappements et commandes RTF, puis les accolades
        text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
        return text.replace("{", "").replace("}", "")


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def _from_pdf(data):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


# --------------------------------------------------------------------------
# DOC (ancien format binaire Word) — nécessite antiword ou catdoc
# --------------------------------------------------------------------------
def _from_doc(data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tf:
            tf.write(data)
            tmp = tf.name
        for tool in ("antiword", "catdoc"):
            try:
                out = subprocess.run(  # nosec B603 - binaire fixe, sans shell, chemin contrôlé
                    [tool, tmp], capture_output=True, timeout=20, check=False
                )
                if out.returncode == 0 and out.stdout.strip():
                    return out.stdout.decode("utf-8", "replace")
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    raise ValueError(
        "Le format .doc nécessite l'outil « antiword » sur le boîtier. "
        "Astuce : enregistrez plutôt le document en .docx."
    )


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------
_EXTRACTORS = {
    ".docx": _from_docx,
    ".odt": _from_odt,
    ".rtf": _from_rtf,
    ".pdf": _from_pdf,
    ".doc": _from_doc,
}


def extract_text(filename, data):
    """Extrait puis nettoie le texte d'un fichier (donné par son nom + ses octets).

    Lève ValueError avec un message clair si le format ne peut pas être lu."""
    ext = Path(filename or "").suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    try:
        raw = extractor(data) if extractor else _decode(data)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 - on renvoie un message lisible à l'utilisateur
        raise ValueError(f"Impossible de lire ce fichier ({ext or 'inconnu'}) : {e}") from e
    # Borné DEUX fois : sur le texte brut d'abord, car clean_text parcourt la chaîne
    # caractère par caractère et coûterait des dizaines de secondes sur un Pi ; puis
    # sur le résultat, qui est ce qui partira réellement à l'écran.
    return check_size(clean_text(check_size(raw)))
