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


def test_installer_par_defaut_la_famille_ili9486(boot):
    """La famille la plus répandue (Waveshare A/C et leurs copies) : pilote
    officiel piscreen en mode drm, tactile compris — pas de second ads7846."""
    r = boot["lancer"]("installer")
    assert r.returncode == 0, r.stderr
    texte = boot["config"].read_text(encoding="utf-8")
    assert texte.startswith(ORIGINE)  # rien d'autre n'est touché
    bloc = _bloc(texte)
    assert "[all]\n" in bloc  # sinon nos lignes ne vaudraient que pour [cm5]
    assert "dtoverlay=piscreen,drm,speed=16000000\n" in bloc
    assert "mipi-dbi" not in bloc and "ads7846" not in bloc
    assert (boot["tmp"] / "config.txt.avant-petit-ecran").read_text(encoding="utf-8") == ORIGINE
    reglage = boot["maison"] / ".config" / "prompteur" / "petit-ecran.conf"
    assert reglage.read_text(encoding="utf-8").split() == ["modele=ili9486", "rotation=normal", "tactile="]


def test_installer_le_st7796s_et_sa_sequence(boot):
    r = boot["lancer"]("installer", "--modele", "st7796s")
    assert r.returncode == 0, r.stderr
    bloc = _bloc(boot["config"].read_text(encoding="utf-8"))
    assert "dtoverlay=mipi-dbi-spi,speed=48000000,write-only" in bloc
    assert "dtparam=compatible=st7796s\\0panel-mipi-dbi-spi" in bloc  # antislash-zéro littéral
    assert "dtparam=reset-gpio=27,dc-gpio=22,backlight-gpio=18" in bloc
    assert "dtoverlay=ads7846,speed=2000000,penirq=17," in bloc
    assert "piscreen" not in bloc
    assert (boot["tmp"] / "st7796s.bin").read_bytes() == FIRMWARE_FABRICANT


def _reglage(boot):
    return (boot["maison"] / ".config" / "prompteur" / "petit-ecran.conf").read_text(encoding="utf-8").split()


def test_reinstaller_ne_double_rien_et_garde_les_choix(boot):
    lancer = boot["lancer"]
    assert lancer("installer", "--modele", "st7796s", "--rotation", "left", "--tactile", "inverse-y").returncode == 0
    assert lancer("installer").returncode == 0
    texte = boot["config"].read_text(encoding="utf-8")
    assert texte.count("# >>> Prompteur") == 1
    assert _reglage(boot) == ["modele=st7796s", "rotation=left", "tactile=inverse-y"]
    # Changer de modèle garde la rotation et le réglage du tactile.
    assert lancer("installer", "--modele", "ili9486").returncode == 0
    bloc = _bloc(boot["config"].read_text(encoding="utf-8"))
    assert "dtoverlay=piscreen,drm,speed=16000000\n" in bloc and "mipi-dbi" not in bloc
    assert _reglage(boot) == ["modele=ili9486", "rotation=left", "tactile=inverse-y"]
    # Plusieurs corrections à la fois, rangées dans un ordre fixe.
    assert lancer("installer", "--tactile", "inverse-y,echange").returncode == 0
    assert _reglage(boot) == ["modele=ili9486", "rotation=left", "tactile=echange,inverse-y"]
    assert lancer("installer", "--tactile", "normal").returncode == 0
    assert _reglage(boot) == ["modele=ili9486", "rotation=left", "tactile="]


def test_le_tactile_ne_touche_pas_au_fichier_de_demarrage(boot):
    """Les corrections du tactile sont faites par le bureau : le fichier de
    démarrage n'en porte aucune (le pilote du noyau retourne AVANT d'échanger
    les axes, ses « invx / invy » ne veulent pas dire ce qu'on croit)."""
    assert boot["lancer"]("installer", "--tactile", "echange,inverse-x,inverse-y").returncode == 0
    bloc = _bloc(boot["config"].read_text(encoding="utf-8"))
    assert "invx" not in bloc and "invy" not in bloc and "swapxy" not in bloc


def test_corriger_le_tactile_sans_sudo_ni_redemarrage(boot):
    lancer = boot["lancer"]
    assert lancer("installer", "--rotation", "right").returncode == 0
    avant = boot["config"].read_text(encoding="utf-8")
    r = lancer("tactile", "inverse-y")
    assert r.returncode == 0, r.stderr
    assert _reglage(boot) == ["modele=ili9486", "rotation=right", "tactile=inverse-y"]
    assert boot["config"].read_text(encoding="utf-8") == avant  # rien à redémarrer
    assert lancer("tactile", "magique").returncode == 2
    assert _reglage(boot) == ["modele=ili9486", "rotation=right", "tactile=inverse-y"]


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
    assert boot["lancer"]("installer", "--modele", "hdmi").returncode == 2
    assert boot["lancer"]("installer", "--tactile", "echange,magique").returncode == 2
    assert boot["lancer"]("installer", "--tactile", "").returncode == 2
    assert boot["config"].read_text(encoding="utf-8") == ORIGINE


def test_matrice_du_tactile_avec_les_mesures_du_boitier():
    """Mesures relevées sur le boîtier (valeurs brutes de la dalle, sur 65535) :
    haut et bas étaient inversés. Avec « inverse-y », chaque coin doit tomber
    dans le bon coin du petit écran (480 × 320, à droite du grand : x de 1920
    à 2400, y de 0 à 320, sur un bureau de 2400 × 1080)."""
    kiosk = (RACINE / "install" / "kiosk.sh").as_posix()
    sortie = subprocess.run(  # nosec B603 - script du dépôt, arguments fixes
        [
            _bash(),
            "-c",
            'source <(sed -n "/^composer_matrice()/,/^}/p" "$1"); composer_matrice "$2" "$3"',
            "essai",
            kiosk,
            "0.200000, 0.000000, 0.800000, 0.000000, 0.296296, 0.000000, 0.000000, 0.000000, 1.000000",
            "inverse-y",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    m = [float(v) for v in sortie.stdout.split()]
    assert len(m) == 9, sortie.stderr

    def ecran(u, v):
        u, v = u / 65535, v / 65535
        return (m[0] * u + m[1] * v + m[2]) * 2400, (m[3] * u + m[4] * v + m[5]) * 1080

    hg_x, hg_y = ecran(4287.93, 62847.04)  # coin touché : en haut à gauche
    hd_x, hd_y = ecran(61503.06, 61119.07)  # en haut à droite
    bg_x, bg_y = ecran(4575.93, 2847.96)  # en bas à gauche
    assert 1920 <= hg_x < 2000 and 0 <= hg_y < 40
    assert 2320 < hd_x <= 2400 and 0 <= hd_y < 40
    assert 1920 <= bg_x < 2000 and 280 < bg_y <= 320
