# Le petit écran tactile — les deux montages possibles

Ce document sert à **brancher l'écran tactile de 3,5 pouces** posé sur les broches
du Raspberry, et à en faire le **tableau de bord du boîtier** : de gros boutons au
doigt pour ouvrir le prompteur, la télécommande ou l'écran de régie, pendant que
le grand écran affiche le texte.

- **Écran concerné** : CUQI / Waveshare 3.5″ RPi LCD **(C)** — 480 × 320, tactile
  résistif (il se pilote à l'ongle ou au stylet), raccordé en **SPI** sur les
  broches GPIO. La mention « SPI 125 MHz » et « 60 FPS » de la fiche produit est
  la signature de ce modèle.
- **Ce document ne concerne que le branchement.** Le tableau de bord, lui, est
  déjà en place et fonctionne sur n'importe quel appareil : il s'ouvre à
  l'adresse **`/menu`**, ou depuis la télécommande, barre « Écran du boîtier ».

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

Le 7″ affiche le prompteur, le 3,5″ affiche le tableau de bord. C'est possible si
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

Il ne reste qu'à afficher le tableau de bord dessus :

```bash
~/prompteur/install/kiosk.sh --menu
```

La fenêtre se place toute seule sur le second écran. Pour la fermer :
`~/prompteur/install/kiosk.sh --menu-stop`.

Pour qu'elle revienne à chaque démarrage, ajoutez la même commande au démarrage
automatique de la session :

```bash
echo "$HOME/prompteur/install/kiosk.sh --menu &" >> "$HOME/.config/labwc/autostart"
```

---

## Montage B — recopie de l'écran principal *(si le mode DRM est indisponible)*

Le petit écran ne peut alors que **répéter** ce que montre le grand. Le tableau de
bord ne peut pas y être affiché seul, et l'afficher en recopie n'aurait pas de
sens : on verrait le prompteur en tout petit.

**Dans ce cas, on n'installe pas le pilote de l'écran.** Le tableau de bord reste
parfaitement utilisable — simplement, il s'ouvre sur l'appareil de votre choix :

- depuis le téléphone ou la tablette : **`http://10.42.0.1:5000/menu`** ;
- depuis la télécommande : barre **« Écran du boîtier »** → **« Tableau de bord »**.

Le confort est moindre, rien n'est perdu, et le boîtier reste intact.

---

## Ce que le tableau de bord affiche

Quatre gros boutons, pensés pour un tactile résistif — cibles larges, bien
séparées, aucun geste fin :

| Bouton | Effet |
|---|---|
| **Prompteur** | ouvre l'écran de lecture (relance le plein écran sur le boîtier) |
| **Télécommande** | coller un texte, régler, sans sortir le téléphone |
| **Écran régie** | l'affichage qui suit, en lecture seule |
| **Fermer** | ferme le prompteur et rend la main au bureau |

En haut, un voyant et l'état du prompteur ; en bas, l'adresse à taper sur le
téléphone et le nom du réseau WiFi. Tout tient sans défilement : sur un écran de
la taille d'une carte bancaire, une barre de défilement est inutilisable.

---

## Si l'écran reste blanc

Un écran SPI **sans pilote chargé** affiche un fond blanc : le rétroéclairage est
allumé, mais rien ne pilote la dalle. **Ce n'est pas une panne** — c'est l'état
normal tant que l'étape A n'a pas été faite, et c'est sans conséquence sur le
reste du boîtier.

---

*Voir aussi : `SAUVEGARDE-ET-RESTAURATION.md` (revenir en arrière) et
`MISE-EN-ROUTE.md` (installation complète du boîtier).*
