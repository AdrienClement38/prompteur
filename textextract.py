# -*- coding: utf-8 -*-
"""Extraction et nettoyage du texte de divers formats de fichiers.

Formats gérés : .txt/.md, .docx, .odt (pur Python, dézippage), .rtf, .pdf,
et .doc (ancien format binaire, via l'outil système « antiword » si présent).

On garde l'ESSENTIEL de la présentation — titres, paragraphes, sauts de ligne —
et on retire seulement la mise en page (polices, couleurs, marges, caractères
invisibles/parasites). Les titres sont marqués par des dièses en début de ligne
(« # Titre »), que le prompteur affiche ensuite en gros/gras.

Depuis l'ajout de la mise en forme, .docx et .odt font aussi remonter le GRAS,
l'ITALIQUE et le SOULIGNÉ sous forme de PLAGES (« marks ») posées sur le texte
final : extract_rich() renvoie (texte, plages), extract_text() ne renvoie que le
texte et reste donc compatible avec ses appelants actuels.
"""

import bisect
import colorsys
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

# Nombre maximal de plages de mise en forme produites par un import.
# ALIGNÉ SUR server.MAX_MARKS : au-delà, sanitize_marks() tronquerait la liste
# en silence, et une mise en forme tronquée au milieu d'un document est pire
# qu'une absence de mise en forme. On ne fait pas « from server import » : c'est
# server.py qui importe textextract.py, l'inverse créerait un cycle.
MAX_MARKS = 500


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
# POURQUOI UN NETTOYAGE INSTRUMENTÉ (table de positions) PLUTÔT QU'UN NETTOYAGE
# FRAGMENT PAR FRAGMENT.
#
# Le problème : les plages de mise en forme doivent désigner des indices dans le
# texte NETTOYÉ, alors que le gras est lu sur le texte BRUT du document. Or le
# nettoyage change les longueurs (espaces réduits, lignes vides fusionnées,
# caractères invisibles supprimés). Une plage décalée de trois caractères met en
# évidence les mauvais mots en pleine lecture : c'est pire que pas de mise en forme.
#
# Deux voies étaient possibles.
#   1. Nettoyer le texte entier UNE fois, en notant au passage, pour chaque
#      caractère survivant, d'où il vient dans le brut (la « table d'origines »).
#   2. Découper d'abord en fragments stylés, nettoyer chaque fragment, puis recoller.
#
# La 2 est écartée pour trois raisons :
#   * le nettoyage est CONTEXTUEL, pas local. Réduire les espaces multiples, retirer
#     les espaces de bord de ligne et fusionner les lignes vides dépend de ce qui
#     entoure le fragment. Deux espaces à cheval sur la frontière « fin de passage
#     normal / début de passage gras » ne se verraient pas. Le texte obtenu serait
#     donc DIFFÉRENT de clean_text(brut) — exactement la régression interdite ;
#   * avec la voie 1, clean_text() délègue à _clean_indexed() : il n'existe qu'UN
#     seul algorithme de nettoyage. Un document sans style et un document stylé
#     traversent le même code, ils ne peuvent pas diverger à la prochaine retouche ;
#   * la table est produite PENDANT le nettoyage, jamais reconstituée après coup par
#     recherche de chaîne ou par diff : aucune heuristique ne peut se tromper
#     d'occurrence sur un mot répété.
#
# La table est croissante (non strictement : voir _nfc_indexe), donc la conversion
# d'un intervalle brut en intervalle nettoyé se fait par simple bissection.

# Jamos et syllabes Hangul : le seul cas où la composition NFC réunit deux
# caractères « de départ » (classe combinatoire 0). Partout ailleurs, une
# composition ne franchit jamais une frontière de départ, ce qui autorise à
# normaliser groupe par groupe (voir _nfc_indexe).
_PLAGES_HANGUL = ((0x1100, 0x11FF), (0xA960, 0xA97F), (0xAC00, 0xD7A3), (0xD7B0, 0xD7FF))


def _est_hangul(ch):
    code = ord(ch)
    if code < 0x1100:  # tout l'alphabet latin sort ici, en une comparaison
        return False
    return any(debut <= code <= fin for debut, fin in _PLAGES_HANGUL)


def _nfc_indexe(s):
    """Normalise en NFC en conservant l'origine de chaque caractère produit.

    Renvoie (liste de caractères, liste d'origines). La NFC n'est pas une
    correspondance 1 pour 1 (« e » + accent combinant donne « é », deux caractères
    pour un) : on normalise donc par GROUPES — un caractère de départ suivi de ses
    marques combinantes — et tous les caractères issus d'un groupe pointent sur le
    début de ce groupe. Quand un groupe est déjà normalisé, chaque caractère garde
    son propre index : c'est le cas courant, et il reste ainsi exact au caractère.
    """
    if unicodedata.is_normalized("NFC", s):
        return list(s), list(range(len(s)))
    groupes = []  # [index de départ, liste de caractères]
    for i, ch in enumerate(s):
        if ch < "̀":  # U+0300 est la 1re marque combinante : en deçà, toujours un départ
            groupes.append([i, [ch]])
            continue
        depart = unicodedata.combining(ch) == 0
        if depart and groupes and _est_hangul(ch) and _est_hangul(groupes[-1][1][-1]):
            depart = False  # L + V + T : la composition franchit la frontière
        if depart or not groupes:
            groupes.append([i, [ch]])
        else:
            groupes[-1][1].append(ch)
    # Un texte décomposé répète les mêmes groupes des milliers de fois (« e » + accent
    # aigu…). On mémorise donc le résultat par groupe : un texte de 290 000 caractères
    # accentués passe de ~150 000 appels à unicodedata.normalize() à quelques dizaines.
    # Le cache est LOCAL à l'appel, donc libéré aussitôt, et borné par check_size().
    connus = {}
    chars, origines = [], []
    for debut, morceau in groupes:
        source = "".join(morceau)
        compose = connus.get(source)
        if compose is None:
            compose = connus[source] = unicodedata.normalize("NFC", source)
        if compose == source:
            chars.extend(morceau)
            origines.extend(range(debut, debut + len(morceau)))
        else:
            chars.extend(compose)
            origines.extend([debut] * len(compose))
    return chars, origines


def _clean_indexed(s):
    """Nettoie le texte ET renvoie la table des positions d'origine.

    Renvoie (texte_propre, origines) où origines[i] est l'index, dans la chaîne
    reçue, du caractère qui a produit texte_propre[i]. La liste est croissante.
    """
    if not s:
        return "", []
    chars, origines = _nfc_indexe(str(s))

    # Passe unique : CRLF, classification caractère par caractère, réduction des
    # espaces multiples et retrait des espaces de bord de ligne. Après la
    # classification, le seul blanc possible à l'intérieur d'une ligne est
    # l'espace ASCII (tabulation et Zs deviennent un espace, Zl/Zp un saut de
    # ligne, Cc/Cf disparaissent) : « réduire les espaces » suffit donc à
    # reproduire les expressions régulières de la version d'origine.
    lignes = [([], [])]  # une ligne = (caractères, origines)
    separateurs = []  # origine de chaque « \n » entre deux lignes

    def _fermer_ligne():
        car, ori = lignes[-1]
        while car and car[-1] == " ":
            car.pop()
            ori.pop()

    i, total = 0, len(chars)
    while i < total:
        ch, origine = chars[i], origines[i]
        i += 1
        if ch == "\r":  # « \r\n » comme « \r » seul valent un saut de ligne
            if i < total and chars[i] == "\n":
                i += 1
            ch = "\n"
        elif ch != "\n":
            cat = unicodedata.category(ch)
            if ch == "\t" or cat == "Zs":  # tabulation, espaces Unicode (nbsp, cadratin…)
                ch = " "
            elif cat in ("Zl", "Zp"):  # séparateurs ligne / paragraphe
                ch = "\n"
            elif cat[0] == "C":  # contrôle / format (zéro-largeur, BOM…) -> supprimés
                continue
        if ch == "\n":
            _fermer_ligne()
            lignes.append(([], []))
            separateurs.append(origine)
            continue
        car, ori = lignes[-1]
        if ch == " " and (not car or car[-1] == " "):
            continue  # espace de tête ou espace multiple
        car.append(ch)
        ori.append(origine)
    _fermer_ligne()

    # Assemblage : 3 sauts de ligne ou plus -> un seul saut de paragraphe.
    sortie_c, sortie_o = [], []
    sauts = 0  # nombre de « \n » consécutifs déjà émis en fin de sortie
    for rang, (car, ori) in enumerate(lignes):
        if rang:
            if sauts < 2:
                sortie_c.append("\n")
                sortie_o.append(separateurs[rang - 1])
                sauts += 1
        if car:
            sortie_c.extend(car)
            sortie_o.extend(ori)
            sauts = 0

    # Retrait des blancs de bord (seuls des « \n » peuvent subsister ici).
    debut, fin = 0, len(sortie_c)
    while debut < fin and sortie_c[debut].isspace():
        debut += 1
    while fin > debut and sortie_c[fin - 1].isspace():
        fin -= 1
    return "".join(sortie_c[debut:fin]), sortie_o[debut:fin]


def clean_text(s):
    """Ne conserve que le texte lisible : normalise Unicode, supprime les
    caractères de contrôle/invisibles, réduit les espaces et lignes vides."""
    return _clean_indexed(s)[0]


# --------------------------------------------------------------------------
# Décodage texte brut
# --------------------------------------------------------------------------
def _utf16_probable(data):
    """Vrai pour un texte UTF-16 : « Unicode » dans le Bloc-notes de Windows.

    Avec sa marque d'ordre des octets (BOM), c'est certain. Sans elle, un texte
    UTF-16 en alphabet latin a un octet nul sur deux — ce qu'aucun texte en UTF-8
    ou en Latin-1 ne contient jamais.
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if len(data) >= 4 and data.count(b"\x00") * 3 >= len(data):
        return "utf-16-le" if data[1:2] == b"\x00" else "utf-16-be"
    return None


def _decode(data):
    # UTF-16 d'abord : Latin-1 accepte TOUS les octets, et décodait donc sans erreur
    # un texte « Unicode » en charabia parsemé de caractères nuls.
    if isinstance(data, bytes):
        utf16 = _utf16_probable(data)
        if utf16:
            try:
                return data.decode(utf16).replace("\x00", "")
            except UnicodeDecodeError:
                pass
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
#
# Le texte est produit sous forme de SEGMENTS : une liste de (texte, styles) dont
# la concaténation est, au caractère près, le texte brut d'avant. Un document sans
# aucun style redonne donc exactement le même résultat qu'auparavant, et il n'y a
# qu'un seul chemin de code pour les deux cas.
#
# LIMITES ASSUMÉES : on ne lit que la mise en forme DIRECTE (le gras posé sur les
# mots). Un gras hérité d'un style nommé défini dans styles.xml n'est pas vu —
# choix délibéré : ne rien afficher vaut mieux que croire à tort qu'un document
# entier est en gras. w:bCs / w:iCs (scripts complexes) sont ignorés, et .pdf /
# .rtf restent hors périmètre, leurs extracteurs ne donnant pas accès aux styles.
# --------------------------------------------------------------------------
_RE_RPR_DOCX = re.compile(r"<w:rPr\b[^>]*>(.*?)</w:rPr>", re.S)
# Repérage des OUVERTURES seulement : ces motifs sont sans « .* », donc sans retour
# arrière possible. La fin du bloc est trouvée par _blocs() (voir ci-dessous).
_OUVRE_PARA_DOCX = re.compile(r"<w:p\b")
_OUVRE_RUN_DOCX = re.compile(r"<w:r\b")
_OUVRE_PARA_ODT = re.compile(r"<text:(p|h)\b")
_OUVRE_STYLE_ODT = re.compile(r"<style:style\b")
_FERME_PARA_ODT = {"p": "</text:p>", "h": "</text:h>"}


def _blocs(xml, re_ouvre, ferme, auto_fermant=True):
    """Énumère les blocs « <balise …/> » ou « <balise …>…</balise> », en temps LINÉAIRE.

    Remplace les motifs du genre « <w:r\\b(?:[^>]*/>|[^>]*>.*?</w:r>) ». Ceux-ci sont
    corrects mais QUADRATIQUES sur un document abîmé : quand la balise n'est jamais
    refermée, « .*?</w:r> » relit tout le reste du fichier à CHAQUE ouverture. Mesuré
    sur un .docx de 500 octets contenant 40 000 « <w:r> » sans fermeture : 103 secondes,
    et le plafond MAX_ZIP_ENTRY n'y peut rien puisque le fichier est minuscule. Un
    import gèlerait le boîtier en plein tournage — exactement ce que ce module
    s'attache à empêcher par ailleurs.

    Ici, chaque caractère n'est lu qu'un nombre borné de fois : « rfind » dit d'emblée
    qu'aucune fermeture ne suit, et la position du « > » courant est retenue.

    Produit (debut, fin, m) où m est la correspondance de l'ouverture. Les blocs
    renvoyés sont EXACTEMENT ceux des anciens motifs — c'est ce que verrouille
    test_blocs_identiques_aux_anciens_motifs, qui rejoue les deux sur des XML abîmés.

    « ferme » est la balise fermante : une chaîne, ou un dictionnaire indexé par le
    1er groupe capturé quand elle dépend du nom trouvé (<text:p> / <text:h>).
    « auto_fermant » à False supprime la variante « <balise/> », que le motif des
    paragraphes ODT ne prévoyait pas.
    """
    derniers = {}  # balise fermante -> index de sa DERNIÈRE occurrence (-1 si absente)
    chevron = -1  # « > » trouvé pour l'ouverture précédente : les positions ne reculent pas
    pos = 0
    while True:
        m = re_ouvre.search(xml, pos)
        if m is None:
            return
        debut = m.end()  # juste après « <w:r », là où commence « [^>]* »
        if chevron < debut:
            chevron = xml.find(">", debut)
            if chevron < 0:
                return  # plus aucune balise complète ensuite : rien ne peut correspondre
        if auto_fermant and chevron - 1 >= debut and xml[chevron - 1] == "/":
            yield m.start(), chevron + 1, m  # « <balise …/> »
            pos = chevron + 1
            continue
        tag = ferme if isinstance(ferme, str) else ferme[m.group(1)]
        if tag not in derniers:
            derniers[tag] = xml.rfind(tag)
        # find() ne peut aboutir que s'il reste une fermeture après le « > ».
        fin = xml.find(tag, chevron + 1) if chevron < derniers[tag] else -1
        if fin < 0:
            pos = m.start() + 1  # ouverture jamais refermée : ignorée, comme l'ancien motif
            continue
        yield m.start(), fin + len(tag), m
        pos = fin + len(tag)


# Découpage sans perte : une balise, du texte, ou un « < » orphelin. Les frontières
# tombent exactement là où _para_body() reconnaît une balise, donc appliquer
# _para_body() morceau par morceau donne la même chaîne qu'en une seule fois.
_RE_JETON = re.compile(r"<[^>]+>|[^<]+|<", re.S)
# « (?=[\s/>]) » : ne pas confondre <text:s/> avec <text:span>.
_RE_ESPACE_ODT = re.compile(r'<text:s(?=[\s/>])[^>]*?(?:\btext:c="(\d+)")?[^>]*/?>')
_VALEURS_OFF = ("0", "false", "off", "none")


def _para_body(p_xml):
    """Texte d'un paragraphe : sauts de ligne manuels et tabulations préservés,
    toutes les autres balises (mise en forme) retirées."""
    p_xml = re.sub(r"<w:br\b[^>]*/?>|<w:cr\b[^>]*/?>|<text:line-break\b[^>]*/?>", "\n", p_xml)
    p_xml = re.sub(r"<w:tab\b[^>]*/?>|<text:tab\b[^>]*/?>", " ", p_xml)
    # LibreOffice écrit certaines espaces comme une BALISE : <text:s/>, ou
    # <text:s text:c="3"/> pour trois d'affilée. Retirée comme les autres
    # balises, elle collait les mots entre eux.
    p_xml = _RE_ESPACE_ODT.sub(lambda m: " " * max(1, min(100, int(m.group(1) or 1))), p_xml)
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


def _rogner_segments(segments):
    """Reproduit le .strip() de _mark() sur une liste de segments."""
    debut = 0
    while debut < len(segments):
        texte = segments[debut][0].lstrip()
        if texte:
            segments[debut] = (texte, segments[debut][1])
            break
        debut += 1
    segments = segments[debut:]
    fin = len(segments)
    while fin > 0:
        texte = segments[fin - 1][0].rstrip()
        if texte:
            segments[fin - 1] = (texte, segments[fin - 1][1])
            break
        fin -= 1
    return [seg for seg in segments[:fin] if seg[0]]


PUCE = "• "  # le point de puce, suivi d'une espace


def _titrer_segments(niveau, segments, puce=False, alignement=None):
    """Pose ce qui appartient au PARAGRAPHE : dièses de titre, puce, alignement.

    Le titre et la puce deviennent du TEXTE (« # », « • ») et non un style : c'est
    ce qui permet de les écrire aussi à la main, et de les retrouver intacts dans un
    fichier enregistré puis relu des mois plus tard. L'alignement, lui, n'a pas
    d'écriture possible au clavier : il voyage comme une plage posée sur toute la
    ligne, que l'écran lit au premier caractère.
    """
    segments = _rogner_segments(segments)
    if segments:
        prefixe = ("#" * niveau + " ") if niveau else (PUCE if puce else "")
        if prefixe:
            segments.insert(0, (prefixe, {}))
        if alignement:
            segments = [(t, dict(st, align=alignement)) for t, st in segments]
    return segments


# --------------------------------------------------------------------------
# Couleur et taille : de la mise en page du document vers ce qui est LISIBLE
# --------------------------------------------------------------------------
# Le prompteur n'offre que CINQ couleurs, toutes choisies lisibles sur fond
# sombre. Un document, lui, peut en contenir des millions — dont du bleu marine
# et du gris anthracite, invisibles sur l'ecran d'un prompteur, au moment precis
# ou l'on comptait sur le passage mis en avant.
#
# On ne recopie donc pas la couleur du document : on garde son INTENTION
# (« ce passage est en rouge ») en tombant sur la couleur lisible la plus proche.
# La correspondance se fait sur la TEINTE et non sur la distance RVB : un rouge
# sombre doit devenir le rouge de la palette, pas le gris qui se trouve etre
# numeriquement plus proche.
PALETTE_TEINTES = ((1, 50.0), (2, 9.0), (3, 142.0), (4, 207.0))  # jaune, rouge, vert, bleu
PALETTE_GRIS = 5
_RE_HEXA = re.compile(r"^[0-9a-f]{6}$")


def _couleur_palette(valeur):
    """Couleur ecrite dans le document -> numero de palette (1-5), ou None.

    None signifie « texte ordinaire » : noir, blanc, automatique. Les marquer
    serait pire que de les ignorer, car cela figerait la couleur du texte et
    empecherait le reglage general de la changer.
    """
    if not valeur:
        return None
    brut = valeur.strip().lstrip("#").lower()
    if brut in ("auto", "automatic", "windowtext", "transparent"):
        return None
    if len(brut) == 3:
        brut = "".join(c * 2 for c in brut)
    if not _RE_HEXA.match(brut):
        return None
    r, v, b = (int(brut[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    teinte, lum, sat = colorsys.rgb_to_hls(r, v, b)
    if sat < 0.15:
        # Gris franc -> la couleur grise de la palette ; noir et blanc -> rien,
        # c'est la couleur normale du texte.
        return None if lum < 0.25 or lum > 0.85 else PALETTE_GRIS
    degres = teinte * 360.0
    meilleur, ecart_min = PALETTE_GRIS, 999.0
    for numero, ref in PALETTE_TEINTES:
        ecart = abs(degres - ref)
        ecart = min(ecart, 360.0 - ecart)  # le cercle des teintes se referme
        if ecart < ecart_min:
            meilleur, ecart_min = numero, ecart
    return meilleur


def _taille_relative(rapport):
    """Taille du document, RAPPORTEE au corps du texte -> « s », « l », « xl ».

    Rapportee et non absolue : sur un prompteur, c'est le lecteur qui fixe la
    taille generale selon sa distance a l'ecran. Recopier un « 8 points » rendrait
    le passage illisible ; ce qu'il faut conserver, c'est « plus petit que le
    reste » ou « bien plus gros que le reste ».
    """
    if not rapport or rapport <= 0:
        return None
    if rapport <= 0.85:
        return "s"
    if rapport >= 1.45:
        return "xl"
    if rapport >= 1.15:
        return "l"
    return None


def _mode_des_tailles(valeurs, defaut):
    """Taille du corps du texte = la plus repandue dans le document."""
    if not valeurs:
        return defaut
    comptes = {}
    for v in valeurs:
        comptes[v] = comptes.get(v, 0) + 1
    return max(comptes.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def _actif(balise):
    """Une balise de style Word est-elle activée ? (<w:b/> oui, <w:b w:val="0"/> non)"""
    m = re.search(r'\bw:val="([^"]*)"', balise)
    return not (m and m.group(1).strip().lower() in _VALEURS_OFF)


_RE_SZ_DOCX = re.compile(r'<w:sz\b[^>]*\bw:val="(\d+)"')
_RE_COLOR_DOCX = re.compile(r'<w:color\b[^>]*\bw:val="([^"]*)"')
_RE_OUVRE_RUN_COMPTE = re.compile(r"<w:r(?:\s[^>]*)?>")
_RE_JC_DOCX = re.compile(r'<w:jc\b[^>]*\bw:val="([^"]*)"')
_ALIGNEMENTS = {"center": "center", "right": "right", "end": "right"}


_DEFAUT_SZ_DOCX = 22  # 11 points, la taille par défaut de Word


def _docx_corps_taille(xml):
    """Taille du corps du texte : la plus répandue du document, en demi-points.

    Les passages SANS taille explicite comptent, eux aussi, pour la taille par
    défaut. Sans cela, un document dont un seul mot est agrandi ferait de ce mot
    la référence — et le mot agrandi ne ressortirait plus du tout.
    """
    tailles = [int(v) for v in _RE_SZ_DOCX.findall(xml)]
    runs = len(_RE_OUVRE_RUN_COMPTE.findall(xml))
    tailles += [_DEFAUT_SZ_DOCX] * max(0, runs - len(tailles))
    return _mode_des_tailles(tailles, _DEFAUT_SZ_DOCX)


def _docx_alignement(p_xml):
    """Alignement du paragraphe, seulement s'il s'écarte du réglage par défaut."""
    m = _RE_JC_DOCX.search(p_xml)
    return _ALIGNEMENTS.get(m.group(1).strip().lower()) if m else None


def _docx_puce(p_xml):
    """Le paragraphe est-il un élément de liste ?

    Deux signes, car Word emploie l'un ou l'autre selon la version : la numérotation
    proprement dite, ou le style « Paragraphe de liste » posé par le bouton de puces.
    """
    entete = p_xml[: p_xml.find("</w:pPr>") + 1] if "</w:pPr>" in p_xml else p_xml[:400]
    if "<w:numPr" in entete:
        return True
    style = re.search(r'<w:pStyle\b[^>]*\bw:val="([^"]*)"', entete)
    if not style:
        return False
    nom = style.group(1).strip().lower().replace(" ", "").replace("-", "")
    return nom in ("listparagraph", "paragraphedeliste", "listbullet", "listnumber")


def _styles_docx_rpr(rpr_xml, corps=22):
    """Gras / italique / souligné / couleur / taille lus dans un <w:rPr> de .docx."""
    styles = {}
    for cle, motif in (("b", r"<w:b\b[^>]*>"), ("i", r"<w:i\b[^>]*>"), ("u", r"<w:u\b[^>]*>")):
        m = re.search(motif, rpr_xml)
        if m and _actif(m.group(0)):
            styles[cle] = True
    couleur = _RE_COLOR_DOCX.search(rpr_xml)
    if couleur:
        numero = _couleur_palette(couleur.group(1))
        if numero:
            styles["color"] = numero
    taille = _RE_SZ_DOCX.search(rpr_xml)
    if taille and corps:
        relative = _taille_relative(int(taille.group(1)) / float(corps))
        if relative:
            styles["size"] = relative
    return styles


def _styles_docx_run(run_xml, corps=22):
    m = _RE_RPR_DOCX.search(run_xml)
    return _styles_docx_rpr(m.group(1), corps) if m else {}


def _docx_para_segments(p_xml, corps=22):
    """Découpe un paragraphe .docx en segments (texte, styles)."""
    niveau = _docx_heading_level(p_xml)
    segments = []
    pos = 0
    for debut, fin, _m in _blocs(p_xml, _OUVRE_RUN_DOCX, "</w:r>"):
        if debut > pos:  # hors run : <w:pPr>, <w:br/> isolé, etc.
            segments.append((_para_body(p_xml[pos:debut]), {}))
        run_xml = p_xml[debut:fin]
        segments.append((_para_body(run_xml), _styles_docx_run(run_xml, corps)))
        pos = fin
    if pos < len(p_xml):
        segments.append((_para_body(p_xml[pos:]), {}))
    return _titrer_segments(niveau, segments, _docx_puce(p_xml), _docx_alignement(p_xml))


def _docx_segments(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "word/document.xml").decode("utf-8", "replace")
    corps = _docx_corps_taille(xml)
    segments = []
    for rang, (debut, fin, _m) in enumerate(_blocs(xml, _OUVRE_PARA_DOCX, "</w:p>")):
        if rang:
            segments.append(("\n", {}))
        segments.extend(_docx_para_segments(xml[debut:fin], corps))
    return segments


_RE_TAILLE_ODT = re.compile(r'\bfo:font-size="([0-9.]+)(pt|%)"')
_RE_COULEUR_ODT = re.compile(r'\bfo:color="([^"]*)"')
_RE_ALIGN_ODT = re.compile(r'\bfo:text-align="([^"]*)"')
_DEFAUT_PT_ODT = 12.0


def _odt_corps_taille(xml):
    """Taille du corps du texte d'un .odt, en points.

    On la lit dans le style par défaut du document plutôt que de prendre la plus
    répandue : contrairement au .docx, un .odt n'écrit la taille que là où elle
    s'écarte du défaut, donc « la plus répandue » ne voudrait rien dire.
    """
    for motif in (
        r"<style:default-style\b[^>]*?style:family=\"paragraph\".*?</style:default-style>",
        r"<style:style\b[^>]*?style:name=\"Standard\".*?</style:style>",
    ):
        bloc = re.search(motif, xml, re.S)
        if bloc:
            m = _RE_TAILLE_ODT.search(bloc.group(0))
            if m and m.group(2) == "pt":
                return float(m.group(1))
    return _DEFAUT_PT_ODT


def _styles_odt_props(props_xml, corps_pt=_DEFAUT_PT_ODT):
    """Gras / italique / souligné / couleur / taille lus dans un <style:text-properties>.

    Renvoie un état à TROIS valeurs : clé absente = « le style ne se prononce pas,
    on garde ce qui est hérité » ; valeur vraie = activé ; valeur FAUSSE = annulé
    explicitement.

    Cette troisième valeur n'est pas un raffinement, elle est indispensable. Dans un
    .odt, la mise en forme des caractères se CUMULE : un span dans un span, et un
    style qui hérite de son parent. Quand on dégrasse un mot au milieu d'une phrase
    en gras, LibreOffice n'enlève rien au span extérieur — il imbrique un span
    portant fo:font-weight="normal". Sans le False, l'annulation passait inaperçue
    et le mot dégrassé ressortait EN GRAS : la mise en forme tombait sur les
    mauvais mots, précisément ce qu'on cherche à éviter. La couleur et la taille
    suivent la même règle, avec 0 et "" pour valeurs d'annulation.
    """
    styles = {}
    graisse = re.search(r'\bfo:font-weight="([^"]*)"', props_xml)
    if graisse:
        valeur = graisse.group(1).strip().lower()
        styles["b"] = valeur == "bold" or (valeur.isdigit() and int(valeur) >= 600)
    penche = re.search(r'\bfo:font-style="([^"]*)"', props_xml)
    if penche:
        styles["i"] = penche.group(1).strip().lower() in ("italic", "oblique")
    souligne = re.search(r'\bstyle:text-underline-style="([^"]*)"', props_xml)
    if souligne:
        styles["u"] = souligne.group(1).strip().lower() not in ("", "none")
    couleur = _RE_COULEUR_ODT.search(props_xml)
    if couleur:
        styles["color"] = _couleur_palette(couleur.group(1)) or 0
    taille = _RE_TAILLE_ODT.search(props_xml)
    if taille:
        valeur = float(taille.group(1))
        rapport = valeur / 100.0 if taille.group(2) == "%" else valeur / (corps_pt or _DEFAUT_PT_ODT)
        styles["size"] = _taille_relative(rapport) or ""
    return styles


def _odt_table_styles(xml, corps_pt=_DEFAUT_PT_ODT):
    """Dictionnaire « nom de style de texte » -> styles, héritage résolu."""
    bruts = {}
    for debut, fin, _m in _blocs(xml, _OUVRE_STYLE_ODT, "</style:style>"):
        bloc = xml[debut:fin]
        entete = bloc[: bloc.find(">") + 1]
        if 'style:family="text"' not in entete:
            continue
        nom = re.search(r'\bstyle:name="([^"]*)"', entete)
        if not nom:
            continue
        parent = re.search(r'\bstyle:parent-style-name="([^"]*)"', entete)
        props = re.search(r"<style:text-properties\b([^>]*)>", bloc)
        bruts[nom.group(1)] = (
            parent.group(1) if parent else None,
            _styles_odt_props(props.group(1), corps_pt) if props else {},
        )

    table = {}
    for nom in bruts:
        chaine, courant, vus = [], nom, set()
        while courant in bruts and courant not in vus:
            vus.add(courant)
            chaine.append(bruts[courant][1])
            courant = bruts[courant][0]
        styles = {}
        for maillon in reversed(chaine):  # le parent d'abord, l'enfant l'emporte
            styles.update(maillon)
        table[nom] = styles
    return table


def _odt_para_segments(inner, table):
    """Découpe un paragraphe ODT en segments, en suivant les <text:span> imbriqués.

    Une PILE de styles, empilée à l'ouverture d'un span et dépilée à sa fermeture :
    c'est ce qui rend correct un span italique à l'intérieur d'un span gras, là où
    une expression régulière se perdrait.
    """
    pile = [{}]
    segments = []
    for m in _RE_JETON.finditer(inner):
        jeton = m.group(0)
        if re.match(r"<text:span\b", jeton):
            nom = re.search(r'\btext:style-name="([^"]*)"', jeton)
            styles = dict(pile[-1])
            if nom:
                styles.update(table.get(nom.group(1), {}))
            if not jeton.endswith("/>"):  # un span vide n'ouvre rien
                pile.append(styles)
            continue
        if re.match(r"</text:span\b", jeton):
            if len(pile) > 1:
                pile.pop()
            continue
        texte = _para_body(jeton)
        if texte:
            # La pile conserve l'état à trois valeurs (voir _styles_odt_props) ;
            # le segment, lui, ne porte que ce qui est réellement activé.
            segments.append((texte, {cle: val for cle, val in pile[-1].items() if val}))
    return segments


def _odt_table_paragraphes(xml):
    """Dictionnaire « nom de style de paragraphe » -> alignement, héritage résolu."""
    bruts = {}
    for debut, fin, _m in _blocs(xml, _OUVRE_STYLE_ODT, "</style:style>"):
        bloc = xml[debut:fin]
        entete = bloc[: bloc.find(">") + 1]
        if 'style:family="paragraph"' not in entete:
            continue
        nom = re.search(r'\bstyle:name="([^"]*)"', entete)
        if not nom:
            continue
        parent = re.search(r'\bstyle:parent-style-name="([^"]*)"', entete)
        props = re.search(r"<style:paragraph-properties\b([^>]*)>", bloc)
        aligne = None
        if props:
            m = _RE_ALIGN_ODT.search(props.group(1))
            if m:
                aligne = _ALIGNEMENTS.get(m.group(1).strip().lower())
        bruts[nom.group(1)] = (parent.group(1) if parent else None, aligne)

    table = {}
    for nom in bruts:
        courant, vus = nom, set()
        while courant in bruts and courant not in vus:
            vus.add(courant)
            if bruts[courant][1]:
                table[nom] = bruts[courant][1]
                break
            courant = bruts[courant][0]
    return table


def _odt_plages_listes(xml):
    """Positions des <text:list> : un paragraphe qui s'y trouve est un élément de liste."""
    plages, pile = [], []
    # Le garde (?=[\s/>]) est indispensable : sans lui, <text:list-item> passait
    # pour une ouverture de liste, alors que </text:list-item> ne la refermait pas —
    # et toute la fin du document se retrouvait a puces.
    for m in re.finditer(r"<text:list(?=[\s/>])[^>]*?(/?)>|</text:list>", xml):
        if m.group(0).startswith("</"):
            if pile:
                plages.append((pile.pop(), m.end()))
        elif not m.group(1):  # <text:list/> vide : rien à ouvrir
            pile.append(m.start())
    for reste in pile:  # document tronqué : la liste court jusqu'à la fin
        plages.append((reste, len(xml)))
    return plages


def _odt_dans_liste(position, plages):
    return any(debut <= position < fin for debut, fin in plages)


def _odt_segments(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "content.xml").decode("utf-8", "replace")
    corps = _odt_corps_taille(xml)
    table = _odt_table_styles(xml, corps)
    alignements = _odt_table_paragraphes(xml)
    listes = _odt_plages_listes(xml)
    segments = []
    # auto_fermant=False : le motif d'origine ne prévoyait pas « <text:p/> », qui reste
    # donc traité comme une ouverture — on ne change pas ce comportement.
    for rang, (_debut, fin, m) in enumerate(_blocs(xml, _OUVRE_PARA_ODT, _FERME_PARA_ODT, False)):
        if rang:
            segments.append(("\n", {}))
        tag = m.group(1)
        tete = xml.find(">", m.end())  # fin de l'en-tête « <text:p …> »
        attrs = xml[m.end() : tete]
        inner = xml[tete + 1 : fin - len(_FERME_PARA_ODT[tag])]
        niveau = 0
        if tag == "h":
            lvl = re.search(r'text:outline-level="(\d+)"', attrs)
            niveau = max(1, min(3, int(lvl.group(1)))) if lvl else 1
        nom_style = re.search(r'\btext:style-name="([^"]*)"', attrs)
        aligne = alignements.get(nom_style.group(1)) if nom_style else None
        puce = _odt_dans_liste(m.start(), listes)
        segments.extend(_titrer_segments(niveau, _odt_para_segments(inner, table), puce, aligne))
    return segments


def _from_docx(data):
    return "".join(texte for texte, _ in _docx_segments(data))


def _from_odt(data):
    return "".join(texte for texte, _ in _odt_segments(data))


# --------------------------------------------------------------------------
# Texte simple (.txt, .md, .text)
# --------------------------------------------------------------------------
# Un fichier texte ne contient AUCUN style : c'est sa définition même. Il a en
# revanche des CONVENTIONS d'écriture, les mêmes depuis quarante ans, que tout le
# monde reconnaît à l'œil : des astérisques autour d'un mot important, un tiret en
# début de ligne pour une puce. Ce sont elles qu'on lit ici — et comme ce sont des
# signes qui se tapent au clavier, elles marchent aussi dans la zone de saisie.
#
# La couleur et l'alignement n'ont, eux, aucune convention établie. Plutôt que de
# laisser ces deux cases vides, on les écrit en toutes lettres entre crochets :
# « [rouge]…[/rouge] », « [centre] … ». C'est plus long que deux astérisques, et
# c'est voulu — un marqueur nommé se relit six mois plus tard sans rien avoir à
# retenir, et il ne peut pas se déclencher par accident : seuls ces mots-là
# comptent, « [voir encadré] » ne produit rien.
#
# DEUX PRÉCAUTIONS, parce qu'une syntaxe qui se déclenche toute seule peut abîmer
# un texte existant :
#
# 1. Seules les paires SOIGNÉES comptent. Pour le gras, l'italique et le souligné,
#    le marqueur doit ouvrir contre un signe visible et fermer contre un signe
#    visible, au sein d'une même ligne. Un astérisque isolé (un appel de note), un
#    souligné au milieu d'un identifiant (« nom_du_fichier ») ou une
#    multiplication ne déclenchent rien.
# 2. La conversion n'a lieu qu'à l'IMPORT d'un fichier. Un texte déjà enregistré
#    dans la bibliothèque est relu tel quel, avec ses marques rangées à côté : il
#    ne peut donc pas changer d'aspect des mois plus tard, sous les yeux de
#    quelqu'un qui n'a rien demandé.
_OUVRANTS = "([{«“\"'"
_FERMANTS = ".,;:!?…)]}»”\"'"
# Les six couleurs du prompteur, nommées. L'ordre suit les pastilles de la
# zone de saisie, de gauche à droite. « blanc » sert à remettre en blanc un mot
# au milieu d'un passage coloré.
COULEURS_NOMMEES = {"jaune": 1, "rouge": 2, "vert": 3, "bleu": 4, "gris": 5, "blanc": 6}
_ALIGNEMENTS_NOMMES = {"centre": "center", "droite": "right"}
_RE_TXT_INLINE = re.compile(
    r"\[(?P<couleur>" + "|".join(COULEURS_NOMMEES) + r")\](?P<ctexte>.+?)\[/(?P=couleur)\]"
    r"|(?:(?<=^)|(?<=[\s" + re.escape(_OUVRANTS) + r"]))"
    r"(?:"
    r"\*\*(?P<b>\S(?:[^*\n]*\S)?)\*\*"
    r"|\*(?P<i>\S(?:[^*\n]*\S)?)\*"
    r"|_(?P<u>\S(?:[^_\n]*\S)?)_"
    r")"
    r"(?=$|[\s" + re.escape(_FERMANTS) + r"])"
)
PROFONDEUR_MAX_TXT = 6  # imbrication des marqueurs : au-delà, c'est du bruit


def _txt_inline_segments(texte, herites, profondeur=0):
    """Segments d'un fragment de ligne, marqueurs imbriqués compris.

    L'appel récursif est ce qui permet d'écrire « **[rouge]urgent[/rouge]** » :
    chaque marqueur AJOUTE son style à ceux qui l'entourent, au lieu de les
    remplacer.
    """
    if not texte:
        return []
    if profondeur >= PROFONDEUR_MAX_TXT:
        return [(texte, dict(herites))]
    segments = []
    pos = 0
    for m in _RE_TXT_INLINE.finditer(texte):
        if m.start() < pos:
            continue
        if m.group("couleur"):
            interieur, style = m.group("ctexte"), {"color": COULEURS_NOMMEES[m.group("couleur")]}
        else:
            cle = next(c for c in ("b", "i", "u") if m.group(c) is not None)
            interieur, style = m.group(cle), {cle: True}
        if m.start() > pos:
            segments.append((texte[pos : m.start()], dict(herites)))
        segments.extend(_txt_inline_segments(interieur, dict(herites, **style), profondeur + 1))
        pos = m.end()
    if pos < len(texte):
        segments.append((texte[pos:], dict(herites)))
    return segments


def _texte_ligne_segments(ligne):
    """Segments d'une ligne de texte simple, marqueurs d'écriture compris.

    Les marqueurs de DÉBUT DE LIGNE — « # », « - », « [centre] » — ne sont PAS
    retirés ici : l'écran de lecture les traduit lui-même. Une seule mécanique,
    donc, pour un fichier importé comme pour du texte tapé dans la zone de saisie,
    où aucune conversion n'a lieu. Un signe qui marcherait à l'import mais pas au
    clavier passerait pour une panne — et il n'y a d'ailleurs aucun bouton pour
    centrer une ligne : garder le marqueur, c'est garder de quoi le défaire.
    """
    return [(t, s) for t, s in _txt_inline_segments(ligne, {}) if t]


def _texte_segments(data):
    segments = []
    for rang, ligne in enumerate(_decode(data).split("\n")):
        if rang:
            segments.append(("\n", {}))
        segments.extend(_texte_ligne_segments(ligne))
    return segments


# --------------------------------------------------------------------------
# RTF
# --------------------------------------------------------------------------
# Le RTF, lui, DIT sa mise en forme : « \b » ouvre le gras, « \fs28 » fixe la
# taille, « \cf2 » désigne la deuxième couleur de la table des couleurs. Il n'y a
# donc rien à deviner — seulement à suivre correctement l'imbrication des
# accolades, car un style ouvert dans un groupe se referme à la fin de ce groupe.
#
# Le repli reste en place : si l'analyse échoue ou ne rend rien, on retombe sur
# l'extraction de texte simple d'avant. Un script qui arrive sans son gras vaut
# infiniment mieux qu'un script qui n'arrive pas.
_RE_RTF_JETON = re.compile(
    r"\\'([0-9a-fA-F]{2})"  # \'e9 : un octet écrit en hexadécimal
    r"|\\([a-zA-Z]+)(-?\d+)? ?"  # \b, \fs28, \cf2, \par...
    r"|\\([^a-zA-Z])"  # \\, \{, \}, \~ ...
    r"|([{}])"  # ouverture / fermeture de groupe
    r"|([^\\{}]+)"  # du texte ordinaire
)
# Groupes dont le CONTENU ne doit jamais arriver à l'écran : tables internes,
# propriétés du document, images. Les oublier remplirait le prompteur de réglages.
_RTF_DESTINATIONS = {
    "fonttbl",
    "colortbl",
    "stylesheet",
    "info",
    "pict",
    "object",
    "header",
    "footer",
    "headerl",
    "headerr",
    "footerl",
    "footerr",
    "footnote",
    "generator",
    "themedata",
    "colorschememapping",
    "latentstyles",
    "datastore",
    "listtable",
    "listoverridetable",
    "rsidtbl",
    "xmlnstbl",
    "mmathPr",
    "filetbl",
    "revtbl",
    "upr",
    "annotation",
    "atnid",
    "atnauthor",
}
# Groupes dont le contenu est le REPÈRE de puce, et rien d'autre : on ne le garde
# pas tel quel (c'est souvent un caractère de police symbole), on note la puce.
_RTF_PUCES = {"pntext", "listtext"}
_RTF_CARACTERES = {
    "tab": "\t",
    "line": "\n",
    "emdash": "\u2014",
    "endash": "\u2013",
    "lquote": "\u2018",
    "rquote": "\u2019",
    "ldblquote": "\u201c",
    "rdblquote": "\u201d",
    "bullet": "\u2022",
    "enspace": " ",
    "emspace": " ",
    "nbsp": "\u00a0",
}
_RTF_ALIGNEMENTS = {"qc": "center", "qr": "right", "ql": None, "qj": None}
_DEFAUT_FS_RTF = 24  # 12 points, en demi-points comme l'écrit le RTF


def _rtf_couleurs(source):
    """Table des couleurs : indice RTF -> numéro de palette du prompteur.

    L'indice 0 est la couleur « automatique » : la table commence par un « ; »
    vide. Le confondre avec la première vraie couleur décalerait tout d'un cran.
    """
    m = re.search(r"\{\\colortbl(.*?)\}", source, re.S)
    if not m:
        return {}
    table = {}
    for indice, entree in enumerate(m.group(1).split(";")):
        r = re.search(r"\\red(\d+)", entree)
        v = re.search(r"\\green(\d+)", entree)
        b = re.search(r"\\blue(\d+)", entree)
        if not (r and v and b):
            continue  # entrée vide = couleur automatique : aucune marque
        octets = tuple(max(0, min(255, int(x.group(1)))) for x in (r, v, b))
        numero = _couleur_palette("%02x%02x%02x" % octets)
        if numero:
            table[indice] = numero
    return table


def _rtf_analyse(source):
    """Découpe un RTF en segments (texte, styles), accolades comprises."""
    couleurs = _rtf_couleurs(source)
    etat = {"b": False, "i": False, "u": False, "fs": None, "cf": 0}
    pile = []
    profondeur = 0
    saut = None  # profondeur du groupe ignoré, le cas échéant
    uc = 1  # nombre de caractères de repli à sauter après un \u
    a_sauter = 0
    haut = None  # première moitié d'un caractère hors BMP, en attente de la seconde

    bruts = []  # (texte, etat fige) du paragraphe courant
    paragraphes = []  # listes de bruts
    aligne = None
    puce = False

    def ajouter(texte):
        nonlocal a_sauter
        if a_sauter > 0:  # repli d'un \u déjà rendu : on le jette
            pris = min(a_sauter, len(texte))
            a_sauter -= pris
            texte = texte[pris:]
        if texte and saut is None:
            bruts.append((texte, dict(etat)))

    def finir_paragraphe():
        nonlocal bruts, aligne, puce
        paragraphes.append((bruts, aligne, puce))
        bruts, puce = [], False

    for m in _RE_RTF_JETON.finditer(source):
        hexa, mot, param, echappe, accolade, texte = m.groups()
        if accolade == "{":
            profondeur += 1
            pile.append(dict(etat))
            continue
        if accolade == "}":
            profondeur -= 1
            if pile:
                etat = pile.pop()
            if saut is not None and profondeur < saut:
                saut = None
            continue
        if saut is not None:
            continue
        if hexa:
            ajouter(bytes([int(hexa, 16)]).decode("cp1252", "replace"))
            continue
        if echappe == "*":
            # « {\\*\\motcle …} » : destination IGNORABLE. Un lecteur qui ne connaît
            # pas le mot-clé doit sauter tout le groupe — c'est la règle du format.
            # Sans cela, numérotation, champs et tables de Word fuyaient à l'écran.
            saut = profondeur
            continue
        if echappe:
            ajouter({"\\": "\\", "{": "{", "}": "}", "~": "\u00a0", "-": "", "_": "-"}.get(echappe, ""))
            continue
        if texte:
            ajouter(texte)
            continue
        if not mot:
            continue
        valeur = int(param) if param else None
        if mot == "*" or mot in _RTF_DESTINATIONS:
            saut = profondeur
        elif mot in _RTF_PUCES:
            puce = True
            saut = profondeur
        elif mot == "u" and valeur is not None:
            code = valeur % 65536
            if 0xD800 <= code < 0xDC00:
                # Première moitié d'un emoji : Word l'écrit en DEUX \\u. On attend
                # la seconde pour les réunir, au lieu de les perdre toutes les deux.
                haut = code
            elif 0xDC00 <= code < 0xE000 and haut is not None:
                ajouter(chr(0x10000 + ((haut - 0xD800) << 10) + (code - 0xDC00)))
                haut = None
            else:
                haut = None
                ajouter(chr(code))
            a_sauter = uc
        elif mot == "uc" and valeur is not None:
            uc = max(0, valeur)
        elif mot in ("b", "i", "ul"):
            # « ul » est le nom RTF du souligne ; notre cle, c'est « u ». Sans cette
            # traduction, on alimentait une cle fantome et le souligne se perdait.
            etat["u" if mot == "ul" else mot] = valeur != 0
        elif mot in ("ulnone", "ulw"):
            etat["u"] = False
        elif mot == "fs" and valeur:
            etat["fs"] = valeur
        elif mot == "cf":
            etat["cf"] = valeur or 0
        elif mot in _RTF_ALIGNEMENTS:
            aligne = _RTF_ALIGNEMENTS[mot]
        elif mot == "pard":
            aligne = None
        elif mot == "par":
            finir_paragraphe()
        elif mot in _RTF_CARACTERES:
            ajouter(_RTF_CARACTERES[mot])
    finir_paragraphe()

    # La taille du corps du texte, comme ailleurs : la plus répandue, en comptant
    # les passages qui n'en déclarent aucune pour la valeur par défaut.
    tailles = []
    for bruts_p, _a, _p in paragraphes:
        for txt, st in bruts_p:
            tailles.extend([st["fs"] or _DEFAUT_FS_RTF] * max(1, len(txt.strip())))
    corps = _mode_des_tailles(tailles, _DEFAUT_FS_RTF)

    segments = []
    for rang, (bruts_p, align_p, puce_p) in enumerate(paragraphes):
        if rang:
            segments.append(("\n", {}))
        # Un paragraphe ENTIEREMENT plus gros que le corps est un titre, et non un
        # passage agrandi : comme dans un PDF, c'est ainsi qu'un RTF ecrit ses titres.
        avec_texte = [st["fs"] or corps for txt, st in bruts_p if txt.strip()]
        entiere = min(avec_texte) if avec_texte else 0
        niveau = 0
        if corps and entiere >= corps * 1.45:
            niveau = 1
        elif corps and entiere >= corps * 1.15:
            niveau = 2
        para = []
        for txt, st in bruts_p:
            styles = {cle: True for cle in ("b", "i", "u") if st[cle]}
            if couleurs.get(st["cf"]):
                styles["color"] = couleurs[st["cf"]]
            if not niveau and st["fs"] and corps:
                relative = _taille_relative(st["fs"] / float(corps))
                if relative:
                    styles["size"] = relative
            para.append((txt, styles))
        segments.extend(_titrer_segments(niveau, para, puce_p, align_p))
    return segments


def _rtf_plat(data):
    """Repli : le texte seul, sans mise en forme (comportement d'origine)."""
    text = _decode(data)
    try:
        from striprtf.striprtf import rtf_to_text

        return rtf_to_text(text)
    except ImportError:
        # repli minimal : retire les échappements et commandes RTF, puis les accolades
        text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
        return text.replace("{", "").replace("}", "")


def _rtf_segments(data):
    source = _decode(data)
    try:
        segments = _rtf_analyse(source)
    except Exception:  # noqa: BLE001 - un RTF biscornu ne doit pas faire perdre le texte
        segments = []
    if "".join(t for t, _ in segments).strip():
        return segments
    return [(_rtf_plat(data), {})]


def _from_rtf(data):
    return "".join(texte for texte, _ in _rtf_segments(data))


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
# Un PDF ne dit pas « ce mot est en gras » : il dit « ce mot est peint avec la
# police Arial-BoldMT ». Le gras, l'italique, la taille, la couleur, le centrage
# et le soulignement doivent donc être DÉDUITS de la façon dont la page est
# peinte. Le soulignement, en particulier, n'est pas une propriété du texte mais
# un TRAIT dessiné dessous : on le retrouve par la géométrie, en rapprochant les
# traits horizontaux du texte qui passe juste au-dessus.
#
# On ne remplace pas pour autant l'extraction de texte existante : elle reste
# maîtresse du découpage en lignes et de l'espacement, que pypdf calcule mieux
# qu'un recollage de morceaux. Les morceaux observés sont ensuite REPOSÉS sur ce
# texte, dans l'ordre où ils sont venus. Le texte ne change donc pas d'un iota
# par rapport à la version précédente : on ne fait qu'ajouter par-dessus.
_MOTS_GRAS = ("bold", "black", "heavy", "semibold", "demibold")
_MOTS_ITALIQUE = ("italic", "oblique")
MAX_MORCEAUX_PDF = 20000  # borne de coût sur un PDF pathologique
# Largeur approximative d'un signe, en fraction de la taille de police. Sert
# UNIQUEMENT à situer un trait de soulignement dans une ligne, et le résultat est
# ensuite recalé sur les limites de mots — un mot n'est jamais souligné à moitié.
#
# Une moyenne unique ne suffisait pas : elle se trompait de deux à cinq signes,
# c'est-à-dire d'un mot entier une fois recalée. Distinguer les signes étroits des
# larges ramène l'erreur à un signe au plus, ce que le recalage absorbe.
_CHASSE_ETROITE = set(" ijltfI.,:;!'|()[]/-")
_CHASSE_LARGE = set("mwMW@")


def _chasse(c):
    if c in _CHASSE_ETROITE:
        return 0.28
    if c in _CHASSE_LARGE:
        return 0.85
    if c.isupper():
        return 0.70
    if c.isdigit():
        return 0.56
    return 0.53


def _indice_a_la_distance(texte, distance, taille):
    """Indice du signe atteint après une distance donnée depuis le début de la ligne."""
    if taille <= 0:
        return 0
    cumul = 0.0
    for i, c in enumerate(texte):
        if cumul * taille >= distance:
            return i
        cumul += _chasse(c)
    return len(texte)


def _police_styles(nom):
    """Gras / italique déduits du nom de la police (Arial-BoldMT, Times-Italic...)."""
    bas = str(nom or "").lower()
    styles = {}
    if any(mot in bas for mot in _MOTS_GRAS):
        styles["b"] = True
    if any(mot in bas for mot in _MOTS_ITALIQUE):
        styles["i"] = True
    return styles


def _couleur_operateur(op, args):
    """Couleur de remplissage du texte -> numéro de palette, ou None.

    « rg » est du RVB, « g » du gris, « k » du CMJN. Les valeurs vont de 0 à 1.
    """
    try:
        vals = [float(a) for a in args]
    except (TypeError, ValueError):
        return None
    if op == "rg" and len(vals) >= 3:
        r, v, b = vals[:3]
    elif op == "g" and len(vals) >= 1:
        r = v = b = vals[0]
    elif op == "k" and len(vals) >= 4:
        c, m, j, n = vals[:4]
        r, v, b = 1 - min(1, c + n), 1 - min(1, m + n), 1 - min(1, j + n)
    else:
        return None
    octets = tuple(max(0, min(255, round(x * 255))) for x in (r, v, b))
    return _couleur_palette("%02x%02x%02x" % octets)


def _matrice(m):
    """Une matrice PDF utilisable, ou l'identité si elle est absente ou illisible."""
    try:
        vals = [float(x) for x in m]
        return vals if len(vals) >= 6 else [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    except (TypeError, ValueError):
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def _point_page(cm, x, y):
    """Un point exprimé dans le repère courant, ramené au repère de la page.

    Sans ce passage, tout ce qui suit est faux sur la plupart des vrais PDF : Word
    et LibreOffice ne déplacent pas le curseur de texte, ils déplacent le REPÈRE.
    Deux lignes différentes portent alors exactement la même position de texte, et
    tout le document passerait pour une seule ligne.
    """
    return (x * cm[0] + y * cm[2] + cm[4], x * cm[1] + y * cm[3] + cm[5])


def _echelle(cm):
    """Facteur d'agrandissement du repère courant (1 s'il ne fait que déplacer)."""
    aire = abs(cm[0] * cm[3] - cm[1] * cm[2])
    return aire**0.5 if aire > 0 else 1.0


def _pdf_morceaux(page):
    """Texte de la page, morceaux de texte observés, et traits horizontaux dessinés."""
    morceaux, traits = [], []
    etat = {"couleur": None, "point": None}

    def avant_operateur(op, args, cm, tm):
        nom = op.decode("ascii", "replace") if isinstance(op, bytes) else str(op)
        if nom in ("rg", "g", "k"):
            etat["couleur"] = _couleur_operateur(nom, args)
            return
        if nom not in ("m", "l", "re"):
            return
        matrice = _matrice(cm)
        try:
            vals = [float(a) for a in args]
        except (TypeError, ValueError):
            return
        if nom == "m" and len(vals) >= 2:
            etat["point"] = _point_page(matrice, vals[0], vals[1])
        elif nom == "l" and len(vals) >= 2 and etat["point"]:
            x1, y1 = etat["point"]
            x2, y2 = _point_page(matrice, vals[0], vals[1])
            if abs(y2 - y1) < 1.2:  # un soulignement est horizontal
                traits.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2.0))
            etat["point"] = (x2, y2)
        elif nom == "re" and len(vals) >= 4:
            # Beaucoup de logiciels soulignent avec un rectangle très plat.
            x, y, larg, haut = vals[:4]
            if abs(haut) * _echelle(matrice) < 3.0 and abs(larg) > 1.0:
                xa, ya = _point_page(matrice, x, y)
                xb, _yb = _point_page(matrice, x + larg, y)
                traits.append((min(xa, xb), max(xa, xb), ya))

    def a_chaque_texte(texte, cm, tm, police, taille):
        if not texte or not texte.strip() or len(morceaux) >= MAX_MORCEAUX_PDF:
            return
        matrice, tmat = _matrice(cm), _matrice(tm)
        x, y = _point_page(matrice, tmat[4], tmat[5])
        morceaux.append(
            {
                "texte": texte,
                "police": police.get("/BaseFont") if hasattr(police, "get") else None,
                "taille": float(taille or 0) * _echelle(matrice) * _echelle(tmat),
                "x": x,
                "y": y,
                "couleur": etat["couleur"],
            }
        )

    texte = page.extract_text(visitor_text=a_chaque_texte, visitor_operand_before=avant_operateur)
    return texte, morceaux, traits


def _pdf_lignes(morceaux):
    """Regroupe les morceaux par ligne (même hauteur sur la page)."""
    lignes, courante = [], []
    for m in morceaux:
        if courante and abs(m["y"] - courante[-1]["y"]) > 1.5:
            lignes.append(courante)
            courante = []
        courante.append(m)
    if courante:
        lignes.append(courante)
    return lignes


def _limites_de_mots(texte):
    """Positions où un mot commence ou finit — les seules coupures acceptables."""
    bornes = {0, len(texte)}
    for m in re.finditer(r"\S+", texte):
        bornes.add(m.start())
        bornes.add(m.end())
    return sorted(bornes)


def _recale_sur_un_mot(bornes, approx):
    """Ramène une position approximative sur la limite de mot la plus proche.

    L'estimation en largeur de signes se trompe de deux ou trois caractères ; un
    soulignement qui commencerait au milieu d'un mot se verrait immédiatement. Les
    documents, eux, soulignent des mots entiers.
    """
    return min(bornes, key=lambda b: abs(b - approx))


def _pdf_alignement(ligne, marge_corps, largeur_page):
    """Centré / à droite, déduits de la position de la ligne sur la page.

    Une ligne qui commence à la marge ordinaire est alignée à gauche : c'est le cas
    de l'immense majorité, et on ne pose alors aucune marque.
    """
    if not ligne or not largeur_page:
        return None
    gauche = ligne[0]["x"]
    if gauche <= marge_corps + 12:
        return None
    # Largeur estimée : un PDF ne la donne pas. Une demi-chasse par signe est
    # grossier, mais suffit à distinguer « centré » de « collé à droite ».
    signes = sum(len(m["texte"]) for m in ligne)
    taille = max(m["taille"] for m in ligne) or 12.0
    largeur = 0.5 * taille * signes
    if abs(gauche + largeur / 2.0 - largeur_page / 2.0) < largeur_page * 0.07:
        return "center"
    if gauche + largeur > largeur_page - marge_corps - 12:
        return "right"
    return None


def _pdf_souligne(ligne, traits, texte_ligne, decalage):
    """Plages de caractères soulignées, en indices du TEXTE PRODUIT.

    On raisonne sur la ligne telle que l'extraction l'a rendue, et non sur le
    recollage des morceaux : pypdf insère des espaces entre eux, et travailler sur
    le recollage décalait les indices de plusieurs signes — donc d'un mot entier
    une fois recalé.
    """
    if not texte_ligne.strip() or not traits:
        return []
    base = ligne[0]["y"]
    taille = max((m["taille"] for m in ligne), default=12.0) or 12.0
    debut_x = min(m["x"] for m in ligne)
    if taille <= 0:
        return []
    bornes = _limites_de_mots(texte_ligne)
    plages = []
    for x0, x1, y in traits:
        # Le trait doit passer JUSTE sous la ligne : plus bas, c'est un cadre ou un
        # filet de mise en page, et souligner tout un paragraphe serait pire que rien.
        if not (base - 0.45 * taille <= y <= base + 0.05 * taille):
            continue
        i = _recale_sur_un_mot(bornes, _indice_a_la_distance(texte_ligne, x0 - debut_x, taille))
        j = _recale_sur_un_mot(bornes, _indice_a_la_distance(texte_ligne, x1 - debut_x, taille))
        if j > i:
            plages.append((decalage + i, decalage + j))
    return plages


def _decoupe_selon_souligne(texte, depart, plages):
    """Découpe un morceau en sous-morceaux selon ce qui y est souligné.

    depart est la position du morceau dans le texte produit ; les plages sont dans
    le même repère. Un seul repère pour tout le monde, sinon la mise en forme tombe
    à côté des mots qu'elle vise.
    """
    coupes = {0, len(texte)}
    for i, j in plages:
        for b in (i - depart, j - depart):
            if 0 < b < len(texte):
                coupes.add(b)
    bouts = []
    ordonnees = sorted(coupes)
    # strict=False assume : les deux listes different d'un element, par construction.
    for a, b in zip(ordonnees, ordonnees[1:], strict=False):
        milieu = depart + (a + b) / 2.0
        bouts.append((texte[a:b], any(i <= milieu <= j for i, j in plages)))
    return bouts


def _pdf_page_segments(page, corps):
    texte, morceaux, traits = _pdf_morceaux(page)
    if not texte or not morceaux:
        return [(texte or "", {})]
    try:
        largeur_page = float(page.mediabox.width)
    except (AttributeError, TypeError, ValueError):
        largeur_page = 0.0

    lignes = _pdf_lignes(morceaux)
    marge_corps = _mode_des_tailles([round(li[0]["x"]) for li in lignes], 0)

    # 1. Situer chaque morceau dans le texte produit, une fois pour toutes.
    pos = 0
    for ligne in lignes:
        for m in ligne:
            noyau = m["texte"].strip()
            m["noyau"] = noyau
            m["ou"] = texte.find(noyau, pos) if noyau else -1
            if m["ou"] >= 0:
                pos = m["ou"] + len(noyau)

    # 2. Ce qui appartient à la LIGNE : alignement, niveau de titre, soulignement.
    for ligne in lignes:
        places = [m for m in ligne if m["ou"] >= 0]
        aligne = _pdf_alignement(ligne, marge_corps, largeur_page)
        souligne = []
        if places:
            debut = places[0]["ou"]
            fin = places[-1]["ou"] + len(places[-1]["noyau"])
            souligne = _pdf_souligne(ligne, traits, texte[debut:fin], debut)
        # Une ligne ENTIÈREMENT plus grosse que le corps est un titre, et non un
        # passage agrandi : faute de styles, c'est ainsi qu'un PDF écrit ses titres.
        entiere = min(m["taille"] for m in ligne)
        niveau = 0
        if corps and entiere >= corps * 1.45:
            niveau = 1
        elif corps and entiere >= corps * 1.15:
            niveau = 2
        for m in ligne:
            styles = _police_styles(m["police"])
            if m["couleur"]:
                styles["color"] = m["couleur"]
            if not niveau and corps:
                relative = _taille_relative(m["taille"] / corps)
                if relative:
                    styles["size"] = relative
            if aligne:
                styles["align"] = aligne
            m["styles"] = styles
            m["souligne"] = souligne
        ligne[0]["niveau"] = niveau

    # 3. Reposer les morceaux sur le texte produit, dans l'ordre d'arrivée.
    segments = []
    pos = 0
    for ligne in lignes:
        for rang, m in enumerate(ligne):
            if m["ou"] < 0:
                continue  # morceau que l'extraction n'a pas restitué tel quel
            if m["ou"] > pos:
                segments.append((texte[pos : m["ou"]], {}))
            if rang == 0 and ligne[0].get("niveau"):
                segments.append(("#" * ligne[0]["niveau"] + " ", {}))
            for bout, souligne in _decoupe_selon_souligne(m["noyau"], m["ou"], m["souligne"]):
                if bout:
                    segments.append((bout, dict(m["styles"], u=True) if souligne else m["styles"]))
            pos = m["ou"] + len(m["noyau"])
    if pos < len(texte):
        segments.append((texte[pos:], {}))
    return segments


def _pdf_corps_taille(pages_morceaux):
    """Taille du corps du texte : la plus répandue, pondérée par le nombre de signes."""
    tailles = []
    for morceaux in pages_morceaux:
        for m in morceaux:
            tailles.extend([round(m["taille"], 1)] * max(1, len(m["texte"].strip())))
    return _mode_des_tailles(tailles, 0) or 0


def _pdf_segments(data):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    # Deux passes : la première pour connaître la taille du corps du texte, qui sert
    # de référence à tout le reste. Sans elle, « plus gros que le reste » n'a pas de
    # sens — et c'est la seule chose qu'un prompteur doive retenir d'une taille.
    corps = _pdf_corps_taille([_pdf_morceaux(page)[1] for page in reader.pages])
    segments = []
    for rang, page in enumerate(reader.pages):
        if rang:
            segments.append(("\n\n", {}))
        segments.extend(_pdf_page_segments(page, corps))
    return segments


def _from_pdf(data):
    return "".join(texte for texte, _ in _pdf_segments(data))


# --------------------------------------------------------------------------
# DOC (ancien format binaire Word) — nécessite antiword ou catdoc
# --------------------------------------------------------------------------
def _from_doc(data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tf:
            tf.write(data)
            tmp = tf.name
        # Options explicites : sans elles, antiword coupe chaque paragraphe en
        # lignes de 78 colonnes (des lignes hachées à l'écran), et écrit dans le
        # jeu de caractères de la session — celle du service systemd n'en a pas,
        # et les accents se perdaient.
        outils = (
            ("antiword", ["-w", "0", "-m", "UTF-8.txt"]),
            ("catdoc", ["-w", "-d", "utf-8"]),
        )
        for tool, options in outils:
            try:
                out = subprocess.run(  # nosec B603 - binaire fixe, sans shell, chemin contrôlé
                    [tool, *options, tmp], capture_output=True, timeout=20, check=False
                )
                if out.returncode == 0 and out.stdout.strip():
                    try:
                        return out.stdout.decode("utf-8")
                    except UnicodeDecodeError:
                        return out.stdout.decode("latin-1")
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
# Des segments stylés aux plages posées sur le texte nettoyé
# --------------------------------------------------------------------------
def _plages_depuis_segments(segments, origines, texte):
    """Convertit les segments stylés en plages d'indices du texte NETTOYÉ."""
    # Fusion des segments voisins de mêmes styles : Word découpe volontiers une
    # phrase en gras en cinq runs (correcteur orthographique, identifiants de
    # révision). Sans fusion, on dépasserait les 500 plages sur un texte ordinaire.
    fusionnes = []
    position = 0
    for texte_brut, styles in segments:
        debut, position = position, position + len(texte_brut)
        if fusionnes and fusionnes[-1][2] == styles:
            fusionnes[-1][1] = position
        else:
            fusionnes.append([debut, position, styles])

    plages = []
    for debut, fin, styles in fusionnes:
        if not styles:
            continue
        # Bissection : premier caractère nettoyé issu de [debut, fin[.
        i = bisect.bisect_left(origines, debut)
        j = bisect.bisect_left(origines, fin)
        # Les blancs de bord sont rognés EN COORDONNÉES NETTOYÉES : un run « gras »
        # ne doit pas souligner l'espace qui le suit (un espace souligné se voit).
        while i < j and texte[i].isspace():
            i += 1
        while j > i and texte[j - 1].isspace():
            j -= 1
        if j <= i:
            continue  # run vide après nettoyage : on l'abandonne plutôt que d'émettre une plage fausse
        if plages and plages[-1]["end"] >= i and _memes_styles(plages[-1], styles):
            plages[-1]["end"] = j
            continue
        plages.append({"start": i, "end": j, **styles})
    return plages[:MAX_MARKS]


def _memes_styles(plage, styles):
    return {cle: val for cle, val in plage.items() if cle not in ("start", "end")} == styles


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

# Formats dont on sait lire la mise en forme. Les autres passent par _EXTRACTORS
# et donnent un unique segment sans style.
_SEGMENTEURS = {
    ".docx": _docx_segments,
    ".odt": _odt_segments,
    ".pdf": _pdf_segments,
    ".rtf": _rtf_segments,
    ".txt": _texte_segments,
    ".md": _texte_segments,
    ".text": _texte_segments,
}


def extract_rich(filename, data):
    """Extrait le texte ET sa mise en forme : renvoie (texte, plages).

    Les plages sont au format attendu par server.sanitize_marks() :
    {"start": int, "end": int, "b"/"i"/"u": True}, indices portant sur le texte
    renvoyé. Lève ValueError avec un message clair si le format ne peut pas être lu.
    """
    ext = Path(filename or "").suffix.lower()
    # Garde-barriere UNIQUE, ici et pas dans chaque appelant : sans elle, un fichier
    # qui n'est pas un document (une photo, une archive) tombait dans le decodage
    # texte de secours et remplissait la zone de texte d'octets illisibles, sans le
    # moindre message. Mieux vaut un refus clair qu'un ecran de charabia.
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            "Ce fichier n'est pas un document texte (%s). "
            "Formats acceptés : %s." % (ext or "sans extension", ", ".join(SUPPORTED_EXTS))
        )
    segmenteur = _SEGMENTEURS.get(ext)
    extractor = _EXTRACTORS.get(ext)
    try:
        if segmenteur:
            segments = segmenteur(data)
        else:
            segments = [(extractor(data) if extractor else _decode(data), {})]
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 - on renvoie un message lisible à l'utilisateur
        raise ValueError(f"Impossible de lire ce fichier ({ext or 'inconnu'}) : {e}") from e
    brut = "".join(texte for texte, _ in segments)
    # Borné DEUX fois : sur le texte brut d'abord, car le nettoyage parcourt la chaîne
    # caractère par caractère et coûterait des dizaines de secondes sur un Pi ; puis
    # sur le résultat, qui est ce qui partira réellement à l'écran.
    check_size(brut)
    texte, origines = _clean_indexed(brut)
    check_size(texte)
    return texte, _plages_depuis_segments(segments, origines, texte)


def extract_text(filename, data):
    """Extrait puis nettoie le texte d'un fichier (donné par son nom + ses octets).

    Lève ValueError avec un message clair si le format ne peut pas être lu."""
    return extract_rich(filename, data)[0]
