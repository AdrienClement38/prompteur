"""install/petit-ecran.sh : le petit écran de 3,5 pouces sur les broches.

Le script modifie le fichier de démarrage du Raspberry : on vérifie, sur une
copie, qu'il n'ajoute que ses lignes, qu'il ne les double pas, qu'il garde les
choix précédents, qu'il s'arrête devant un pilote de vendeur, et qu'« annuler »
rend le fichier d'origine à l'identique. La séquence d'allumage produite est
comparée octet par octet à celle du fabricant.
"""

import os
import shutil
import subprocess  # nosec B404 - script du dépôt, arguments fixes
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "install" / "petit-ecran.sh"

# st7796s.bin du fabricant (page « 3.5inch RPi LCD (G) », méthode Bookworm), en
# hexadécimal : c'est la référence que la séquence du dépôt doit reproduire.
FIRMWARE_FABRICANT = bytes.fromhex(
    "4d49504920444249000000000000000101000001963601483a0105f001c3f001"
    "96b40101b701c6c0028045c10113c201a7c5010ae808408a00002919a533e00e"
    "d0080f0606333033471713132b31e10ed00a110b09072f33473815162c32f001"
    "3cf001692100110000016429000001641300000114"
)

ORIGINE = "# config\ndtoverlay=vc4-kms-v3d\nmax_framebuffers=2\n\n[cm5]\ndtoverlay=dwc2,dr_mode=host\n"


def _bash():
    chemin = shutil.which("bash")
    # Sous Windows, le « bash » de System32 est celui de WSL : autre système de fichiers.
    if not chemin or "system32" in chemin.lower():
        return None
    return chemin


pytestmark = pytest.mark.skipif(_bash() is None, reason="bash introuvable")


@pytest.fixture
def boot(tmp_path):
    config = tmp_path / "config.txt"
    config.write_text(ORIGINE, encoding="utf-8")
    maison = tmp_path / "maison"
    maison.mkdir()
    # python3 = l'interpréteur des tests (sous Windows, « python3 » n'est souvent
    # qu'un raccourci vers le Store).
    outils = tmp_path / "outils"
    outils.mkdir()
    cale = outils / "python3"
    cale.write_text('#!/bin/sh\nexec "%s" "$@"\n' % Path(sys.executable).as_posix(), encoding="utf-8")
    cale.chmod(0o755)
    env = dict(os.environ)
    env.update(
        PROMPTEUR_ESSAI="1",
        PROMPTEUR_BOOT_CONFIG=config.as_posix(),
        PROMPTEUR_FIRMWARE=(tmp_path / "st7796s.bin").as_posix(),
        HOME=maison.as_posix(),
        SUDO_USER="",
        PATH=outils.as_posix() + os.pathsep + env.get("PATH", ""),
    )

    def lancer(*args):
        return subprocess.run(  # nosec B603 - script du dépôt, arguments fixes
            [_bash(), SCRIPT.as_posix(), *args], env=env, capture_output=True, text=True, timeout=60
        )

    return {"config": config, "maison": maison, "tmp": tmp_path, "lancer": lancer}


def _bloc(texte):
    debut = texte.index("# >>> Prompteur")
    fin = texte.index("# <<< Prompteur")
    return texte[debut:fin]


def test_installer_ajoute_ses_lignes_et_la_sequence(boot):
    r = boot["lancer"]("installer")
    assert r.returncode == 0, r.stderr
    texte = boot["config"].read_text(encoding="utf-8")
    assert texte.startswith(ORIGINE)  # rien d'autre n'est touché
    bloc = _bloc(texte)
    assert "[all]\n" in bloc  # sinon nos lignes ne vaudraient que pour [cm5]
    assert "dtoverlay=mipi-dbi-spi,speed=48000000" in bloc
    assert "dtparam=compatible=st7796s\\0panel-mipi-dbi-spi" in bloc  # antislash-zéro littéral
    assert "dtparam=reset-gpio=27,dc-gpio=22,backlight-gpio=18" in bloc
    assert "dtoverlay=ads7846,speed=2000000,penirq=17," in bloc
    assert (boot["tmp"] / "st7796s.bin").read_bytes() == FIRMWARE_FABRICANT
    assert (boot["tmp"] / "config.txt.avant-petit-ecran").read_text(encoding="utf-8") == ORIGINE


def test_reinstaller_ne_double_rien_et_garde_les_choix(boot):
    assert boot["lancer"]("installer", "--rotation", "left", "--tactile", "inverse-y").returncode == 0
    assert boot["lancer"]("installer").returncode == 0
    texte = boot["config"].read_text(encoding="utf-8")
    assert texte.count("# >>> Prompteur") == 1
    assert "xohms=400,invy\n" in _bloc(texte)
    reglage = boot["maison"] / ".config" / "prompteur" / "petit-ecran.conf"
    assert reglage.read_text(encoding="utf-8").strip() == "rotation=left"
    assert boot["lancer"]("installer", "--tactile", "normal").returncode == 0
    assert "xohms=400\n" in _bloc(boot["config"].read_text(encoding="utf-8"))


def test_annuler_rend_le_fichier_d_origine(boot):
    boot["lancer"]("installer", "--rotation", "right")
    r = boot["lancer"]("annuler")
    assert r.returncode == 0, r.stderr
    assert boot["config"].read_text(encoding="utf-8") == ORIGINE
    assert not (boot["maison"] / ".config" / "prompteur" / "petit-ecran.conf").exists()


def test_refuse_s_il_trouve_un_pilote_de_vendeur(boot):
    boot["config"].write_text(ORIGINE + "dtoverlay=tft35a:rotate=90\n", encoding="utf-8")
    r = boot["lancer"]("installer")
    assert r.returncode != 0
    assert "# >>> Prompteur" not in boot["config"].read_text(encoding="utf-8")


def test_refuse_sans_le_pilote_graphique(boot):
    boot["config"].write_text("# config\n#dtoverlay=vc4-kms-v3d\n", encoding="utf-8")
    assert boot["lancer"]("installer").returncode != 0
    assert "# >>> Prompteur" not in boot["config"].read_text(encoding="utf-8")


def test_options_inconnues_refusees(boot):
    assert boot["lancer"]("installer", "--rotation", "diagonale").returncode == 2
    assert boot["lancer"]("installer", "--tactile", "magique").returncode == 2
    assert boot["config"].read_text(encoding="utf-8") == ORIGINE
