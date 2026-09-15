# Mettre le boîtier à jour

*Comment installer sur le boîtier tout ce qui a été ajouté depuis sa mise en service.*
*Prévoyez 20 minutes, une seule fois. Aucune connaissance en informatique n'est
nécessaire : il s'agit de recopier trois lignes.*

---

> **📦 Ce qu'il vous faut, posé devant vous, avant de commencer**
>
> - [ ] Le boîtier, son **écran**, son **alimentation**
> - [ ] Un **clavier USB** branché sur le boîtier *(juste pour aujourd'hui)*
> - [ ] Un **câble Ethernet** relié à votre box internet — le boîtier a besoin
>       d'internet **le temps de la mise à jour seulement**
> - [ ] Votre téléphone, pour vérifier à la fin
>
> **Ne faites pas cette mise à jour la veille d'un tournage.** Choisissez un jour
> tranquille où vous pouvez tout essayer deux fois.

---

## Ce qui change pour vous

Le prompteur ne change pas de principe : on branche, on lit au pied. Mais six
choses deviennent plus simples.

| Avant | Maintenant |
|---|---|
| Sortir du prompteur demandait deux raccourcis clavier, et y revenir un redémarrage | **La touche Échap** ramène à la page d'accueil. Une **icône sur le bureau** rouvre le prompteur |
| Un texte importé partait à l'écran tout seul, sans qu'on l'ait demandé | L'import **remplit la zone de texte**. C'est « Envoyer à l'écran » qui diffuse, et rien d'autre |
| Le texte s'affichait tout uni | On peut mettre des passages en **gras**, en *italique*, en souligné, en plus gros ou **en couleur** |
| Un document arrivait en texte plat | **Tous les formats** arrivent avec leur mise en forme : titres, gras, italique, souligné, couleurs, tailles, centrage et puces |
| Deux modes de pédales | **Trois**, dont un où l'on règle la vitesse au pied |
| Un réglage changé sur le téléphone n'apparaissait pas sur les autres appareils | Tout se met à jour **tout seul**, partout |

---

## Étape 1 — Ouvrir la fenêtre noire

- [ ] **1.** Branchez le **clavier** et le **câble Ethernet** sur le boîtier.
- [ ] **2.** Allumez-le et attendez que le prompteur s'affiche.
- [ ] **3.** Appuyez sur **Alt + F4**. *Le prompteur se ferme, le bureau apparaît.*
- [ ] **4.** Appuyez sur **Ctrl + Alt + T**. *Une fenêtre noire s'ouvre.*

> **⚠️ Pendant toute la suite, quand le boîtier demande votre mot de passe, rien
> ne s'affiche à l'écran** — ni étoiles, ni points. C'est normal et voulu. Tapez
> à l'aveugle, puis appuyez sur Entrée.

---

## Étape 2 — Récupérer les nouveautés

Recopiez cette ligne, exactement, puis **Entrée** :

```bash
cd ~/prompteur && git pull
```

**✅ Ce que vous devez voir :** une liste de fichiers avec des `+` et des `-`, puis
une ligne du type `xx files changed`.

> **🆘 Si le boîtier répond `Your local changes would be overwritten`** — sans
> gravité, c'est une permission de fichier qui a changé. Recopiez cette ligne,
> puis reprenez la précédente :
> ```bash
> git checkout -- install/
> ```

> **🆘 Si le boîtier répond `Already up to date.`** — arrêtez-vous et
> signalez-le : cela voudrait dire qu'il ne regarde pas au bon endroit.

---

## Étape 3 — Redémarrer le logiciel

C'est **obligatoire** : sans cela, le boîtier continuerait d'afficher les
anciennes pages.

```bash
sudo systemctl restart prompteur
```

**✅ Ce que vous devez voir :** rien du tout. Aucune réponse = réussi. *(Le boîtier
vous redemandera peut-être votre mot de passe : c'est normal, tapez-le à
l'aveugle.)*

---

## Étape 4 — Poser l'icône sur le bureau *(recommandé)*

Cette étape installe l'**icône « Le Prompteur »** sur le bureau et renforce la
sécurité du boîtier. Elle n'est pas indispensable au fonctionnement, mais c'est
elle qui vous permettra de rouvrir le prompteur d'un double-clic.

> **🛑 LE PIÈGE À NE PAS MANQUER.** Cette commande **recrée le réseau WiFi du
> boîtier**. Si vous oubliez d'y mettre votre mot de passe actuel, **le boîtier
> en invente un nouveau au hasard**, et plus aucun téléphone ne pourra s'y
> connecter tant que vous ne l'aurez pas relevé.
>
> **Le mot de passe à utiliser est celui écrit sur la fiche collée au dos du
> boîtier.** Si la fiche est vide, retrouvez-le d'abord avec :
> ```bash
> sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur
> ```

Recopiez la ligne suivante **en remplaçant `VotreMotDePasse`** par le vôtre, en
gardant bien les guillemets :

```bash
WIFI_PASS="VotreMotDePasse" ./install/setup.sh
```

**✅ Ce que vous devez voir :** des lignes qui défilent pendant deux à trois
minutes, puis un **cadre entouré de signes `=`** annonçant « Installation
terminée », avec l'adresse et le mot de passe WiFi.

📸 **Vérifiez dans ce cadre que le mot de passe est bien le vôtre**, et pas un
autre. S'il a changé, corrigez la fiche du boîtier immédiatement.

---

## Étape 5 — Redémarrer le boîtier

```bash
sudo reboot
```

**✅ Ce que vous devez voir :** l'écran s'éteint, la framboise apparaît, puis en 30
à 60 secondes **le prompteur revient tout seul** avec votre dernier texte.

Vous pouvez débrancher le câble Ethernet : le boîtier n'a plus besoin d'internet.

---

## Étape 6 — Vérifier que tout marche

Cochez au fur et à mesure. Comptez cinq minutes.

- [ ] Le prompteur s'affiche **tout seul** au démarrage
- [ ] Les **pédales** font défiler le texte
- [ ] Sur l'écran du prompteur, la touche **Échap** affiche « Revenir à la page
      d'accueil ? », et un second **Échap** y ramène
- [ ] Sur cette page d'accueil, deux boutons apparaissent en haut :
      **« Écran principal »** et **« Écran secondaire »**
- [ ] Le bouton **« Écran principal »** ramène à l'écran de lecture
- [ ] Sur le bureau du Raspberry, l'icône **« Le Prompteur »** est présente
      *(seulement si vous avez fait l'étape 4)*
- [ ] Depuis le téléphone connecté au WiFi **Prompteur**, la page
      `http://10.42.0.1:5000` s'ouvre normalement
- [ ] Dans la zone de texte, **sélectionnez quelques mots et appuyez sur G** :
      ils passent en gras **sous vos yeux**
- [ ] **« Envoyer à l'écran »** : le gras apparaît aussi sur le grand écran
- [ ] Importez un document Word **puis un PDF** contenant du **gras**, un **passage en couleur**, un
      **titre** et une **liste à puces** : tout se retrouve à l'écran de lecture
- [ ] Onglet **Réglages** → carte **Pédales** : il y a maintenant **trois modes**
      (Maintien, Impulsion, Dynamique)

Si les onze cases sont cochées, la mise à jour est réussie.

---

## Les nouveautés en détail

### Sortir du prompteur, et y revenir

Sur l'écran de lecture, **Échap** demande confirmation, et un second **Échap**
ramène à la page d'accueil. Le texte et la position sont conservés.

Pour revenir à la lecture : le bouton **« Écran principal »** de l'accueil, ou
l'**icône sur le bureau** du Raspberry.

> 💡 **Un seul écran principal à la fois.** Si un autre appareil tient déjà ce
> rôle, le bouton se grise et l'annonce. C'est voulu : deux écrans principaux se
> disputeraient le défilement, et le texte sauterait en pleine lecture.

### Mettre un passage en valeur

Dans l'onglet **Texte**, sélectionnez un passage, puis appuyez sur :

| Bouton | Effet |
|---|---|
| **G** | gras |
| **I** | italique |
| **S** | souligné |
| **petit · Titre · Grand titre** | change la taille du passage |
| Les **cinq pastilles de couleur** | change sa couleur |

**Rappuyez sur le même bouton pour enlever l'effet.** « Tout effacer » retire
toute la mise en forme d'un coup.

La mise en forme apparaît **directement dans la zone de texte**, telle qu'elle
sera à l'écran.

### Vos documents arrivent avec leur mise en forme

Un document importé conserve ses **titres**, son **gras**, son *italique*, ses **couleurs**,
ses **tailles** (en proportion du reste), le **centrage** de ses paragraphes et ses **listes à
puces** — et cela vaut pour **Word (`.docx`), LibreOffice (`.odt`), le PDF et le RTF**.

Le **fichier texte simple**, lui, n'a pas de mise en forme à conserver — c'est sa
définition. Il comprend en revanche les signes qui se tapent au clavier, et ils couvrent
tout :

| Ce que vous tapez | Ce que ça donne |
|---|---|
| `# ` `## ` `### ` en début de ligne | les trois niveaux de titre |
| `- ` en début de ligne | une puce |
| `[centre] ` `[droite] ` en début de ligne | la ligne est centrée, ou à droite |
| `**important**` | **gras** |
| `*nuance*` | *italique* |
| `_appuyé_` | souligné |
| `[rouge]alerte[/rouge]` | en rouge |

Les cinq couleurs portent le nom des pastilles, de gauche à droite : `jaune`, `rouge`,
`vert`, `bleu`, `gris`. Les signes se combinent : `**[rouge]très urgent[/rouge]**`.

**Rien ne se déclenche par accident** : `3 * 4 = 12`, `mon_texte.txt`, `[voir encadré]` ou
une note isolée `*` restent tels quels. Les mêmes signes fonctionnent directement dans la
zone de saisie de la télécommande.

Deux précisions qui évitent une mauvaise surprise :

- **La couleur est ramenée à la plus proche des cinq du prompteur.** Votre rouge reste rouge,
  mais un bleu marine devient un bleu qui se voit : sur fond noir, recopier votre couleur
  exacte rendrait le passage invisible.
- **Le centrage ne se voit que sur l'écran de lecture**, pas dans la zone de saisie de la
  télécommande, qui est une simple ligne de texte.

Un fichier qui n'est pas un document texte (une photo, une archive) est maintenant **refusé
avec un message**. Avant, il remplissait la zone de texte de caractères illisibles sans rien
dire.

### Écrire la mise en forme au clavier

Sous les boutons de mise en forme, un bloc **« Écrire la mise en forme au clavier »** se
déplie et rappelle tous les signes du tableau ci-dessus. L'espace après les dièses et le
tiret est obligatoire. C'est exactement la forme sous laquelle arrive un fichier texte
importé.

### L'import ne part plus tout seul

**« Fichier »** et **« Clé USB »** remplissent maintenant la zone de texte sans
rien diffuser. Un repère jaune apparaît : *« Ce texte n'est pas encore à
l'écran »*. Il disparaît quand vous appuyez sur **« Envoyer à l'écran »**.

*(Le bouton « Charger » de vos textes enregistrés, lui, envoie toujours
directement à l'écran : c'est le geste le plus courant en tournage.)*

### Les trois modes de pédales

Onglet **Réglages** → carte **Pédales** → **Mode**. L'explication du mode choisi
s'affiche dessous.

| Mode | Comment ça marche |
|---|---|
| **Maintien** *(celui d'avant)* | Pédale enfoncée = ça défile, relâchée = ça s'arrête |
| **Impulsion** | Une pression lance, une **seconde pression sur la même pédale** met en pause |
| **Dynamique** | La **pédale centrale** fait lecture/pause. La droite accélère, la gauche ralentit puis repart en arrière. **La vitesse atteinte est conservée** quand vous relâchez |

> 💡 Le mode **Dynamique** demande un pédalier à **trois pédales**. Comptez une
> dizaine de secondes d'appui pour atteindre la vitesse maximale — c'est réglable
> juste en dessous.

### Tout se synchronise

Un réglage changé sur le téléphone apparaît **en moins de trois secondes** sur
tous les autres appareils, sans recharger quoi que ce soit. Idem pour le texte à
l'écran et la liste de vos textes enregistrés.

Une seule exception, volontaire : **un texte que vous êtes en train d'écrire n'est
jamais écrasé.** Si quelqu'un envoie autre chose pendant ce temps, un message vous
prévient, mais votre saisie reste intacte.

---

## Si quelque chose ne va pas

| Ce que vous constatez | Quoi faire |
|---|---|
| **Le prompteur ne revient pas** après le redémarrage | Attendez **une minute complète**. Toujours rien : rebranchez l'alimentation, attendez, recomptez une minute |
| **L'écran affiche encore l'ancienne version** | L'étape 3 a été oubliée. Refaites-la : `sudo systemctl restart prompteur` |
| **Le téléphone ne trouve plus le WiFi « Prompteur »** | Le mot de passe a probablement été régénéré à l'étape 4. Retrouvez-le avec la commande de l'encadré, et corrigez la fiche du boîtier |
| **Un bandeau rouge « Liaison avec le boîtier perdue »** | Le texte affiché reste lisible et les pédales fonctionnent. Si le bandeau persiste, redémarrez le boîtier |
| **Rien ne va plus** | Débranchez, attendez 10 secondes, rebranchez, comptez une minute. Votre texte est conservé |

> **🔙 Revenir à la version précédente**, si vraiment nécessaire :
> ```bash
> cd ~/prompteur && git checkout HEAD~1 && sudo systemctl restart prompteur
> ```
> Vos textes et vos réglages ne sont pas touchés.

---

## Et le petit écran tactile ?

Il fait l'objet d'un document à part : **ECRAN-TACTILE.md**. Il n'est pas
nécessaire au fonctionnement du prompteur, et peut être branché plus tard, sans
rien remettre en cause.

---

*Voir aussi : `MODE-EMPLOI.md` (usage quotidien, à jour de toutes ces
nouveautés), `SAUVEGARDE-ET-RESTAURATION.md` (revenir en arrière), et
`MISE-EN-ROUTE.md` (installation complète depuis zéro).*
