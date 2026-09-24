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
- **Écran de 7 pouces à la place ?** Si c'est un écran HDMI, il se branche sur la
  **seconde prise HDMI** du Raspberry, sans aucun pilote : passez directement à la
  vérification de la fin du montage A (`xrandr`), puis à `kiosk.sh --menu`.

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

Il ne reste qu'à afficher la vue Settings dessus :

```bash
~/prompteur/install/kiosk.sh --menu
```

La fenêtre se place toute seule sur le second écran, à sa taille exacte. Pour la fermer :
`~/prompteur/install/kiosk.sh --menu-stop`.

Pour qu'elle revienne à chaque démarrage, ajoutez la même commande au démarrage
automatique de la session :

```bash
echo "$HOME/prompteur/install/kiosk.sh --menu &" >> "$HOME/.config/labwc/autostart"
```

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

La vue **Settings**, comme sur le téléphone, avec tout en haut trois boutons :

| Bouton | Effet |
|---|---|
| **Settings** | texte, réglages, commandes — et la section « Vue du journaliste », qui choisit ce que montre le grand écran |
| **Spectateur** | le texte qui défile, en direct, en lecture seule |
| **⏻ Veille** | éteint le grand écran et met le petit au noir ; un appui sur le petit écran rallume tout |

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
