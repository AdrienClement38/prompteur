# -*- coding: utf-8 -*-
"""Tests de l'extraction et du nettoyage de texte (docx, odt, rtf, doc, nettoyage).

La seconde moitié du fichier verrouille la REMONTÉE DE LA MISE EN FORME : les
plages produites doivent désigner EXACTEMENT les bons mots du texte nettoyé.
Toutes les assertions se font donc par découpage — texte[plage["start"]:plage["end"]]
comparé à la chaîne attendue — et jamais sur des indices écrits en dur.
"""

import io
import itertools
import random
import re
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import textextract as tx  # noqa: E402


def _docx(paragraphs):
    xml = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
    for para in paragraphs:
        xml += f"<w:p><w:r><w:t>{para}</w:t></w:r></w:p>"
    xml += "</w:body></w:document>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_clean_text_normalise():
    dirty = "Bonjour   le  monde​ !\n\n\n\nDeux\tparagraphe\r\nfin  "
    out = tx.clean_text(dirty)
    assert "  " not in out  # plus d'espaces doubles
    assert "​" not in out  # caractère zéro-largeur supprimé
    assert "\n\n\n" not in out  # lignes vides multiples fusionnées
    assert out.startswith("Bonjour le monde !")
    assert not out.endswith(" ")  # espaces de bord retirés


def test_clean_text_vide():
    assert tx.clean_text("") == ""
    assert tx.clean_text(None) == ""


def test_extract_docx():
    data = _docx(["Titre du sujet", "Ligne un &amp; suite.", "Paragraphe deux"])
    assert tx.extract_text("x.docx", data) == "Titre du sujet\nLigne un & suite.\nParagraphe deux"


def test_extract_docx_titres_et_sauts_de_ligne():
    # titre (Title), sous-titre (Heading2), corps avec gras à retirer et saut de ligne à garder
    xml = (
        '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>Le Journal</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Politique</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>Debut </w:t></w:r>"
        "<w:r><w:rPr><w:b/></w:rPr><w:t>en gras</w:t></w:r>"
        "<w:r><w:t>.</w:t></w:r><w:br/><w:r><w:t>Ligne deux.</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    out = tx.extract_text("j.docx", buf.getvalue())
    assert out == "# Le Journal\n## Politique\nDebut en gras.\nLigne deux."


def test_extract_odt():
    xml = '<?xml version="1.0"?><o xmlns:text="x"><text:p>Bonjour</text:p><text:p>Ligne deux</text:p></o>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("content.xml", xml)
    assert tx.extract_text("x.odt", buf.getvalue()) == "Bonjour\nLigne deux"


def test_extract_rtf():
    rtf = r"{\rtf1\ansi Bonjour \b gras\b0 .\par Fin.}"
    out = tx.extract_text("x.rtf", rtf.encode("latin-1"))
    assert "Bonjour" in out
    assert "Fin." in out
    assert "\\" not in out  # commandes RTF retirées


def test_extract_txt_est_nettoye():
    assert tx.extract_text("note.txt", "A   B\n\n\n\nC".encode("utf-8")) == "A B\n\nC"


def test_doc_sans_antiword_message_clair():
    # Sans antiword (ou avec un contenu invalide), on lève une ValueError lisible.
    with pytest.raises(ValueError):
        tx.extract_text("vieux.doc", b"\xd0\xcf\x11\xe0 pas un vrai .doc")


# ============================================================================
# Mise en forme importée : construction de vrais .docx / .odt en mémoire
# ============================================================================
def _zip(entrees):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nom, contenu in entrees.items():
            z.writestr(nom, contenu)
    return buf.getvalue()


def _run(texte, props=""):
    """Un <w:r> de .docx ; props est le contenu brut du <w:rPr>."""
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{texte}</w:t></w:r>'


def _docx_riche(paragraphes):
    """paragraphes : liste de (style_de_paragraphe ou None, contenu XML du paragraphe)."""
    xml = '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
    for style, contenu in paragraphes:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        xml += f"<w:p>{ppr}{contenu}</w:p>"
    xml += "</w:body></w:document>"
    return _zip({"word/document.xml": xml})


def _style_odt(nom, props, parent=None):
    herite = f' style:parent-style-name="{parent}"' if parent else ""
    return f'<style:style style:name="{nom}" style:family="text"{herite}><style:text-properties {props}/></style:style>'


def _odt_riche(styles, corps):
    xml = (
        '<?xml version="1.0"?><office:document-content xmlns:office="o" xmlns:text="t" '
        'xmlns:style="s" xmlns:fo="f">'
        f"<office:automatic-styles>{''.join(styles)}</office:automatic-styles>"
        f"<office:body><office:text>{corps}</office:text></office:body>"
        "</office:document-content>"
    )
    return _zip({"content.xml": xml})


def _seule(plages):
    """Une et une seule plage attendue : on renvoie la plage."""
    assert len(plages) == 1, plages
    return plages[0]


# ----------------------------------------------------------------------------
# Le test central : les indices sont-ils bien recalés sur le texte NETTOYÉ ?
# ----------------------------------------------------------------------------
def test_docx_indices_recales_apres_espaces_et_ligne_vide():
    # Tout ce qui raccourcit le texte au nettoyage est placé AVANT le passage
    # en gras : espaces multiples, tabulation, espace insécable, caractère
    # zéro-largeur, espaces de fin de ligne, puis un paragraphe vide.
    sale = "Un   texte\tavec  des\u00a0espaces\u200b   "
    data = _docx_riche(
        [
            (None, _run(sale)),
            (None, ""),  # paragraphe vide : une ligne qui disparaît au nettoyage
            (None, _run("voici le ") + _run("passage en gras", "<w:b/>")),
        ]
    )
    texte, plages = tx.extract_rich("m.docx", data)

    assert texte == "Un texte avec des espaces\n\nvoici le passage en gras"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "passage en gras"
    assert plage["start"] == texte.index("passage en gras")
    assert plage == {"start": texte.index("passage en gras"), "end": len(texte), "b": True}

    # Preuve chiffrée que le recalage a eu lieu : l'indice dans le texte BRUT
    # (avant nettoyage) est strictement plus grand, ce n'est donc pas une coïncidence.
    brut = "".join(t for t, _ in tx._docx_segments(data))
    assert plage["start"] < brut.index("passage en gras")


# ----------------------------------------------------------------------------
# Aucune régression : sans style, tout doit être identique à avant
# ----------------------------------------------------------------------------
def _clean_reference(s):
    """Copie FIGÉE de l'algorithme de nettoyage d'origine, avant instrumentation.

    Elle sert d'étalon : _clean_indexed() doit lui être identique au caractère près.
    Ne pas la « corriger » — c'est justement sa fixité qui a de la valeur.
    """
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
            if cat in ("Zl", "Zp"):
                out.append("\n")
            elif cat == "Zs":
                out.append(" ")
            elif cat[0] == "C":
                continue
            else:
                out.append(ch)
    lignes = [re.sub(r" {2,}", " ", ln).strip() for ln in "".join(out).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()


ENTREES_MECHANTES = [
    "",
    "   ",
    "\n\n\n\n\n",
    "\u200b\u200b\u200b",
    "texte normal",
    "Bonjour   le  monde\u200b !\n\n\n\nDeux\tparagraphe\r\nfin  ",
    "a\r\nb\rc\nd\r\r\n\re",
    "  bord  \n  bord  \n",
    "a\u2028b\u2029c",
    "cafe\u0301 et crème brûlée",  # accent combinant : la NFC raccourcit
    "\ufeffBOM au début et é\u0301trange",
    "nbsp\u00a0ici, cadratin\u2003là, fin\u2007espace",
    "un\ttab\t\tdeux",
    "\n a \n\n b \n\n\n c \n",
    "ligne\n\nligne",
    "mot " * 50,
    "\r\n\r\n\r\n",
    "déjà composé \u1100\u1161\u11a8 hangul",  # jamos : composition starter+starter
]


@pytest.mark.parametrize("entree", ENTREES_MECHANTES)
def test_clean_text_identique_a_la_reference(entree):
    assert tx.clean_text(entree) == _clean_reference(entree)


@pytest.mark.parametrize("entree", ENTREES_MECHANTES)
def test_origines_coherentes(entree):
    texte, origines = tx._clean_indexed(entree)
    assert len(origines) == len(texte)
    assert all(origines[i] <= origines[i + 1] for i in range(len(origines) - 1))
    assert all(0 <= o < len(entree) for o in origines)


def test_docx_sans_style_texte_identique():
    # Même entrée que tests/test_server.py::test_upload_docx_extrait_et_nettoie
    texte, plages = tx.extract_rich("note.docx", _docx(["Titre", "Corps du   texte."]))
    assert texte == "Titre\nCorps du texte."
    assert plages == []


def test_extract_text_delegue_a_extract_rich():
    data = _docx_riche([(None, _run("normal ") + _run("gras", "<w:b/>"))])
    assert tx.extract_text("d.docx", data) == tx.extract_rich("d.docx", data)[0]


def test_txt_et_rtf_sans_plages():
    assert tx.extract_rich("note.txt", "A   B\n\n\n\nC".encode("utf-8")) == ("A B\n\nC", [])
    rtf = r"{\rtf1\ansi Bonjour \b gras\b0 .\par Fin.}"
    assert tx.extract_rich("x.rtf", rtf.encode("latin-1"))[1] == []


def test_document_trop_gros_toujours_refuse():
    with pytest.raises(tx.TextTooLarge):
        tx.extract_rich("gros.txt", ("a" * (tx.MAX_TEXT_CHARS + 1)).encode("utf-8"))
    with pytest.raises(tx.TextTooLarge):
        tx.extract_rich("long.txt", ("x\n" * (tx.MAX_TEXT_LINES + 1)).encode("utf-8"))


# ----------------------------------------------------------------------------
# .docx : styles, cumuls, fusions, bords
# ----------------------------------------------------------------------------
def test_docx_gras_italique_souligne_cumules():
    data = _docx_riche(
        [
            (
                None,
                _run("avant ") + _run("tout a la fois", "<w:b/><w:i/><w:u w:val='single'/>") + _run(" apres"),
            )
        ]
    )
    texte, plages = tx.extract_rich("c.docx", data)
    assert texte == "avant tout a la fois apres"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "tout a la fois"
    assert plage == {"start": 6, "end": 20, "b": True, "i": True, "u": True}


def test_docx_style_desactive_val_zero():
    data = _docx_riche([(None, _run("pas gras", '<w:b w:val="0"/><w:u w:val="none"/>'))])
    texte, plages = tx.extract_rich("z.docx", data)
    assert texte == "pas gras"
    assert plages == []


def test_docx_bcs_ics_ignores():
    # <w:bCs> est le gras des « scripts complexes » : il ne doit pas être pris pour <w:b>
    data = _docx_riche([(None, _run("arabe", "<w:bCs/><w:iCs/>"))])
    assert tx.extract_rich("bcs.docx", data)[1] == []


def test_docx_runs_consecutifs_fusionnes():
    # Word découpe volontiers une phrase en gras en plusieurs runs : une seule plage attendue.
    data = _docx_riche(
        [
            (
                None,
                _run("gra", "<w:b/>") + _run("s et", "<w:b/>") + _run(" suite", "<w:b/>"),
            )
        ]
    )
    texte, plages = tx.extract_rich("f.docx", data)
    assert texte == "gras et suite"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "gras et suite"


def test_docx_run_gras_uniquement_espaces_ignore():
    data = _docx_riche([(None, _run("mot") + _run("   ", "<w:b/>") + _run("suite"))])
    texte, plages = tx.extract_rich("e.docx", data)
    assert texte == "mot suite"
    assert plages == []  # jamais de plage vide, que sanitize_marks écarterait


def test_docx_gras_avec_espace_final():
    data = _docx_riche([(None, _run("mot ") + _run("gras ", "<w:b/>") + _run("fin"))])
    texte, plages = tx.extract_rich("g.docx", data)
    assert texte == "mot gras fin"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "gras"  # l'espace n'est pas mis en forme


def test_docx_titre_diese_ne_decale_pas():
    # Les dièses ajoutés devant les titres allongent le texte : les plages qui
    # suivent doivent en tenir compte.
    data = _docx_riche(
        [
            ("Heading1", _run("Mon titre")),
            (None, _run("un ") + _run("mot", "<w:b/>") + _run(" apres")),
        ]
    )
    texte, plages = tx.extract_rich("t.docx", data)
    assert texte == "# Mon titre\nun mot apres"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "mot"
    assert plage["start"] == texte.index("mot")


def test_docx_titre_entierement_en_gras():
    # Un titre dont le texte est en gras : la plage ne doit pas déborder sur les dièses.
    data = _docx_riche([("Heading2", _run("Titre gras", "<w:b/>"))])
    texte, plages = tx.extract_rich("tg.docx", data)
    assert texte == "## Titre gras"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "Titre gras"


def test_docx_saut_de_ligne_dans_un_run_gras():
    data = _docx_riche([(None, _run("ligne un<w:br/>ligne deux", "<w:b/>"))])
    texte, plages = tx.extract_rich("br.docx", data)
    assert texte == "ligne un\nligne deux"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "ligne un\nligne deux"


def test_docx_nfd_avant_le_gras():
    # « cafe » + accent combinant : la NFC raccourcit le texte d'un caractère
    # AVANT le passage en gras. Sans la table d'origines, la plage glisserait.
    data = _docx_riche([(None, _run("cafe\u0301 tie\u0300de ") + _run("gras", "<w:b/>"))])
    texte, plages = tx.extract_rich("n.docx", data)
    assert texte == "café tiède gras"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "gras"
    assert plage["start"] == texte.index("gras")


def test_docx_plusieurs_plages_distinctes():
    data = _docx_riche(
        [
            (None, _run("le ") + _run("gras", "<w:b/>") + _run(" puis ") + _run("l'italique", "<w:i/>")),
        ]
    )
    texte, plages = tx.extract_rich("p.docx", data)
    assert texte == "le gras puis l'italique"
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "gras"
    assert texte[plages[1]["start"] : plages[1]["end"]] == "l'italique"
    assert plages[0]["b"] is True and "i" not in plages[0]
    assert plages[1]["i"] is True and "b" not in plages[1]


def test_docx_entite_dans_un_run_gras():
    data = _docx_riche([(None, _run("Paul ") + _run("&amp; Marie", "<w:b/>") + _run(" arrivent"))])
    texte, plages = tx.extract_rich("amp.docx", data)
    assert texte == "Paul & Marie arrivent"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "& Marie"


# ----------------------------------------------------------------------------
# .odt
# ----------------------------------------------------------------------------
def test_odt_gras_et_italique_bons_mots():
    data = _odt_riche(
        [
            _style_odt("T1", 'fo:font-weight="bold"'),
            _style_odt("T2", 'fo:font-style="italic"'),
        ],
        '<text:p>Le <text:span text:style-name="T1">gras</text:span> et '
        '<text:span text:style-name="T2">l\'italique</text:span> ici.</text:p>',
    )
    texte, plages = tx.extract_rich("o.odt", data)
    assert texte == "Le gras et l'italique ici."
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "gras"
    assert texte[plages[1]["start"] : plages[1]["end"]] == "l'italique"
    assert plages[0] == {"start": 3, "end": 7, "b": True}


def test_odt_spans_imbriques():
    data = _odt_riche(
        [
            _style_odt("T1", 'fo:font-weight="bold"'),
            _style_odt("T2", 'fo:font-style="italic"'),
        ],
        '<text:p>Debut <text:span text:style-name="T1">gras '
        '<text:span text:style-name="T2">et italique</text:span></text:span> fin.</text:p>',
    )
    texte, plages = tx.extract_rich("i.odt", data)
    assert texte == "Debut gras et italique fin."
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "gras"
    assert plages[0]["b"] is True and "i" not in plages[0]
    assert texte[plages[1]["start"] : plages[1]["end"]] == "et italique"
    assert plages[1]["b"] is True and plages[1]["i"] is True


def test_odt_style_herite_du_parent():
    data = _odt_riche(
        [
            _style_odt("Base", 'fo:font-weight="bold"'),
            _style_odt("T3", 'style:text-underline-style="solid"', parent="Base"),
        ],
        '<text:p>un <text:span text:style-name="T3">mot</text:span> la</text:p>',
    )
    texte, plages = tx.extract_rich("h.odt", data)
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "mot"
    assert plage == {"start": 3, "end": 6, "b": True, "u": True}


def test_odt_souligne_none_ignore():
    data = _odt_riche(
        [_style_odt("T4", 'style:text-underline-style="none" fo:font-weight="normal"')],
        '<text:p>rien <text:span text:style-name="T4">de special</text:span></text:p>',
    )
    assert tx.extract_rich("s.odt", data)[1] == []


def test_odt_espaces_multiples_et_ligne_vide():
    data = _odt_riche(
        [_style_odt("T1", 'fo:font-weight="bold"')],
        "<text:p>Un   texte\tavec  des\u00a0espaces\u200b   </text:p>"
        "<text:p></text:p>"
        '<text:p>voici le <text:span text:style-name="T1">passage en gras</text:span></text:p>',
    )
    texte, plages = tx.extract_rich("r.odt", data)
    assert texte == "Un texte avec des espaces\n\nvoici le passage en gras"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "passage en gras"
    brut = "".join(t for t, _ in tx._odt_segments(data))
    assert plage["start"] < brut.index("passage en gras")


def test_odt_titre_et_gras():
    data = _odt_riche(
        [_style_odt("T1", 'fo:font-weight="bold"')],
        '<text:h text:outline-level="2">Chapitre</text:h>'
        '<text:p>corps <text:span text:style-name="T1">en gras</text:span></text:p>',
    )
    texte, plages = tx.extract_rich("th.odt", data)
    assert texte == "## Chapitre\ncorps en gras"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "en gras"


# ----------------------------------------------------------------------------
# Contrat avec le validateur du serveur
# ----------------------------------------------------------------------------
def test_plages_acceptees_telles_quelles_par_sanitize_marks():
    """Les plages produites doivent traverser sanitize_marks() SANS être modifiées.

    C'est le contrat réel : une plage mal formée serait écartée en silence et la
    mise en forme disparaîtrait sans que personne ne sache pourquoi.
    """
    server = pytest.importorskip("server")
    data = _docx_riche(
        [
            ("Heading1", _run("Le titre", "<w:b/>")),
            (
                None,
                _run("du ")
                + _run("gras", "<w:b/>")
                + _run(", de ")
                + _run("l'italique", "<w:i/>")
                + _run(" et du ")
                + _run("souligne", '<w:u w:val="single"/>'),
            ),
        ]
    )
    texte, plages = tx.extract_rich("v.docx", data)
    assert len(plages) == 4
    assert server.sanitize_marks(plages, len(texte)) == plages


def test_pas_plus_de_plages_que_le_serveur_n_en_garde():
    mots = "".join(_run(f"m{i} ", "<w:b/>" if i % 2 else "") for i in range(4 * tx.MAX_MARKS))
    texte, plages = tx.extract_rich("beaucoup.docx", _docx_riche([(None, mots)]))
    assert len(plages) <= tx.MAX_MARKS
    for plage in plages:
        assert texte[plage["start"] : plage["end"]].strip() == texte[plage["start"] : plage["end"]]


# --------------------------------------------------------------------------
# Découpage en blocs : équivalence avec les anciens motifs, et coût linéaire
# --------------------------------------------------------------------------
# _blocs() a remplacé des motifs du genre « <w:r\b(?:[^>]*/>|[^>]*>.*?</w:r>) ».
# Ces motifs étaient corrects mais QUADRATIQUES quand la balise n'est jamais
# refermée : 40 000 « <w:r> » sans fermeture, dans un .docx de 500 octets,
# coûtaient 103 secondes — et MAX_ZIP_ENTRY n'y pouvait rien, le fichier étant
# minuscule. Les deux tests ci-dessous verrouillent les deux moitiés du contrat :
# mêmes blocs qu'avant, et coût désormais linéaire.
_ANCIENS_MOTIFS = [
    (re.compile(r"<w:p\b(?:[^>]*/>|[^>]*>.*?</w:p>)", re.S), tx._OUVRE_PARA_DOCX, "</w:p>", True),
    (re.compile(r"<w:r\b(?:[^>]*/>|[^>]*>.*?</w:r>)", re.S), tx._OUVRE_RUN_DOCX, "</w:r>", True),
    (
        re.compile(r"<style:style\b(?:[^>]*/>|[^>]*>.*?</style:style>)", re.S),
        tx._OUVRE_STYLE_ODT,
        "</style:style>",
        True,
    ),
]
_JETONS_ABIMES = [
    "<w:p>",
    "</w:p>",
    "<w:p/>",
    "<w:pPr>",
    "<w:p",
    '<w:p a="/>',
    "<w:r>",
    "</w:r>",
    "<w:r/>",
    "<w:rPr>",
    "<style:style>",
    "</style:style>",
    "<style:style/>",
    "<text:p>",
    "</text:p>",
    "<text:h>",
    "</text:h>",
    "<text:p/>",
    "x",
    ">",
    "<",
    "/>",
]


def test_blocs_identiques_aux_anciens_motifs():
    """Sur du XML ABÎMÉ, _blocs() rend exactement les blocs des anciens motifs."""
    chaines = ["".join(c) for n in (1, 2, 3) for c in itertools.product(_JETONS_ABIMES, repeat=n)]
    assert len(chaines) > 10000  # le jeu de cas doit rester massif
    for chaine in chaines:
        for motif, ouvre, ferme, auto in _ANCIENS_MOTIFS:
            attendu = [(m.start(), m.end()) for m in motif.finditer(chaine)]
            obtenu = [(a, b) for a, b, _m in tx._blocs(chaine, ouvre, ferme, auto)]
            assert obtenu == attendu, f"bloc {ferme} sur {chaine!r}"


def test_blocs_paragraphes_odt_identiques_a_l_ancien_motif():
    """Même vérification pour <text:p>/<text:h>, dont les groupes portent le contenu."""
    ancien = re.compile(r"<text:(p|h)\b([^>]*)>(.*?)</text:\1>", re.S)
    chaines = ["".join(c) for n in (1, 2, 3) for c in itertools.product(_JETONS_ABIMES, repeat=n)]
    for chaine in chaines:
        attendu = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3)) for m in ancien.finditer(chaine)]
        obtenu = []
        for debut, fin, m in tx._blocs(chaine, tx._OUVRE_PARA_ODT, tx._FERME_PARA_ODT, False):
            tag = m.group(1)
            tete = chaine.find(">", m.end())
            obtenu.append((debut, fin, tag, chaine[m.end() : tete], chaine[tete + 1 : fin - len(f"</text:{tag}>")]))
        assert obtenu == attendu, f"paragraphe ODT sur {chaine!r}"


@pytest.mark.parametrize("balise", ["w:r", "w:p"])
def test_balises_docx_non_fermees_restent_rapides(balise):
    """Un fichier d'un demi-kilo-octet ne doit pas occuper le boîtier des minutes."""
    corps = "<w:p>" + f"<{balise}>" * 20000 + "texte</w:p>"
    data = _zip(
        {"word/document.xml": f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{corps}</w:body></w:document>'}
    )
    # Le document reste minuscule (et tombe sous le kilo-octet une fois compressé) :
    # aucun plafond de taille ne peut donc protéger du coût de son analyse.
    assert len(data) < 200_000
    depart = time.perf_counter()
    tx.extract_text("abime.docx", data)
    duree = time.perf_counter() - depart
    assert duree < 5.0, f"<{balise}> : {duree:.1f} s — le coût quadratique est revenu"


def test_balises_odt_non_fermees_restent_rapides():
    """Même garde côté ODT : styles et paragraphes jamais refermés."""
    corps = "<text:p>" * 15000 + "texte"
    styles = '<style:style style:family="text">' * 15000
    data = _zip(
        {
            "content.xml": '<?xml version="1.0"?><office:document-content xmlns:office="o" xmlns:text="t" '
            f'xmlns:style="s" xmlns:fo="f"><office:automatic-styles>{styles}</office:automatic-styles>'
            f"<office:body><office:text>{corps}</office:text></office:body></office:document-content>",
        }
    )
    depart = time.perf_counter()
    tx.extract_text("abime.odt", data)
    duree = time.perf_counter() - depart
    assert duree < 5.0, f"{duree:.1f} s — le coût quadratique est revenu"


# ----------------------------------------------------------------------------
# .odt : un style qui DÉSACTIVE explicitement la mise en forme héritée
#
# Dans un .odt la mise en forme des caractères se CUMULE (span dans span, style
# et style parent). Dégrasser un mot au milieu d'une phrase en gras n'enlève rien
# au span extérieur : LibreOffice imbrique un span fo:font-weight="normal".
# Ces quatre tests verrouillent le fait qu'une annulation est bien vue — sinon la
# mise en forme s'applique aux mauvais mots, ce qui est pire que pas de gras.
# ----------------------------------------------------------------------------
def test_odt_span_imbrique_qui_annule_le_gras():
    data = _odt_riche(
        [
            _style_odt("Gras", 'fo:font-weight="bold"'),
            _style_odt("PasGras", 'fo:font-weight="normal"'),
        ],
        '<text:p>Debut <text:span text:style-name="Gras">phrase en gras avec '
        '<text:span text:style-name="PasGras">un mot normal</text:span> dedans'
        "</text:span> fin.</text:p>",
    )
    texte, plages = tx.extract_rich("degras.odt", data)
    assert texte == "Debut phrase en gras avec un mot normal dedans fin."
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "phrase en gras avec"
    assert texte[plages[1]["start"] : plages[1]["end"]] == "dedans"
    assert all(plage.get("b") is True for plage in plages)
    # Le cœur du test : le mot dégrassé n'est couvert par AUCUNE plage.
    debut, fin = texte.index("un mot normal"), texte.index("un mot normal") + len("un mot normal")
    assert all(plage["end"] <= debut or plage["start"] >= fin for plage in plages)


def test_odt_style_enfant_annule_le_gras_du_parent():
    data = _odt_riche(
        [
            _style_odt("Base", 'fo:font-weight="bold" fo:font-style="italic"'),
            _style_odt("Enfant", 'fo:font-weight="normal"', parent="Base"),
        ],
        '<text:p>a <text:span text:style-name="Enfant">plus gras</text:span> b</text:p>',
    )
    texte, plages = tx.extract_rich("annule.odt", data)
    assert texte == "a plus gras b"
    plage = _seule(plages)
    assert texte[plage["start"] : plage["end"]] == "plus gras"
    # L'italique hérité reste, le gras est annulé : un seul des deux survit.
    assert plage == {"start": 2, "end": 11, "i": True}


def test_odt_italique_et_souligne_annules_dans_un_span():
    data = _odt_riche(
        [
            _style_odt("IU", 'fo:font-style="italic" style:text-underline-style="solid"'),
            _style_odt("Rien", 'fo:font-style="normal" style:text-underline-style="none"'),
        ],
        '<text:p>x <text:span text:style-name="IU">penche '
        '<text:span text:style-name="Rien">droit</text:span> encore</text:span> y</text:p>',
    )
    texte, plages = tx.extract_rich("iu.odt", data)
    assert texte == "x penche droit encore y"
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "penche"
    assert texte[plages[1]["start"] : plages[1]["end"]] == "encore"
    assert all(plage.get("i") is True and plage.get("u") is True for plage in plages)
    debut, fin = texte.index("droit"), texte.index("droit") + len("droit")
    assert all(plage["end"] <= debut or plage["start"] >= fin for plage in plages)


def test_odt_span_muet_herite_toujours():
    """Garde-fou du correctif : « non précisé » ne doit PAS devenir « désactivé ».

    Un span qui ne parle que du souligné doit continuer à hériter du gras.
    """
    data = _odt_riche(
        [
            _style_odt("G", 'fo:font-weight="bold"'),
            _style_odt("S", 'style:text-underline-style="solid"'),
        ],
        '<text:p><text:span text:style-name="G">tout gras '
        '<text:span text:style-name="S">et souligne</text:span></text:span></text:p>',
    )
    texte, plages = tx.extract_rich("muet.odt", data)
    assert texte == "tout gras et souligne"
    assert len(plages) == 2
    assert texte[plages[0]["start"] : plages[0]["end"]] == "tout gras"
    assert plages[0] == {"start": 0, "end": 9, "b": True}
    assert texte[plages[1]["start"] : plages[1]["end"]] == "et souligne"
    assert plages[1] == {"start": 10, "end": 21, "b": True, "u": True}


# ----------------------------------------------------------------------------
# Garde-fou permanent : chaque caractère porte sa mise en forme dans son dessin
#
# Une classe de caractères par combinaison de styles. Le contrôle ne compare donc
# AUCUN indice écrit en dur : il vérifie que la mise en forme posée sur chaque
# caractère du texte final est bien celle que sa classe impose. Un décalage d'un
# seul caractère fait tomber le test, quelle que soit la forme du document.
# ----------------------------------------------------------------------------
CLASSES_STYLES = {
    frozenset(): "abcd",
    frozenset({"b"}): "ABCD",
    frozenset({"i"}): "efgh",
    frozenset({"u"}): "EFGH",
    frozenset({"b", "i"}): "mnop",
    frozenset({"b", "u"}): "MNOP",
    frozenset({"i", "u"}): "wxyz",
    frozenset({"b", "i", "u"}): "WXYZ",
}
CARACTERE_VERS_STYLES = {car: styles for styles, cars in CLASSES_STYLES.items() for car in cars}
# Tout ce qui change les longueurs au nettoyage : espaces multiples, tabulation,
# insécable, zéro-largeur, BOM, séparateur de ligne, accent combinant, lignes vides.
BLANCS_PIEGES = [
    " ",
    "  ",
    "   ",
    "\t",
    "\n",
    "\n\n\n",
    "\u00a0",
    "\u200b",
    "\ufeff",
    "\u2003",
    "\u2028",
    "",
    "\u0301",
    "\u0308",
]


def _suite_aleatoire(tirage, nombre, un_caractere_par_run):
    """Renvoie [(texte, styles)] : le texte d'un morceau ne pioche QUE dans sa classe."""
    morceaux = []
    for _ in range(nombre):
        styles = tirage.choice(list(CLASSES_STYLES))
        if un_caractere_par_run:
            texte = tirage.choice(BLANCS_PIEGES if tirage.random() < 0.5 else CLASSES_STYLES[styles])
        else:
            texte = "".join(
                tirage.choice(BLANCS_PIEGES) if tirage.random() < 0.4 else tirage.choice(CLASSES_STYLES[styles])
                for _ in range(tirage.randint(0, 6))
            )
        morceaux.append((texte, styles))
    return morceaux


def _docx_par_classes(tirage, un_par_run):
    paragraphes = []
    for _ in range(tirage.randint(1, 3)):
        contenu = ""
        for texte, styles in _suite_aleatoire(tirage, tirage.randint(0, 8), un_par_run):
            props = "".join({"b": "<w:b/>", "i": "<w:i/>", "u": '<w:u w:val="single"/>'}[cle] for cle in sorted(styles))
            contenu += _run(texte, props)
        style_p = tirage.choice([None, None, None, "Heading1", "Title"])
        paragraphes.append((style_p, contenu))
    return _docx_riche(paragraphes)


def _odt_par_classes(tirage, un_par_run):
    noms, styles_odt = {}, []
    for rang, styles in enumerate(CLASSES_STYLES):
        if not styles:
            continue
        props = []
        if "b" in styles:
            props.append('fo:font-weight="bold"')
        if "i" in styles:
            props.append('fo:font-style="italic"')
        if "u" in styles:
            props.append('style:text-underline-style="solid"')
        noms[styles] = f"C{rang}"
        styles_odt.append(_style_odt(f"C{rang}", " ".join(props)))
    corps = ""
    for _ in range(tirage.randint(1, 3)):
        interieur = ""
        for texte, styles in _suite_aleatoire(tirage, tirage.randint(0, 8), un_par_run):
            if styles:
                interieur += f'<text:span text:style-name="{noms[styles]}">{texte}</text:span>'
            else:
                interieur += texte
        corps += f"<text:p>{interieur}</text:p>"
    return _odt_riche(styles_odt, corps)


def _controle_par_classes(texte, plages, description):
    obtenu = [set() for _ in texte]
    for plage in plages:
        for indice in range(plage["start"], plage["end"]):
            obtenu[indice].update(cle for cle in ("b", "i", "u") if plage.get(cle))
    for indice, car in enumerate(texte):
        # La base NFD retrouve la classe même après composition (« É » -> « E »).
        attendu = CARACTERE_VERS_STYLES.get(unicodedata.normalize("NFD", car)[0])
        if attendu is None:
            continue  # blanc ou invisible : il n'appartient à aucune classe
        assert set(attendu) == obtenu[indice], (
            f"{description} : le caractère {car!r} (indice {indice}) porte "
            f"{sorted(obtenu[indice])} au lieu de {sorted(attendu)}.\n"
            f"texte  = {texte!r}\nplages = {plages}"
        )


@pytest.mark.parametrize("un_par_run", [False, True])
def test_les_plages_designent_toujours_les_caracteres_de_leur_classe(un_par_run):
    """200 documents piégés par format : aucune plage ne doit glisser d'un cran.

    « un caractère par run » est le pire cas : chaque frontière de style tombe
    entre deux caractères, là où le nettoyage fusionne espaces et lignes vides.
    """
    for graine in range(200):
        tirage = random.Random((graine, un_par_run, "docx").__hash__())
        data = _docx_par_classes(tirage, un_par_run)
        texte, plages = tx.extract_rich("classes.docx", data)
        _controle_par_classes(texte, plages, f"docx graine={graine} un_par_run={un_par_run}")

        tirage = random.Random((graine, un_par_run, "odt").__hash__())
        data = _odt_par_classes(tirage, un_par_run)
        texte, plages = tx.extract_rich("classes.odt", data)
        _controle_par_classes(texte, plages, f"odt graine={graine} un_par_run={un_par_run}")
