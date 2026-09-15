# -*- coding: utf-8 -*-
"""Convertisseur Markdown -> PDF imprimable (reportlab) pour les guides du Prompteur."""

import io
import os
import re
import sys
import unicodedata

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# Polices. Windows d'abord (c'est là que les guides sont écrits), puis les noms
# Linux : le script doit rester lançable ailleurs, et surtout DIRE ce qui manque
# plutôt que d'échouer sur une trace illisible.
_PISTES = (
    (
        "C:/Windows/Fonts/",
        {
            "Body": "arial.ttf",
            "Body-B": "arialbd.ttf",
            "Body-I": "ariali.ttf",
            "Body-BI": "arialbi.ttf",
            "Mono": "consola.ttf",
            "Sym": "seguisym.ttf",
        },
    ),
    (
        "/usr/share/fonts/truetype/dejavu/",
        {
            "Body": "DejaVuSans.ttf",
            "Body-B": "DejaVuSans-Bold.ttf",
            "Body-I": "DejaVuSans-Oblique.ttf",
            "Body-BI": "DejaVuSans-BoldOblique.ttf",
            "Mono": "DejaVuSansMono.ttf",
            "Sym": "DejaVuSans.ttf",
        },
    ),
)


def _charger_polices():
    for dossier, fichiers in _PISTES:
        if all(os.path.exists(dossier + f) for f in fichiers.values()):
            for nom, fichier in fichiers.items():
                pdfmetrics.registerFont(TTFont(nom, dossier + fichier))
            return dossier
    saut = chr(10)
    raise SystemExit(
        "Polices introuvables. Ce convertisseur cherche, dans l'ordre :"
        + saut
        + saut.join("  " + d for d, _ in _PISTES)
        + saut
        + "Sur Debian/Ubuntu : sudo apt install fonts-dejavu-core"
    )


FONTS = _charger_polices()
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B", italic="Body-I", boldItalic="Body-BI")

GLYPHS = pdfmetrics.getFont("Body").face.charToGlyph
SYM_GLYPHS = pdfmetrics.getFont("Sym").face.charToGlyph
TOK = "\x01"

# Pictogrammes de tete d'encadre -> libelles imprimables (lecture en noir et blanc)
PICTO = {
    "\u26a0": "ATTENTION",
    "\U0001f198": "SI CELA NE MARCHE PAS",
    "\u270d": "A NOTER SUR PAPIER",
    "\U0001f4a1": "BON A SAVOIR",
    "\U0001f4cc": "A RETENIR",
    "\u26d4": "A NE PAS FAIRE",
    "\u274c": "A NE PAS FAIRE",
    "\u2705": "VERIFICATION",
    "\U0001f4e6": "DEBALLAGE",
    "\U0001f5a8": "IMPRESSION",
    "\u2702": "A DECOUPER",
    "\u2b50": "L'ESSENTIEL",
    "\U0001f4f1": "TELEPHONE",
    "\u2328": "CLAVIER",
    "\U0001f501": "REDEMARRAGE",
    "\u260e": "APPELER",
    "\U0001f4cb": "NOTE",
    "\U0001f4e5": "A PREPARER AVANT",
    "\U0001f511": "MOT DE PASSE",
    "\U0001f4d8": "DOCUMENT",
    "\U0001f4fb": "LE PROMPTEUR",
    "\U0001f9ed": "REPERES",
    "\U0001f5e3": "A DIRE A VOIX HAUTE",
    "\U0001f6d1": "STOP",
    "\U0001f9ea": "TEST",
    "\U0001f500": "AU CHOIX",
    "\u2753": "QUESTION",
    "\u2139": "INFO",
    "\U0001f527": "REGLAGE",
    "\U0001f3ac": "TOURNAGE",
    "\U0001f4c4": "DOCUMENT",
}

# Caracteres invisibles a supprimer (selecteurs de variante, liant emoji)
DROP = ("\ufe0f", "\ufe0e", "\u200d")


def clean(text):
    """Rend le texte imprimable : symboles balises pour la police Sym, emoji -> libelle."""
    for ch in DROP:
        text = text.replace(ch, "")
    out = []
    for ch in text:
        code = ord(ch)
        if code < 128 or code in GLYPHS:
            out.append(ch)
        elif code <= 0xFFFF and code in SYM_GLYPHS:
            # Au-dela de U+FFFF, reportlab produit une table ToUnicode invalide
            # (le copier-coller depuis le PDF devient illisible) : ces caracteres
            # passent donc toujours par un libelle texte.
            out.append(TOK + ch + TOK)
        elif ch in PICTO:
            out.append(PICTO[ch])
    return "".join(out)


def plain(text):
    """Texte tel qu'il sera imprime, sans balisage : sert a mesurer les colonnes."""
    return clean(re.sub(r"[*`_]", "", text)).replace(TOK, "").strip()


def fold(text):
    """Forme comparable d'un texte : sans accents, sans ponctuation, en majuscules."""
    text = unicodedata.normalize("NFD", plain(text))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def redundant(label, text):
    """Vrai si le texte repete deja le libelle du pictogramme (doublon a l'impression)."""
    return bool(label) and fold(text).startswith(fold(label))


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def symfont(text):
    """Bascule sur la police de symboles les caracteres absents de la police du texte."""
    return re.sub(TOK + "(.)" + TOK, '<font face="Sym">\\1</font>', text)


CODE_TOK = "\x02"


def emphasis(text):
    """Convertit ** et * en balises gras/italique TOUJOURS bien imbriquees.

    Le markdown redige a la main contient des paires mal imbriquees
    (``***gras**suite*``) ; une substitution par expression reguliere produirait
    des balises croisees que reportlab refuse. On analyse donc a la pile, en
    fermant proprement ce qui reste ouvert en fin de texte.
    """
    out, stack, i, n = [], [], 0, len(text)
    while i < n:
        if text.startswith("**", i):
            tag, size = "b", 2
        elif text[i] == "*":
            tag, size = "i", 1
        else:
            out.append(text[i])
            i += 1
            continue
        if tag in stack:
            while stack:
                open_tag = stack.pop()
                out.append("</%s>" % open_tag)
                if open_tag == tag:
                    break
        else:
            stack.append(tag)
            out.append("<%s>" % tag)
        i += size
    while stack:
        out.append("</%s>" % stack.pop())
    return "".join(out)


def inline(text):
    """Markdown en ligne -> mini-balisage reportlab.

    Les fragments de code sont mis de cote AVANT le traitement du gras et de
    l'italique : sans cela, un `**gras contenant du `code`**` verrait sa paire
    d'asterisques coupee en deux et laisserait des asterisques a l'impression.
    """
    text = clean(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    spans = []

    def stash(match):
        spans.append(match.group(1))
        return CODE_TOK + str(len(spans) - 1) + CODE_TOK

    text = re.sub(r"`([^`]+)`", stash, text)
    text = emphasis(symfont(esc(text)))

    def restore(match):
        return (
            '<font face="Mono" size="9.2" backColor="#EDEEF2">' + symfont(esc(spans[int(match.group(1))])) + "</font>"
        )

    return re.sub(CODE_TOK + r"(\d+)" + CODE_TOK, restore, text)


def picto_label(text):
    """Detache le pictogramme de tete. Renvoie (libelle ou None, texte restant).

    Le balisage d'emphase qui precede le pictogramme est reattache au texte
    restant, pour ne pas laisser d'asterisques orphelines.
    """
    match = re.match(r"^([\s*_#]*)(.*)$", text, re.S)
    prefix, rest = match.group(1), match.group(2)
    for ch, label in PICTO.items():
        if rest.startswith(ch):
            body = rest[len(ch) :]
            for drop in DROP:
                body = body.replace(drop, "")
            body = body.lstrip()
            emph = prefix.replace("#", "").strip()
            return label, (emph + body) if emph else body
    return None, text


STYLES = {
    "h1": ParagraphStyle(
        "h1",
        fontName="Body-B",
        fontSize=19,
        leading=23,
        spaceBefore=2,
        spaceAfter=11,
        textColor=colors.HexColor("#10233F"),
    ),
    "h2": ParagraphStyle(
        "h2",
        fontName="Body-B",
        fontSize=14.5,
        leading=18,
        spaceBefore=15,
        spaceAfter=6,
        textColor=colors.HexColor("#12365F"),
    ),
    "h3": ParagraphStyle(
        "h3",
        fontName="Body-B",
        fontSize=11.8,
        leading=15,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#1F4E79"),
    ),
    "p": ParagraphStyle("p", fontName="Body", fontSize=10, leading=14.2, spaceAfter=5, alignment=TA_LEFT),
    "li": ParagraphStyle("li", fontName="Body", fontSize=10, leading=14.2, leftIndent=13, bulletIndent=3, spaceAfter=3),
    "check": ParagraphStyle("check", fontName="Body", fontSize=10, leading=14.4, spaceAfter=0),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=9.5, leading=13.2, textColor=colors.white),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.2, leading=12.4),
    "cellh": ParagraphStyle("cellh", fontName="Body-B", fontSize=9.2, leading=12.4, textColor=colors.white),
    "boxlab": ParagraphStyle(
        "boxlab", fontName="Body-B", fontSize=8.6, leading=11, spaceAfter=3, textColor=colors.HexColor("#8A3B00")
    ),
    "sub": ParagraphStyle(
        "sub", fontName="Body-I", fontSize=9.5, leading=13, spaceAfter=6, textColor=colors.HexColor("#555555")
    ),
    "mark": ParagraphStyle("mark", fontName="Body-B", fontSize=10, leading=13, spaceAfter=0),
}

CONTENT_W = 168 * mm


TOC_STYLES = [
    ParagraphStyle(
        "toc0", fontName="Body-B", fontSize=10.4, leading=16, leftIndent=0, firstLineIndent=0, spaceBefore=3
    ),
    ParagraphStyle("toc1", fontName="Body", fontSize=10, leading=15, leftIndent=12, firstLineIndent=0),
]


def sommaire():
    """Sommaire a vrais numeros de page, rempli a la fabrication.

    Le document se suit sur papier : sans numeros, un renvoi « voir l'etape F »
    oblige a feuilleter. Ils ne peuvent pas etre ecrits a la main dans le
    Markdown, puisqu'ils dependent de la mise en page — d'ou le calcul en deux
    passes (voir build).
    """
    toc = TableOfContents()
    toc.levelStyles = TOC_STYLES
    toc.dotsMinLevel = 0
    return toc


def callout(flows, label=None):
    inner = []
    if label:
        inner.append(Paragraph(esc(label), STYLES["boxlab"]))
    inner.extend(flows)
    # UNE LIGNE PAR ELEMENT, et non un seul bloc. Un tableau ne se coupe qu'entre
    # ses lignes : avec une ligne unique, un encadre plus haut qu'une page faisait
    # echouer la fabrication du PDF, et il fallait a chaque fois raccourcir le
    # texte. Decoupe en lignes, l'encadre se poursuit page suivante tout seul.
    table = Table([[bloc] for bloc in inner], colWidths=[CONTENT_W], repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F4ED")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CAC3AF")),
                ("LINEBEFORE", (0, 0), (0, -1), 2.4, colors.HexColor("#B07A2B")),
                ("TOPPADDING", (0, 1), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def code_block(lines):
    inner = [Paragraph('<font face="Mono">' + symfont(esc(clean(ln))) + "</font>", STYLES["code"]) for ln in lines] or [
        Spacer(1, 1)
    ]
    table = Table([[inner]], colWidths=[CONTENT_W])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#16202E")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def make_table(rows):
    ncol = max(len(r) for r in rows)
    head = rows[0] + [""] * (ncol - len(rows[0]))
    data = [[Paragraph(inline(c), STYLES["cellh"]) for c in head]]
    for row in rows[1:]:
        row = row + [""] * (ncol - len(row))
        data.append([Paragraph(inline(c), STYLES["cell"]) for c in row])

    if ncol == 1:
        widths = [CONTENT_W]
    elif all(len(plain(r[0])) <= 7 for r in rows):
        widths = [15 * mm] + [(CONTENT_W - 15 * mm) / (ncol - 1)] * (ncol - 1)
    else:
        first = 44 * mm if ncol <= 3 else 32 * mm
        widths = [first] + [(CONTENT_W - first) / (ncol - 1)] * (ncol - 1)

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12365F")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F4F9")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B7C1CE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


TABLE_SEP = re.compile(r"^\s*\|?[\s:\-\|]+\|[\s:\-\|]*$")
BLOCK_START = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||```|-{3,}\s*$)")


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def render(lines, depth=0):
    out = []
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        line = raw.strip()

        if not line:
            i += 1
            continue

        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(code_block(buf))
            out.append(Spacer(1, 6))
            continue

        if line.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                quoted = lines[i].strip()[1:]
                buf.append(quoted[1:] if quoted.startswith(" ") else quoted)
                i += 1
            label = None
            if buf:
                label, rest = picto_label(buf[0])
                if label is not None:
                    buf[0] = rest
                    if redundant(label, rest):
                        label = None
            out.append(callout(render(buf, depth + 1), label))
            out.append(Spacer(1, 7))
            continue

        if line.startswith("|") and i + 1 < n and TABLE_SEP.match(lines[i + 1]):
            rows = [split_row(lines[i])]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(make_table(rows))
            out.append(Spacer(1, 8))
            continue

        if line == "[SOMMAIRE]":
            out.append(sommaire())
            out.append(Spacer(1, 8))
            i += 1
            continue

        head = re.match(r"^(#{1,6})\s+(.*)$", line)
        if head:
            level, text = len(head.group(1)), head.group(2)
            label, rest = picto_label(text)
            if label is not None:
                text = (label + " \u2014 " + rest) if rest else label
            key = "h3" if depth else ("h1" if level == 1 else "h2" if level == 2 else "h3")
            # Une etape = une page. C'est ce qui permet de ne pas perdre sa place
            # quand on leve les yeux de l'ecran pour taper une ligne, et de savoir
            # d'un coup d'oeil ou l'on en est.
            # Une partie = une page : etapes nommees (« Etape F ») comme chapitres
            # numerotes (« 6. Mettre son texte »). C'est ce qui permet de ne pas
            # perdre sa place en levant les yeux, et de retrouver un chapitre sans
            # feuilleter.
            etape = key == "h2" and (text[:5].lower() in ("étape", "etape") or re.match(r"^\d+\.\s", text) is not None)
            if etape and any(not isinstance(f, Spacer) for f in out):
                out.append(PageBreak())
            titre = Paragraph(inline(text), STYLES[key])
            if key in ("h1", "h2"):
                # Retenu pour le rappel en haut de page ET pour le sommaire
                # (voir Guide.afterFlowable).
                titre.section = re.sub(r"<[^>]+>", "", inline(text))
                if key == "h2":
                    titre.toclevel = 0
            out.append(titre)
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
            out.append(
                HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#C3CBD6"), spaceBefore=3, spaceAfter=7)
            )
            i += 1
            continue

        item = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", raw)
        if item:
            indent, text = len(item.group(1)), item.group(3)
            j = i + 1
            while (
                j < n
                and lines[j].strip()
                and not BLOCK_START.match(lines[j])
                and (len(lines[j]) - len(lines[j].lstrip())) > indent
            ):
                text += " " + lines[j].strip()
                j += 1
            i = j
            check = re.match(r"^\[([ xX])\]\s*(.*)$", text)
            if check:
                mark = "X" if check.group(1).lower() == "x" else " "
                width = CONTENT_W - (18 * mm if depth else 0)
                table = Table(
                    [
                        [
                            Paragraph("[%s]" % mark, STYLES["mark"]),
                            Paragraph(inline(check.group(2)), STYLES["check"]),
                        ]
                    ],
                    colWidths=[8 * mm, width - 8 * mm],
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                out.append(table)
            else:
                bullet = item.group(2) if item.group(2)[0].isdigit() else "\u2022"
                out.append(Paragraph(inline(text), STYLES["li"], bulletText=bullet))
            continue

        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not BLOCK_START.match(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        text = " ".join(buf)
        style = (
            STYLES["sub"]
            if (text.startswith("*") and text.endswith("*") and not text.startswith("**"))
            else STYLES["p"]
        )
        label, rest = picto_label(text)
        if label and redundant(label, rest):
            text = rest
        elif label:
            text = ("**" + label + "** \u2014 " + rest) if rest else "**" + label + "**"
        out.append(Paragraph(inline(text), style))
    return out


class Guide(BaseDocTemplate):
    """Document qui retient le titre de la section en cours.

    Sans ce rappel, un guide de vingt pages oblige a remonter pour savoir a
    quelle etape on se trouve — exactement ce qu'on ne peut pas faire quand on a
    les mains sur un clavier et les yeux sur un boitier.
    """

    def __init__(self, *a, **kw):
        BaseDocTemplate.__init__(self, *a, **kw)
        self.section = ""

    def afterFlowable(self, flowable):
        section = getattr(flowable, "section", None)
        if section:
            self.section = section
        niveau = getattr(flowable, "toclevel", None)
        if niveau is not None:
            self.notify("TOCEntry", (niveau, section or "", self.page))


def build(src, dst, footer):
    text = io.open(src, encoding="utf-8").read().replace("\r\n", "\n")
    story = render(text.split("\n"))

    doc = Guide(
        dst,
        pagesize=A4,
        leftMargin=21 * mm,
        rightMargin=21 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=footer,
        author="Le Prompteur",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def decorate(canv, _doc):
        canv.saveState()
        canv.setFont("Body", 7.6)
        canv.setFillColor(colors.HexColor("#8A93A0"))
        canv.drawString(doc.leftMargin, 10 * mm, footer)
        # Rappel de la section, en haut : on sait ou l'on est sans remonter.
        section = getattr(doc, "section", "")
        if section and canv.getPageNumber() > 1:
            canv.drawRightString(A4[0] - doc.rightMargin, A4[1] - 11 * mm, section[:70])
        canv.drawRightString(A4[0] - doc.rightMargin, 10 * mm, "page %d" % canv.getPageNumber())
        canv.setStrokeColor(colors.HexColor("#D6DBE2"))
        canv.setLineWidth(0.4)
        canv.line(doc.leftMargin, 13 * mm, A4[0] - doc.rightMargin, 13 * mm)
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPageEnd=decorate)])
    # Deux passes des qu'un sommaire est present : la premiere releve les
    # numeros de page, la seconde les ecrit. C'est le seul moyen d'avoir des
    # renvois justes, puisqu'ils dependent de la mise en page elle-meme.
    if any(isinstance(f, TableOfContents) for f in story):
        doc.multiBuild(story)
    else:
        doc.build(story)
    return dst


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
    print("OK ->", sys.argv[2], os.path.getsize(sys.argv[2]), "octets")
