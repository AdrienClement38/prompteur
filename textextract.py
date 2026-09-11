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
_VALEURS_OFF = ("0", "false", "off", "none")


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


def _titrer_segments(niveau, segments):
    """Préfixe les dièses de titre, comme _mark(), en un segment sans style."""
    segments = _rogner_segments(segments)
    if niveau and segments:
        segments.insert(0, ("#" * niveau + " ", {}))
    return segments


def _actif(balise):
    """Une balise de style Word est-elle activée ? (<w:b/> oui, <w:b w:val="0"/> non)"""
    m = re.search(r'\bw:val="([^"]*)"', balise)
    return not (m and m.group(1).strip().lower() in _VALEURS_OFF)


def _styles_docx_rpr(rpr_xml):
    """Gras / italique / souligné lus dans un <w:rPr> de .docx."""
    styles = {}
    for cle, motif in (("b", r"<w:b\b[^>]*>"), ("i", r"<w:i\b[^>]*>"), ("u", r"<w:u\b[^>]*>")):
        m = re.search(motif, rpr_xml)
        if m and _actif(m.group(0)):
            styles[cle] = True
    return styles


def _styles_docx_run(run_xml):
    m = _RE_RPR_DOCX.search(run_xml)
    return _styles_docx_rpr(m.group(1)) if m else {}


def _docx_para_segments(p_xml):
    """Découpe un paragraphe .docx en segments (texte, styles)."""
    niveau = _docx_heading_level(p_xml)
    segments = []
    pos = 0
    for debut, fin, _m in _blocs(p_xml, _OUVRE_RUN_DOCX, "</w:r>"):
        if debut > pos:  # hors run : <w:pPr>, <w:br/> isolé, etc.
            segments.append((_para_body(p_xml[pos:debut]), {}))
        run_xml = p_xml[debut:fin]
        segments.append((_para_body(run_xml), _styles_docx_run(run_xml)))
        pos = fin
    if pos < len(p_xml):
        segments.append((_para_body(p_xml[pos:]), {}))
    return _titrer_segments(niveau, segments)


def _docx_segments(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "word/document.xml").decode("utf-8", "replace")
    segments = []
    for rang, (debut, fin, _m) in enumerate(_blocs(xml, _OUVRE_PARA_DOCX, "</w:p>")):
        if rang:
            segments.append(("\n", {}))
        segments.extend(_docx_para_segments(xml[debut:fin]))
    return segments


def _styles_odt_props(props_xml):
    """Gras / italique / souligné lus dans un <style:text-properties> d'ODT.

    Renvoie un état à TROIS valeurs : clé absente = « le style ne se prononce pas,
    on garde ce qui est hérité » ; True = activé ; False = DÉSACTIVÉ EXPLICITEMENT.

    Cette troisième valeur n'est pas un raffinement, elle est indispensable. Dans un
    .odt, la mise en forme des caractères se CUMULE : un span dans un span, et un
    style qui hérite de son parent. Quand on dégrasse un mot au milieu d'une phrase
    en gras, LibreOffice n'enlève rien au span extérieur — il imbrique un span
    portant fo:font-weight="normal". Sans le False, l'annulation passait inaperçue
    et le mot dégrassé ressortait EN GRAS : la mise en forme tombait sur les
    mauvais mots, précisément ce qu'on cherche à éviter.
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
    return styles


def _odt_table_styles(xml):
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
            _styles_odt_props(props.group(1)) if props else {},
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
            segments.append((texte, {cle: True for cle, val in pile[-1].items() if val}))
    return segments


def _odt_segments(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = _read_zip_entry(z, "content.xml").decode("utf-8", "replace")
    table = _odt_table_styles(xml)
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
        segments.extend(_titrer_segments(niveau, _odt_para_segments(inner, table)))
    return segments


def _from_docx(data):
    return "".join(texte for texte, _ in _docx_segments(data))


def _from_odt(data):
    return "".join(texte for texte, _ in _odt_segments(data))


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
}


def extract_rich(filename, data):
    """Extrait le texte ET sa mise en forme : renvoie (texte, plages).

    Les plages sont au format attendu par server.sanitize_marks() :
    {"start": int, "end": int, "b"/"i"/"u": True}, indices portant sur le texte
    renvoyé. Lève ValueError avec un message clair si le format ne peut pas être lu.
    """
    ext = Path(filename or "").suffix.lower()
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
