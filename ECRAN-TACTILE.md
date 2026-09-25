# Le petit écran tactile du boîtier

Le **petit écran** posé sur le Raspberry affiche la vue **Settings** (ou **Spectateur**,
d'un appui) pendant que le grand écran affiche le texte : une copie de
`http://10.42.0.1:5000`, **sans passer par le WiFi**.

- **Écran concerné** : Waveshare **« 3.5inch RPi LCD (G) »** — sa carte porte l'inscription
  **« 3.5 inch Display-G »**. Dalle IPS 320 × 480, contrôleur **ST7796S**, tactile résistif
  **XPT2046** (il se pilote à l'ongle ou au stylet), relié par les **broches** du Raspberry
  (en SPI), **pas en HDMI**.
- **Tant qu'il n'est pas installé, il reste blanc** : le rétroéclairage est allumé, mais rien
  ne pilote la dalle. Ce n'est pas une panne.

---

## Installer le petit écran (5 minutes, une seule fois)

Dans la fenêtre noire du boîtier (**Ctrl + Alt + T**) ou en SSH :

```bash
cd ~/prompteur && git pull
```

```bash
sudo ./install/petit-ecran.sh installer
```

**✅ Attendu :** « Petit écran préparé », puis le nom de la sauvegarde du fichier de démarrage.

```bash
sudo reboot
```

**✅ Attendu, une minute plus tard :** le texte sur le grand écran, et la page **Settings** sur
le petit.

Ce que fait `petit-ecran.sh` : il ajoute au fichier de démarrage (`config.txt`, sauvegardé
avant) les lignes que le fabricant recommande — le pilote **officiel** `mipi-dbi-spi` de
Raspberry Pi avec la séquence d'allumage du ST7796S, et le pilote officiel `ads7846` du
tactile. Au démarrage, le boîtier relie ce petit écran au bureau, cale le tactile dessus et y
ouvre la vue Settings. Le grand écran n'est pas touché.

### Si le résultat n'est pas le bon

| Ce que vous voyez | La ligne à taper, puis `sudo reboot` |
|---|---|
| La page est **couchée** (écran monté en largeur) | `sudo ./install/petit-ecran.sh installer --rotation left` *(ou `right` si elle est couchée de l'autre côté ; `inverted` si elle est à l'envers)* |
| Le **doigt tombe à côté**, en miroir gauche-droite | `sudo ./install/petit-ecran.sh installer --tactile inverse-x` |
| … en miroir haut-bas | `sudo ./install/petit-ecran.sh installer --tactile inverse-y` |
| … le doigt va en haut quand on va à droite | `sudo ./install/petit-ecran.sh installer --tactile echange` |
| **Toujours blanc** | `./install/petit-ecran.sh etat` *(sans sudo)* : envoyez une photo de ce qui s'affiche |

Chaque relance garde les autres choix (la rotation ne défait pas le réglage du tactile).

### Revenir en arrière

```bash
sudo ./install/petit-ecran.sh annuler
```

puis `sudo reboot` : le boîtier revient exactement comme avant.

> 📌 **Si le boîtier ne redémarre plus du tout** : éteignez, sortez la carte SD et mettez-la
> dans un ordinateur. La partition de démarrage est **lisible sous Windows** : remplacez
> `config.txt` par `config.txt.avant-petit-ecran`, replacez la carte. Voir
> **SAUVEGARDE-ET-RESTAURATION.md**.

---

## 🛑 Ne pas lancer les pilotes du vendeur

Les scripts fournis avec ce type d'écran (`LCD35-show`, `LCD35G-show`, `fbcp`, le fichier
`Waveshare35g.dtbo`…) sont faits pour un Raspberry qui n'a **qu'un seul écran** :

1. ils **désactivent le pilote graphique** `vc4-kms-v3d` — sur un Raspberry Pi 5, il n'existe
   aucun mode de secours derrière ;
2. ils **forcent la sortie HDMI en 480 × 320**, ou recopient l'écran principal sur le petit.

Ici il y a deux écrans, qui doivent afficher des choses différentes. `petit-ecran.sh` refuse
d'ailleurs de s'installer par-dessus leurs lignes.

---

## Écran de 7 pouces en HDMI, à la place : rien à installer

Un petit écran **HDMI** se branche sur la **seconde prise HDMI** du Raspberry — le grand écran
reste sur la prise **collée à l'alimentation**. À chaque lancement du prompteur, le boîtier met
les deux écrans côte à côte, cale le tactile sur le petit et y ouvre la vue Settings.
Écrans inversés (le texte sur le petit) : intervertissez les deux câbles et redémarrez.

---

## Ce que le petit écran affiche

La vue **Settings**, comme sur le téléphone, avec tout en haut :

| Groupe | Boutons | Effet |
|---|---|---|
| **Écran régie** | **Settings** · **Spectateur** | ce qu'affiche **ce petit écran** : texte, réglages, commandes — ou le texte qui défile, en direct, en lecture seule |
| **Écran journaliste** | **Settings** · **Journaliste** · **Bureau** | ce qu'affiche **le grand écran** |
| | **⏻ Veille** | éteint le grand écran et met le petit au noir ; un appui sur le petit écran rallume tout |

---

## Pour le dépannage à distance

```bash
~/prompteur/install/kiosk.sh --ecrans
```

dit quelles cartes graphiques et quels écrans le bureau voit, lequel est le grand, lequel le
petit, et quelle dalle tactile est reconnue. `~/prompteur/install/kiosk.sh --menu` rouvre la vue
Settings sur le petit écran (et dit pourquoi, s'il ne peut pas) ; `--menu-stop` la ferme.

*Voir aussi : `SAUVEGARDE-ET-RESTAURATION.md` (revenir en arrière) et
`MISE-EN-ROUTE.md` (installation complète du boîtier).*
