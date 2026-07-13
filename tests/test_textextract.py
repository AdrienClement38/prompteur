# -*- coding: utf-8 -*-
"""Tests de l'extraction et du nettoyage de texte (docx, odt, rtf, doc, nettoyage)."""

import io
import sys
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
