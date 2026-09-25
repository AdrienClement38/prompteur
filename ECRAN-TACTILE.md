# Le petit écran tactile — les deux montages possibles

Ce document sert à **brancher l'écran tactile de 3,5 pouces** posé sur les broches
du Raspberry, et à en faire le **petit écran de contrôle du boîtier** : il affiche la
vue **Settings** (ou **Spectateur**, d'un appui), pendant que le grand écran affiche
le texte.

- **Écran concerné** : CUQI / Waveshare 3.5″ RPi LCD **(C)** — 480 × 320, tactile
  résistif (il se pilote à l'ongle ou au stylet), raccordé en **SPI** sur les
  broches GPIO. La mention « SPI 125 MHz » et « 60 FPS » de la fiche produit est
  la signature de ce modèle.
- **Ce document ne concerne que le branchement.** Les vues Settings et
  Spectateur, elles, sont déjà en place et fonctionnent sur n'importe quel
  appareil : **`/settings`** et **`/spectateur`**.
- **Écran de 7 pouces à la place ?** Voir juste en dessous : il n'y a **rien à
  installer**.

---

## Écran de 7 pouces HDMI : rien à faire

Branchez-le sur la **seconde prise HDMI** du Raspberry — le grand écran, celui qu'on
lit, reste sur la prise **collée à l'alimentation** — et redémarrez. **C'est tout** : à
chaque lancement du prompteur, le boîtier

1. repère les deux écrans ; s'ils affichent la même chose (recopie), il place le petit
   **à côté** du grand ;
2. cale la **dalle tactile** sur le petit écran (sans cela, un appui y tomberait à
   côté) ;
3. y ouvre la **vue Settings en plein écran** — une copie de `http://10.42.0.1:5000`,
   **sans passer par le WiFi**.

Pour vérifier ce que le boîtier a reconnu, dans la fenêtre noire du boîtier (ou en
SSH) :

```bash
~/prompteur/install/kiosk.sh --ecrans
```

**Ce que vous devez voir :** le **grand écran** et le **petit écran** avec leur nom
(`HDMI-1`, `HDMI-2`…), la dalle tactile reconnue, et « Vue Settings du petit écran :
affichée ».

> 📌 **Le texte s'affiche sur le petit écran, et Settings sur le grand ?** Les câbles
> sont inversés côté boîtier : intervertissez-les et redémarrez.

> 📌 **Le petit écran reste sur le bureau** : lancez `~/prompteur/install/kiosk.sh --menu`
> et lisez le message. « Un seul écran branché » = le système ne le voit pas (câble,
> alimentation de l'écran). « n'a pas pu être placé à côté du grand » = il refuse la
> disposition : rien n'est ouvert, pour ne jamais couvrir le prompteur.

Les sections suivantes ne concernent **que le petit écran de 3,5 pouces** sur broches.

---

## 🛑 Avant tout : ne pas lancer le pilote du vendeur

Le script fourni avec ce type d'écran (`LCD35C-show` ou équivalent) fait deux
choses incompatibles avec ce boîtier :

1. il **désactive le pilote graphique** `vc4-kms-v3d` — sur un Raspberry Pi 5, il
   n'existe aucun mode de secours derrière ;
2. il **force la sortie HDMI en 480 × 320** — votre écran 7″ serait rabaissé à la
   résolution du petit et afficherait la même chose.

Ce script est conçu pour un Raspberry qui n'a **qu'un seul écran**. Ici il y en a
deux, et ils doivent afficher des choses différentes.

---

## 1. Savoir de quoi on dispose

Ces deux commandes ne font que **lire**, elles ne modifient rien :

```bash
ls /boot/firmware/overlays/ | grep -iE "waveshare|piscreen|tft35|ili9|mipi"
```

```bash
grep -vE "^\s*#|^\s*$" /boot/firmware/config.txt
```

La première dit quels pilotes d'écran sont disponibles. **C'est elle qui décide
du montage** : selon qu'un pilote accepte ou non le mode « DRM », le petit écran
sera un véritable second écran, ou une simple recopie du grand.

---

## 2. Sauvegarder le fichier de démarrage

Une seule ligne, et c'est ce qui permet de revenir en arrière quoi qu'il arrive :

```bash
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.avant-ecran
```

> 📌 **Si le boîtier ne redémarre plus** : éteignez, sortez la carte SD et mettez-la
> dans un ordinateur. La partition de démarrage est **lisible sous Windows** :
> ouvrez `config.txt` dans le Bloc-notes, remettez le contenu de la sauvegarde,
> replacez la carte. Voir **SAUVEGARDE-ET-RESTAURATION.md**.

---

## Montage A — deux écrans indépendants *(celui qu'on vise)*

Le grand écran affiche le prompteur, le petit affiche la vue Settings. C'est possible si
un pilote accepte le suffixe `,drm`, qui fait du petit écran une **sortie
graphique à part entière** au lieu d'une recopie.

Ajoutez à la fin de `/boot/firmware/config.txt`, **sans rien supprimer d'autre** :

```
dtparam=spi=on
dtoverlay=waveshare35c,drm
```

> Remplacez `waveshare35c` par le nom réellement présent dans la liste de
> l'étape 1. `piscreen` et `tft35a` sont les autres noms courants pour cette
> famille d'écrans.

**Ce qu'il ne faut surtout pas faire** : commenter la ligne `dtoverlay=vc4-kms-v3d`.
Elle doit rester.

Redémarrez, puis vérifiez que le système voit bien **deux écrans** :

```bash
xrandr --query | grep " connected"
```

**Ce que vous devez voir :** deux lignes, l'une pour le HDMI, l'autre pour le petit
écran. S'il n'y en a qu'une, c'est le montage B.

La vue Settings s'y affiche alors **toute seule** à chaque lancement du prompteur,
en plein écran, à sa taille exacte. Pour la fermer : `~/prompteur/install/kiosk.sh
--menu-stop` ; pour la rouvrir : `~/prompteur/install/kiosk.sh --menu`.

---

## Montage B — recopie de l'écran principal *(si le mode DRM est indisponible)*

Le petit écran ne peut alors que **répéter** ce que montre le grand. La vue
Settings ne peut pas y être affichée seule, et l'afficher en recopie n'aurait pas de
sens : on verrait le prompteur en tout petit.

**Dans ce cas, on n'installe pas le pilote de l'écran.** Les vues Settings et
Spectateur restent parfaitement utilisables — simplement, elles s'ouvrent sur
l'appareil de votre choix : **`http://10.42.0.1:5000/settings`** depuis le téléphone,
la tablette ou le PC de la régie.

Le confort est moindre, rien n'est perdu, et le boîtier reste intact.

---

## Ce que le petit écran affiche

La vue **Settings**, comme sur le téléphone, avec tout en haut :

| Groupe | Boutons | Effet |
|---|---|---|
| **Écran régie** | **Settings** · **Spectateur** | ce qu'affiche **ce petit écran** : texte, réglages, commandes — ou le texte qui défile, en direct, en lecture seule |
| **Écran journaliste** | **Settings** · **Journaliste** · **Bureau** | ce qu'affiche **le grand écran** |
| | **⏻ Veille** | éteint le grand écran et met le petit au noir ; un appui sur le petit écran rallume tout |

Settings et Spectateur passent de l'une à l'autre d'un seul appui : on change un
réglage, puis on revient au texte aussitôt.

---

## Si l'écran reste blanc

Un écran SPI **sans pilote chargé** affiche un fond blanc : le rétroéclairage est
allumé, mais rien ne pilote la dalle. **Ce n'est pas une panne** — c'est l'état
normal tant que l'étape A n'a pas été faite, et c'est sans conséquence sur le
reste du boîtier.

---

*Voir aussi : `SAUVEGARDE-ET-RESTAURATION.md` (revenir en arrière) et
`MISE-EN-ROUTE.md` (installation complète du boîtier).*
