# Mettre le boîtier à jour

*Comment installer sur le boîtier tout ce qui a été ajouté depuis sa mise en service.*

**Comptez 30 minutes, une seule fois.** Aucune connaissance en informatique n'est
nécessaire : il s'agit de recopier quatre lignes et de cocher une liste.

> 🎁 **Ce que vous y gagnez, au-delà des nouveautés :** c'est la **dernière fois que vous
> vous déplacez**. À partir de cette mise à jour, le boîtier devient joignable depuis votre
> ordinateur, et les suivantes se feront sans y toucher.

---

## 0. Avant de commencer

### Ce qu'il vous faut, posé devant vous

- [ ] Le boîtier, son **écran**, son **alimentation**
- [ ] Un **clavier USB** branché sur le boîtier *(juste pour aujourd'hui)*
- [ ] Un **câble Ethernet** relié à votre box internet — le boîtier a besoin d'internet
      **le temps de la mise à jour seulement**
- [ ] Votre **téléphone**, pour vérifier à la fin
- [ ] Un **document Word et un PDF** contenant du gras, un titre et une liste à puces —
      ils serviront à l'essai final

### Les deux renseignements à avoir sous la main

Cherchez-les **maintenant**, pas au milieu de la procédure.

| | Où le trouver |
|---|---|
| **Le mot de passe du WiFi `Prompteur`** | Sur la **fiche collée au dos du boîtier**. C'est le renseignement le plus important de cette page — voyez l'encadré rouge de l'étape 4 |
| **Le nom du compte du Raspberry** | Il s'affiche à gauche dans la fenêtre noire, avant le `@`. Vous en aurez besoin pour vous connecter à distance |

> **🛑 Si la fiche du boîtier est vide ou illisible**, arrêtez-vous ici et récupérez le mot
> de passe WiFi d'abord. Faites les étapes 1 et 2, puis tapez cette ligne et **notez la
> réponse sur la fiche** avant de continuer :
> ```bash
> sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur
> ```

### Quand le faire

> **⚠️ Pas la veille d'un tournage.** Choisissez un jour tranquille où vous pouvez tout
> essayer deux fois. Rien n'est risqué — vos textes et vos réglages sont conservés — mais
> une procédure faite dans l'urgence est une procédure bâclée.

---

## Ce qui change pour le journaliste

Le prompteur ne change pas de principe : on branche, on lit au pied.

| Avant | Maintenant |
|---|---|
| Sortir du prompteur demandait deux raccourcis clavier, et y revenir un redémarrage | **Échap** ramène à la page d'accueil, une **icône sur le bureau** rouvre le prompteur |
| Un texte importé partait à l'écran tout seul | L'import **remplit la zone de texte** ; c'est « Envoyer à l'écran » qui diffuse, et rien d'autre |
| Le texte s'affichait tout uni | **Gras, italique, souligné, tailles, couleurs, centrage, puces** |
| Un document arrivait en texte plat | **Word, LibreOffice, PDF, RTF et texte simple** arrivent **avec leur mise en forme** |
| Un fichier illisible remplissait la zone de charabia | Il est **refusé avec un message** |
| Deux modes de pédales | **Trois**, dont un où l'on règle la vitesse au pied |
| Un réglage changé sur le téléphone n'apparaissait pas ailleurs | Tout se met à jour **tout seul**, sur tous les appareils |
| Le boîtier était injoignable à distance | **Accès depuis votre ordinateur**, par le WiFi du boîtier ou par le câble |

---

## Étape 1 — Ouvrir la fenêtre noire

- [ ] **1.** Branchez le **clavier** et le **câble Ethernet** sur le boîtier.
- [ ] **2.** Allumez-le et attendez que le prompteur s'affiche.
- [ ] **3.** Appuyez sur **Alt + F4**. *Le prompteur se ferme, le bureau apparaît.*
- [ ] **4.** Appuyez sur **Ctrl + Alt + T**. *Une fenêtre noire s'ouvre.*

> **⚠️ Dans toute la suite, quand le boîtier demande votre mot de passe, rien ne s'affiche
> à l'écran** — ni étoiles, ni points. C'est normal et voulu. Tapez à l'aveugle, puis
> **Entrée**.

📸 **Au passage, notez le nom du compte** : c'est ce qui est écrit avant le `@` dans la
fenêtre noire. Vous en aurez besoin à l'étape 6.

---

## Étape 2 — Récupérer les nouveautés

```bash
cd ~/prompteur && git pull
```

**✅ Ce que vous devez voir :** une liste de fichiers avec des `+` et des `-`, puis une
ligne du type `xx files changed`.

> **🆘 `Your local changes would be overwritten`** — sans gravité, c'est une permission de
> fichier qui a changé. Recopiez cette ligne, puis reprenez la précédente :
> ```bash
> git checkout -- install/
> ```

> **🆘 `Already up to date.`** — arrêtez-vous et signalez-le. Cela voudrait dire que le
> boîtier ne regarde pas au bon endroit.

---

## Étape 3 — Redémarrer le logiciel

**Obligatoire.** Sans cela, le boîtier continuerait d'afficher les anciennes pages.

```bash
sudo systemctl restart prompteur
```

**✅ Ce que vous devez voir :** rien du tout. Aucune réponse = réussi. *(Le boîtier peut
redemander votre mot de passe : c'est normal, tapez-le à l'aveugle.)*

---

## Étape 4 — Installer les nouveautés du boîtier

Cette étape fait trois choses : elle pose l'**icône « Le Prompteur »** sur le bureau,
renforce la sécurité, et **ouvre l'accès à distance**.

> **🛑 LE PIÈGE À NE PAS MANQUER — lisez ceci avant de taper.**
>
> Cette commande **recrée le réseau WiFi du boîtier**. Si vous oubliez d'y mettre le mot de
> passe **actuel**, le boîtier en **invente un nouveau au hasard**, et plus aucun téléphone
> ne pourra s'y connecter tant que vous ne l'aurez pas relevé.
>
> C'est le mot de passe de la **fiche collée au dos du boîtier** — celui que vous avez
> cherché à l'étape 0.

Recopiez la ligne suivante **en remplaçant `VotreMotDePasse`** par le vôtre, **en gardant
les guillemets** :

```bash
WIFI_PASS="VotreMotDePasse" ./install/setup.sh
```

**✅ Ce que vous devez voir :** des lignes qui défilent pendant deux à trois minutes, puis
un **cadre entouré de signes `=`** annonçant « Installation terminée ». Il contient :

- l'adresse du prompteur et **le mot de passe WiFi** ;
- deux lignes commençant par **`ssh`** — ce sont vos adresses de connexion à distance ;
- la confirmation que l'icône est posée sur le bureau.

📸 **Vérifiez dans ce cadre que le mot de passe WiFi est bien le vôtre**, et pas un autre.
S'il a changé, corrigez la fiche du boîtier **immédiatement**, avant d'oublier.

📸 **Notez aussi les deux lignes `ssh`.** Elles vous éviteront de revenir ici.

> **🆘 Si une ligne signale que SSH n'a pas démarré**, ce n'est pas bloquant pour le
> prompteur. Tapez `sudo raspi-config`, allez dans *Interface Options* → *SSH* → *Yes*,
> puis relancez la commande de cette étape.

---

## Étape 5 — Redémarrer le boîtier

```bash
sudo reboot
```

**✅ Ce que vous devez voir :** l'écran s'éteint, la framboise apparaît, puis en 30 à 60
secondes **le prompteur revient tout seul**, avec le dernier texte.

**Ne débranchez pas encore le câble Ethernet** : il sert à l'essai de l'étape 6.

---

## Étape 6 — Vérifier que tout marche

Cochez au fur et à mesure. Comptez dix minutes. **Si une case ne se coche pas, arrêtez-vous
et signalez-la** plutôt que de continuer.

### Le boîtier

- [ ] Le prompteur s'affiche **tout seul** au démarrage
- [ ] Les **pédales** font défiler le texte
- [ ] Sur l'écran, **Échap** affiche « Revenir à la page d'accueil ? », et un second
      **Échap** y ramène
- [ ] Sur cette page d'accueil, deux boutons en haut : **« Écran principal »** et
      **« Écran secondaire »** ; le premier ramène à l'écran de lecture
- [ ] Sur le bureau du Raspberry, l'icône **« Le Prompteur »** est présente

### Le téléphone

- [ ] Connecté au WiFi **Prompteur** *(avec le mot de passe de la fiche)*, la page
      `http://10.42.0.1:5000` s'ouvre
- [ ] Dans la zone de texte, **sélectionnez quelques mots et appuyez sur G** : ils passent
      en gras **sous vos yeux**
- [ ] **« Envoyer à l'écran »** : le gras apparaît aussi sur le grand écran
- [ ] Tapez une ligne commençant par `- ` *(tiret puis espace)* et envoyez : elle
      s'affiche avec une **puce** sur le grand écran
- [ ] Onglet **Réglages** → carte **Pédales** : il y a bien **trois modes**

### Les documents

- [ ] Importez votre **document Word** : titres, gras et puces se retrouvent à l'écran
- [ ] Importez votre **PDF** : même chose
- [ ] Essayez d'importer une **photo** : elle est **refusée avec un message**, et la zone
      de texte n'est pas abîmée

### L'accès à distance

Depuis **votre ordinateur**, relié à la **même box** que le boîtier. Sur Windows, ouvrez
**PowerShell** — rien à installer.

```bash
ssh nom@prompteur.local
```

*(remplacez `nom` par le nom du compte noté à l'étape 1)*

- [ ] La connexion s'ouvre et affiche une invite du type `nom@prompteur:~ $`

> **🆘 Si `prompteur.local` est introuvable**, ce n'est pas grave : connectez votre
> ordinateur au WiFi **Prompteur** et essayez `ssh nom@10.42.0.1`. Cette adresse-là ne
> change jamais. Le détail est dans **`ACCES-A-DISTANCE.md`**.

**Si toutes les cases sont cochées, la mise à jour est réussie.** Vous pouvez débrancher le
câble Ethernet et le clavier : le boîtier n'en a plus besoin.

---

## Les nouveautés en détail

*À lire tranquillement, ou à transmettre au journaliste — tout est aussi dans
`MODE-EMPLOI.md`.*

### Sortir du prompteur, et y revenir

Sur l'écran de lecture, **Échap** demande confirmation, un second **Échap** ramène à la
page d'accueil. Le texte et la position sont conservés. Pour revenir à la lecture : le
bouton **« Écran principal »**, ou l'**icône du bureau**.

> 💡 **Un seul écran principal à la fois.** Si un autre appareil tient déjà ce rôle, le
> bouton se grise et l'annonce. C'est voulu : deux écrans principaux se disputeraient le
> défilement, et le texte sauterait en pleine lecture.

### Mettre un passage en valeur

Onglet **Texte** : sélectionnez un passage, puis un bouton.

| Bouton | Effet |
|---|---|
| **G** · **I** · **S** | gras · italique · souligné |
| **petit** · **Titre** · **Grand titre** | change la taille du passage |
| Les **cinq pastilles** | change sa couleur |

**Rappuyez sur le même bouton pour enlever l'effet.** « Tout effacer » retire toute la mise
en forme d'un coup. Le résultat apparaît **directement dans la zone de texte**, tel qu'il
sera à l'écran.

### Vos documents arrivent avec leur mise en forme

| | Word · LibreOffice | PDF | RTF | Texte simple |
|---|---|---|---|---|
| Titres | ✅ | ✅ | ✅ | ✅ |
| **Gras**, *italique* | ✅ | ✅ | ✅ | ✅ |
| Souligné | ✅ | ✅ | ✅ | ✅ |
| Couleurs | ✅ | ✅ | ✅ | ✅ |
| Tailles | ✅ | ✅ | ✅ | ✅ |
| Centrage, alignement à droite | ✅ | ✅ | ✅ | ✅ |
| Listes à puces | ✅ | ✅ | ✅ | ✅ |

Deux précisions qui évitent une mauvaise surprise :

- **La couleur est ramenée à la plus proche des cinq du prompteur.** Votre rouge reste
  rouge, mais un bleu marine devient un bleu qui se voit : sur fond noir, recopier votre
  couleur exacte rendrait le passage **invisible** — au moment précis où vous comptiez
  dessus.
- **Les tailles sont conservées en proportion**, pas en points. C'est le lecteur qui fixe
  la taille générale selon sa distance à l'écran ; un « 8 points » recopié tel quel serait
  illisible.

**Ce qui n'est repris dans aucun format** : les images, les tableaux, les polices de
caractères et les retraits. Ce sont des éléments de mise en page ; ils n'ont pas de sens
sur un texte qui défile.

### Écrire la mise en forme au clavier

Un fichier texte simple ne contient aucune mise en forme — c'est sa définition. Il a en
revanche des **signes qui se tapent au clavier**, et le boîtier les comprend. Ils se
répartissent en **deux familles**, et la différence compte.

**1. En début de ligne — ça marche partout**, tapé dans la zone de saisie comme importé :

| Ce que vous tapez | Ce que ça donne |
|---|---|
| `# ` `## ` `### ` | les trois niveaux de titre |
| `- ` *(ou `* `)* | une puce |
| `[centre] ` | la ligne est centrée |
| `[droite] ` | la ligne est alignée à droite |

L'espace après le signe est **obligatoire** — `3 - 4` ne devient pas une puce. Le signe ne
s'affiche pas à l'écran de lecture, mais il **reste dans la zone de saisie** : c'est ce qui
permet de l'enlever. Ils se cumulent : `[centre] # Le titre`.

**2. Autour d'un mot — pour un texte préparé ailleurs :**

| Ce que vous tapez | Ce que ça donne |
|---|---|
| `**important**` | **gras** |
| `*nuance*` | *italique* |
| `_appuyé_` | souligné |
| `[rouge]alerte[/rouge]` | en rouge |

Ceux-là s'appliquent **à l'import d'un fichier**. Dans la zone de saisie, les **boutons
sont plus rapides** : sélectionnez, cliquez. Ces signes servent quand on écrit son texte
dans un éditeur, sur un ordinateur, avant de l'importer.

Les cinq couleurs portent le nom des pastilles, de gauche à droite : `jaune`, `rouge`,
`vert`, `bleu`, `gris`. Les signes se combinent : `**[rouge]très urgent[/rouge]**`.

> 💡 **Rien ne se déclenche par accident.** `3 * 4 = 12`, `mon_texte.txt`,
> `[voir encadré]` ou une note isolée `*` restent tels quels.

La télécommande rappelle les deux familles sous les boutons de mise en forme, dans
**« Écrire la mise en forme au clavier »**.

### L'import ne part plus tout seul

**« Fichier »** et **« Clé USB »** remplissent la zone de texte sans rien diffuser. Un
repère jaune apparaît : *« Ce texte n'est pas encore à l'écran »*. Il disparaît quand on
appuie sur **« Envoyer à l'écran »**.

*(Le bouton « Charger » des textes enregistrés, lui, envoie toujours directement à
l'écran : c'est le geste le plus courant en tournage.)*

> 💡 **Sur un très long document**, la mise en forme est conservée sur les premiers
> passages seulement, et le boîtier le dit au moment de l'import. Le texte, lui, est
> complet.

### Les trois modes de pédales

Onglet **Réglages** → carte **Pédales** → **Mode**. L'explication du mode choisi s'affiche
dessous.

| Mode | Comment ça marche |
|---|---|
| **Maintien** *(celui d'avant)* | Pédale enfoncée = ça défile, relâchée = ça s'arrête |
| **Impulsion** | Une pression lance, une **seconde pression sur la même pédale** met en pause |
| **Dynamique** | La **pédale centrale** fait lecture/pause. La droite accélère, la gauche ralentit puis repart en arrière. **La vitesse atteinte est conservée** au relâchement |

> 💡 Le mode **Dynamique** demande un pédalier à **trois pédales**. Comptez une dizaine de
> secondes d'appui pour atteindre la vitesse maximale — c'est réglable juste en dessous.

### Tout se synchronise

Un réglage changé sur le téléphone apparaît **en moins de trois secondes** sur tous les
autres appareils, sans rien recharger. Idem pour le texte à l'écran et la liste des textes
enregistrés.

Une seule exception, volontaire : **un texte en cours de saisie n'est jamais écrasé.** Si
quelqu'un envoie autre chose pendant ce temps, un message prévient, mais la saisie reste
intacte.

---

## Si quelque chose ne va pas

| Ce que vous constatez | Quoi faire |
|---|---|
| **Le prompteur ne revient pas** après le redémarrage | Attendez **une minute complète**. Toujours rien : rebranchez l'alimentation, attendez, recomptez une minute |
| **L'écran affiche encore l'ancienne version** | L'étape 3 a été oubliée : `sudo systemctl restart prompteur` |
| **Le téléphone ne trouve plus le WiFi « Prompteur »** | Le mot de passe a été régénéré à l'étape 4. Retrouvez-le avec la commande de l'étape 0, et corrigez la fiche |
| **`ssh` répond « Connection refused »** | SSH n'a pas démarré. `sudo raspi-config` → *Interface Options* → *SSH* → *Yes* |
| **`ssh` répond « Could not resolve hostname »** | Votre ordinateur et le boîtier ne sont pas sur le même réseau. Voyez `ACCES-A-DISTANCE.md` |
| **Un bandeau rouge « Liaison avec le boîtier perdue »** | Le texte reste lisible et les pédales fonctionnent. Si le bandeau persiste, redémarrez le boîtier |
| **Rien ne va plus** | Débranchez, attendez 10 secondes, rebranchez, comptez une minute. Votre texte est conservé |

> **🔙 Revenir à la version précédente**, si vraiment nécessaire :
> ```bash
> cd ~/prompteur && git checkout HEAD~1 && sudo systemctl restart prompteur
> ```
> Vos textes et vos réglages ne sont pas touchés.

---

## Et ensuite ?

### Les mises à jour suivantes, sans vous déplacer

Depuis votre ordinateur, deux lignes suffiront désormais :

```bash
ssh nom@prompteur.local
```
```bash
cd ~/prompteur && git pull && sudo systemctl restart prompteur
```

Le boîtier doit être **relié en Ethernet** le temps de l'opération. Tout est détaillé dans
**`ACCES-A-DISTANCE.md`**.

### Le petit écran tactile

Il fait l'objet d'un document à part : **`ECRAN-TACTILE.md`**. Il n'est pas nécessaire au
fonctionnement du prompteur et peut être branché plus tard, sans rien remettre en cause.

---

*Voir aussi : `ACCES-A-DISTANCE.md` (prendre la main sur le boîtier depuis votre
ordinateur), `MODE-EMPLOI.md` (usage quotidien), `SAUVEGARDE-ET-RESTAURATION.md` (revenir
en arrière) et `MISE-EN-ROUTE.md` (installation complète depuis zéro).*
