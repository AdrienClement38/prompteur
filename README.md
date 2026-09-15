# 🎬 Le Prompteur — téléprompteur à pédales, hors-ligne

Un boîtier **dédié** (Raspberry Pi) qui fait défiler votre texte à l'écran, piloté
aux **pédales**. Le texte s'envoie **depuis un téléphone** (le boîtier crée son
propre WiFi) ou **par clé USB**. **Aucune connexion internet n'est nécessaire.**

> 🧑‍🏫 **Vous n'êtes pas informaticien ? Cette page n'est pas faite pour vous.**
> Deux documents le sont, sans une seule commande à taper :
> - **[MISE-EN-ROUTE.md](MISE-EN-ROUTE.md)** ([PDF](Mise-En-Route-Prompteur.pdf)) —
>   installer le boîtier, pas à pas, pour quelqu'un qui n'a jamais ouvert un terminal.
> - **[MODE-EMPLOI.md](MODE-EMPLOI.md)** ([PDF](Mode-Emploi-Prompteur.pdf)) —
>   l'usage quotidien pour la personne qui lit face caméra, avec une fiche à coller
>   sur le boîtier.
>
> Le reste de cette page est technique.
> *Le fichier `Guide-Prompteur.pdf`, à la racine du dossier, décrit une version
> ancienne du logiciel : ne l'imprimez pas, ne le suivez pas.*

---

## 1. Liste de courses (matériel)

| Élément | Rôle | Prix indicatif |
|---|---|---|
| **Kit Starter Raspberry Pi 5** (4 Go) — carte, alimentation, boîtier, ventilateur et câble micro‑HDMI compris | Le cerveau, et tout ce qu'il faut autour | ~175–185 € |
| **Écran HDMI 7″** : moniteur simple (~55 €) **ou** écran tactile officiel (~80 €) | Affiche le texte | ~55–80 € |
| **Pédalier USB programmable à 3 pédales** (par exemple PCsensor FS2020U) | Pédales gauche / centrale / droite | ~30–45 € |

**Total : environ 265 à 310 €.** Prix relevés en **septembre 2026**, à vérifier au
moment de l'achat : les tarifs Raspberry Pi ont fortement augmenté récemment
(coût de la mémoire).

*En option, pour lire en regardant l'objectif* : une vitre sans tain et son
support, ~50 à 150 € (voir § 10).

> 💡 **Les pédales doivent être programmables**, c'est-à-dire réglables pour
> envoyer une touche du clavier (flèche haut, flèche bas…) quand on appuie dessus.
> C'est le cas de la plupart des pédales USB de transcription et des pédales
> « tourne-pages » pour musiciens. Par défaut : **pédale droite = Flèche bas**,
> **pédale gauche = Flèche haut**, **pédale centrale = Flèche droite** — tout cela
> se règle dans l'application (§ 6). Prenez un pédalier à **trois pédales** : la
> troisième sert au mode **Dynamique**.

> *Si vous préférez acheter pièce par pièce, sans kit* : Raspberry Pi 5 4 Go
> ~130 € + carte microSD 32 Go (~8–12 € vierge, ~12–16 € pré‑installée) +
> alimentation officielle ~12 € + boîtier et ventilateur ~10–15 € + câble
> micro‑HDMI vers HDMI ~7 €.

---

## 2. Les touches de l'écran de lecture

**Sur l'écran principal, les touches suivantes répondent :**

| Touche | Effet |
|---|---|
| **Flèche bas** = pédale droite | avancer |
| **Flèche haut** = pédale gauche | reculer |
| **Flèche droite** = pédale centrale | lecture / pause *(mode Dynamique uniquement)* |
| **Espace** | lance ou arrête le défilement tout seul, à la vitesse réglée, sans toucher aux pédales *(mode Maintien uniquement)* |
| **+ / −** | plus vite / moins vite |
| **R** | retour au début |
| **M** | miroir |
| **H** | masquer ou réafficher le bandeau d'aide |
| **i** | affiche les adresses des deux écrans de lecture (§ 9) |
| **F** | plein écran |
| **Échap** | revenir à la page d'accueil (avec confirmation) |

- L'effet exact des flèches dépend du **mode de pédalier** choisi (§ 6) ; à la
  livraison, c'est le mode **Maintien**.
- **+ / −** et **M** n'agissent que sur l'écran où l'on appuie et **ne sont pas
  enregistrés** : le prochain réglage envoyé depuis le téléphone les annulera.
  Pour un réglage durable, passez par le téléphone (§ 7).
- **Sur l'écran secondaire, seule F (plein écran) répond** : cet écran ne se
  pilote pas, il suit. Pour le fermer, fermez simplement sa fenêtre.

### Essai sur un ordinateur (réservé à un technicien)

Le logiciel peut tourner sur un ordinateur ordinaire, sans aucun matériel, pour
vérifier qu'il fonctionne. **Python 3** doit y être installé.

1. Ouvrez un **terminal** (la fenêtre où l'on tape des commandes) dans le dossier
   du projet, et lancez :

   ```bash
   pip install -r requirements.txt
   python server.py
   ```

   *Ce que vous devez voir* : quelques lignes d'installation, puis une ligne du
   type `Serving on http://0.0.0.0:5000`. **Laissez cette fenêtre ouverte** :
   c'est le serveur, il s'arrête si vous la fermez. Pour l'arrêter volontairement,
   revenez-y et faites **Ctrl + C**.
2. Dans un navigateur, ouvrez **http://localhost:5000**. C'est la **page
   d'accueil** : elle sert de télécommande et propose en haut deux gros boutons,
   **« Écran principal »** et **« Écran secondaire »**.
3. Cliquez sur **« Écran principal »**. *Ce que vous devez voir* : une fenêtre
   noire s'ouvre en plein écran et recouvre tout l'ordinateur. Tant que rien n'a
   été envoyé, elle affiche « Aucun texte. Envoie ton texte depuis le téléphone
   (WiFi « Prompteur ») ou par clé USB. » — c'est normal, et ce WiFi n'existe pas
   sur un ordinateur d'essai.
4. **Pour sortir de cette fenêtre : Échap, puis Échap une seconde fois** pour
   confirmer. Vous revenez à la page d'accueil. En gardant les deux côte à côte,
   ce que vous envoyez depuis l'accueil apparaît aussitôt sur l'écran.

---

## 3. Installation sur le Raspberry Pi (résumé)

> 📋 Procédure complète, du déballage au boîtier opérationnel :
> **[PROCEDURE-INSTALLATION.md](PROCEDURE-INSTALLATION.md)**. Avant toute
> intervention sur un boîtier déjà en service :
> **[SAUVEGARDE-ET-RESTAURATION.md](SAUVEGARDE-ET-RESTAURATION.md)**.

> 🔄 **Boîtier déjà en service ?** **[MISE-A-JOUR.md](MISE-A-JOUR.md)**
> ([PDF](Mise-A-Jour-Prompteur.pdf)) — la procédure pour y installer tout ce qui a
> été ajouté depuis : trois lignes à recopier, ce qui change pour le journaliste,
> et une liste de vérification. Écrite pour quelqu'un qui n'est pas informaticien.

> 🪤 **Pour qui reprend ce projet** : **[PIEGES.md](PIEGES.md)**
> ([PDF](Pieges-Prompteur.pdf)) — tout ce qui a mordu, ou failli, pendant la
> construction. La plupart de ces pièges échouent SANS message : les consigner
> évite de les redécouvrir.

> 🖥️ **Le petit écran tactile du boîtier** : **[ECRAN-TACTILE.md](ECRAN-TACTILE.md)**
> ([PDF](Ecran-Tactile-Prompteur.pdf)) — les deux montages possibles, et comment
> savoir lequel s'applique.

1. **Préparez la carte SD** avec *Raspberry Pi Imager* → « Raspberry Pi OS
   (64-bit) », la version **avec bureau**. Notez le nom d'utilisateur et le mot de
   passe choisis.
2. Sur le Pi, ouvrez un terminal et récupérez le projet :

   ```bash
   git clone https://github.com/AdrienClement38/prompteur.git
   cd prompteur
   ```

   Le dossier est alors `~/prompteur`. **Ne le déplacez pas, ne le renommez pas** :
   le démarrage automatique et les mises à jour (`git pull`) s'y réfèrent.
   *Si le Pi n'a pas d'accès internet*, vous pouvez copier le dossier par clé USB,
   sous ce même nom — mais la mise à jour par `git pull` sera alors impossible :
   il faudra recopier le dossier à chaque nouvelle version.
3. Lancez l'installation :

   ```bash
   chmod +x install/setup.sh
   ./install/setup.sh
   ```

   *Ce que vous devez voir à la fin* : un encadré

   ```
   ============================================================
    Installation terminée.
     • Serveur     : http://localhost:5000/display (écran)
     • Téléphone   : connecte-toi au WiFi « Prompteur »
                     (mot de passe : ...)
   ```

   > ⚠️ **Recopiez ce mot de passe maintenant, sur papier.** Il est tiré au hasard,
   > unique à ce boîtier, et **il n'est plus affiché nulle part après le
   > redémarrage** : sans lui, plus aucun téléphone ne peut joindre le boîtier.
   > *(Pour imposer le vôtre, relancez plutôt*
   > `WIFI_PASS="votre_mot_de_passe" ./install/setup.sh`*.)*
4. **Le mot de passe une fois noté**, redémarrez :

   ```bash
   sudo reboot
   ```

   **Après le redémarrage, le prompteur s'affiche tout seul.**

Le script installe tout, crée le WiFi du boîtier, pose l'icône **« Le Prompteur »**
sur le bureau et dans le menu des applications, et fait démarrer l'écran
automatiquement à chaque allumage.

---

## 4. Le prompteur s'ouvre et se ferme comme une application

Brancher le boîtier suffit toujours à afficher le texte : le démarrage
automatique est conservé. Mais l'écran de lecture n'est plus une impasse — on en
sort et on y revient sans redémarrer la machine.

### La page d'accueil

C'est ce que l'on ouvre sur le téléphone ou sur un ordinateur :
**http://10.42.0.1:5000**. Elle sert de télécommande (onglets **Texte**,
**Contrôle**, **Réglages**) et propose en haut **deux boutons** :

- **« Écran principal »** — *celui qu'on pilote aux pédales*. Sur un ordinateur, il
  s'ouvre **dans sa propre fenêtre**, sans barre d'adresse ni onglets ; sur un
  téléphone, c'est un onglet ordinaire.
- **« Écran secondaire »** — *régie, retour plateau, en lecture seule* (§ 8).

### Un seul écran principal à la fois

Le bouton **« Écran principal »** se grise et annonce **« déjà utilisé par un autre
appareil »** dès qu'un écran principal est ouvert **quelque part** — y compris
celui que vous venez d'ouvrir depuis cet appareil et qui est resté dans une autre
fenêtre.

**En fonctionnement normal, c'est l'écran du boîtier qui occupe la place : le
bouton grisé sur le téléphone est le signe que tout va bien.**

On peut malgré tout passer outre : l'écran affiche alors **« Un autre écran
principal est déjà en cours. »** et propose **« Ouvrir en écran secondaire »** ou
**« Prendre la main quand même »**. Ne prenez la main que si l'appareil qui lit est
réellement inaccessible : l'écran du boîtier cesserait de piloter.

Si quelqu'un prend la main, l'écran qui pilotait affiche **« Un autre appareil a
pris la main. »** Le texte reste affiché, mais les pédales de cet écran ne font
plus rien.

Si l'appareil qui tenait la place disparaît (fenêtre fermée, WiFi coupé, boîtier
redémarré), la place **se libère seule** au bout d'**une douzaine de secondes
(12 s)**.

### Revenir à l'accueil : la touche Échap

Depuis l'écran principal, **Échap** demande **« Revenir à la page d'accueil ? »**.
**Échap** une seconde fois confirme ; **n'importe quelle autre touche** annule et
l'on reste en lecture.

**Le texte, le titre et les réglages sont conservés ; la lecture, elle, repart du
début du texte.**

Sur **l'écran du boîtier** — celui qui s'ouvre tout seul, sans barre d'adresse ni
fenêtre parente — **Échap refuse de partir tant que le bandeau rouge « Liaison avec
le boîtier perdue » est affiché**, et l'explique (« Impossible de revenir à
l'accueil. »). Un écran principal ouvert depuis la page d'accueil, lui, referme
simplement sa fenêtre : l'accueil est déjà derrière.

### Afficher ou fermer l'écran du boîtier

Sur le boîtier lui-même, l'icône **« Le Prompteur »** (sur le bureau et dans le
menu des applications) relance l'écran après l'avoir fermé.

Depuis la page d'accueil, **sur n'importe quel appareil connecté au WiFi du boîtier
— téléphone compris**, la barre **« Écran du boîtier »** fait la même chose à
distance. Elle est **repliée par défaut** : appuyez sur son titre pour l'ouvrir.
*Ce que vous devez voir à l'intérieur* :

- une ligne d'état : **« Le prompteur est affiché sur l'écran du boîtier. »** ou
  **« Le prompteur est fermé : l'écran du boîtier montre le bureau. »** ;
- trois boutons : **« Afficher sur le boîtier »**, **« Fermer sur le boîtier »**,
  **« Actualiser l'état »** — des deux premiers, celui qui n'a rien à faire est
  grisé.

**« Fermer sur le boîtier » demande d'abord confirmation** : « Fermer le prompteur
sur l'écran du boîtier et revenir à son bureau ? ». Ces boutons agissent toujours
sur **l'écran du boîtier**, jamais sur l'appareil depuis lequel on les touche. Le
texte et les réglages ne sont pas perdus ; la lecture repart du début.

> Pour **éteindre réellement** la machine, c'est toujours son **bouton physique**.

---

## 5. Mettre son texte

Depuis la page d'accueil, onglet **Texte**.

### Écrire, envoyer, enregistrer

1. **Tapez ou collez** dans la zone de saisie. *Ce que vous devez voir* : un repère
   jaune **« Ce texte n'est pas encore à l'écran — appuyez sur « Envoyer à
   l'écran ». »**, qui reste tant que la zone diffère de ce qui est diffusé.
2. **« Envoyer à l'écran »** — le seul geste qui met le texte à l'antenne.
   *Ce que vous devez voir* : **« Texte envoyé à l'écran ✓ »**, et le repère jaune
   disparaît.
3. **Avant d'enregistrer, remplissez le champ « Titre ».** Sans titre, le texte est
   rangé sous **« Sans titre »** — et le prochain enregistrement sans titre
   proposera de l'écraser (« Un texte « Sans titre » existe déjà. L'écraser ? »).
4. **« Enregistrer »** range le texte dans **« Mes textes enregistrés »** sans le
   diffuser. *Ce que vous devez voir* : **« Enregistré ✓ »**, et le titre apparaît
   dans la liste.

### Importer un document ou une clé USB

**« Fichier »** — un document présent sur l'appareil que vous tenez.
Choisissez-le. *Ce que vous devez voir* : la zone de saisie se remplit et un
message confirme **« Importé : … — appuyez sur « Envoyer à l'écran » »**.

**« Clé USB »** — une clé branchée sur le boîtier. Cela se fait en **deux temps** :

1. **« Clé USB »**. *Ce que vous devez voir* : la **liste des fichiers** trouvés sur
   la clé apparaît sous les deux boutons. Si la clé n'est pas branchée sur le
   boîtier, le message **« Aucun fichier détecté sur une clé USB »** s'affiche.
2. **« Charger »**, en face du fichier voulu. *Ce que vous devez voir* : la zone de
   saisie se remplit, avec le même message **« Importé : … »**.

Dans les deux cas, rien n'est diffusé : vous relisez, vous corrigez, puis
**« Envoyer à l'écran »**.

> ⚠️ Attention, le bouton **« Charger »** de **« Mes textes enregistrés »** ne fait
> pas la même chose : celui-là **envoie directement à l'écran**, et remplace aussi
> ce que vous étiez en train d'écrire. C'est voulu — on y range des textes déjà
> relus.

Formats acceptés : **Word (.doc, .docx), PDF, LibreOffice (.odt), RTF, texte
(.txt)**, **5 Mo maximum par fichier**. Le boîtier extrait et nettoie le texte
automatiquement.

### Mettre en forme le texte

Sous la zone de saisie, une barre applique un style **au passage sélectionné** :

- **G** (gras), **I** (italique), **S** (souligné) ;
- **petit**, **Titre**, **Grand titre** ;
- **cinq couleurs**.

**Rappuyer sur le même bouton retire le style.** **« Tout effacer »** retire toute
la mise en forme — *ce que vous devez voir* : **« Mise en forme effacée »** ; le
texte, lui, reste intact.

Le gras, l'italique, le souligné, les tailles et les couleurs **se voient
directement dans la zone de saisie**. Trois choses n'y apparaissent pas et ne se
voient que sur l'écran de lecture : la **taille générale** du texte, les
**couleurs** de texte et de fond réglées dans Réglages, et les **titres**.

Une ligne commençant par **#** (jusqu'à **###**) s'affiche en **titre** sur l'écran
de lecture, sans rien avoir à sélectionner ; les **#** eux-mêmes ne s'affichent
pas. C'est aussi la forme que prennent les titres d'un document Word importé.

> **Ce qu'un import conserve, selon le format.**
>
> | | .docx / .odt | .pdf | .rtf | .txt / .md |
> |---|---|---|---|---|
> | Titres | ✅ par les styles | ✅ par la taille de la ligne | ✅ par la taille | ✅ `# ` `## ` `### ` |
> | Gras, italique | ✅ | ✅ par le **nom de la police** | ✅ | ✅ `**gras**` `*italique*` |
> | Souligné | ✅ | ✅ par la **géométrie du trait** | ✅ | ✅ `_souligné_` |
> | Couleur du texte | ✅ | ✅ | ✅ | — *(la barre, en un clic)* |
> | Plus gros / plus petit | ✅ | ✅ | ✅ | ✅ *(par les niveaux de titre)* |
> | Centré, aligné à droite | ✅ | ✅ par la **position sur la page** | ✅ | — *(la barre, en un clic)* |
> | Listes à puces | ✅ → « • » | ✅ | ✅ → « • » | ✅ `- ` → « • » |
> | Images, tableaux, polices, retraits | ❌ | ❌ | ❌ | ❌ |
>
> **Chaque format demande une méthode différente.**
>
> - **`.docx` / `.odt`** *déclarent* leur mise en forme : il suffit de suivre correctement
>   l'héritage des styles, y compris le cas où un style **annule** celui dont il hérite.
> - **`.rtf`** la déclare aussi, en clair. Le travail est de suivre l'imbrication des
>   accolades, et surtout de mettre à l'écart les tables internes — sans quoi le prompteur
>   afficherait « Times New Roman;Symbol;red255green0blue0 » avant la première phrase.
> - **`.pdf`** ne déclare **rien**. Il ne dit pas « ce mot est en gras », il dit « ce mot est
>   peint avec la police Arial-BoldMT ». Tout est donc déduit de ce que le format dit
>   vraiment : le **nom de la police**, l'**opérateur de remplissage** pour la couleur, la
>   **position de la ligne** pour le centrage. Le **souligné** est un trait dessiné sous le
>   texte : on le retrouve en rapprochant les traits horizontaux de la ligne qui passe
>   juste au-dessus, puis en recalant le résultat sur les **limites de mots** — un mot
>   n'est jamais souligné à moitié.
> - **`.txt` / `.md`** ne contiennent aucun style : c'est leur définition. Ils ont en
>   revanche des **conventions d'écriture**, les mêmes depuis quarante ans. Comme ce sont
>   des signes qui se tapent au clavier, ils marchent aussi dans la zone de saisie — la
>   télécommande les rappelle sous la barre de mise en forme.
>
> **Deux précautions sur les conventions de texte simple**, parce qu'une syntaxe qui se
> déclenche toute seule peut abîmer un texte existant : seules les **paires soignées**
> comptent (le marqueur ouvre et ferme contre un signe visible, sur une même ligne), et la
> conversion n'a lieu **qu'à l'import d'un fichier**. Un texte déjà rangé dans la
> bibliothèque est relu tel quel, avec ses marques stockées à côté : il ne peut pas changer
> d'aspect des mois plus tard. Ainsi `3 * 4 = 12`, `mon_fichier.txt`, une note isolée `*`
> ou une adresse `http://x/a_b_c` ressortent intacts.
>
> **Pourquoi pas de couleur en texte simple.** Il faudrait inventer un langage à apprendre
> pour faire moins bien que les pastilles de la télécommande, qui la posent en un clic.
> Même chose pour le centrage.
>
> Le texte d'un PDF n'est **pas** reconstruit à partir des morceaux observés : l'extraction
> existante reste maîtresse du découpage en lignes et de l'espacement, et la mise en forme
> est **reposée par-dessus**. Un test verrouille cet invariant — aux dièses de titre près,
> le texte produit est exactement celui d'avant.
>
> **Trois choix assumés, et leur raison.**
>
> - **La couleur est ramenée à la palette** (cinq couleurs, toutes lisibles sur fond noir)
>   au lieu d'être recopiée. Un bleu marine recopié fidèlement serait invisible à l'écran,
>   au moment précis où l'on compte sur le passage mis en avant. La correspondance se fait
>   sur la **teinte** : un rouge sombre devient le rouge de la palette, pas le gris qui
>   s'en approche numériquement.
> - **La taille est relative, jamais absolue.** Sur un prompteur, c'est le lecteur qui fixe
>   la taille générale selon sa distance à l'écran. Un « 8 points » recopié serait
>   illisible ; ce qui compte, c'est « plus petit que le reste » ou « bien plus gros ». La
>   référence est la taille **la plus répandue du document**, en comptant aussi les
>   passages qui n'en déclarent aucune.
> - **Titres et puces deviennent du texte** (`# `, `• `) et non un style. C'est ce qui
>   permet de les écrire au clavier, et de les retrouver intacts dans un fichier enregistré
>   puis relu des mois plus tard.
>
> L'alignement, lui, n'a pas d'écriture possible au clavier : il voyage comme une plage
> posée sur la ligne entière, et ne se voit que sur les écrans de lecture — la zone de
> saisie de la télécommande est une simple ligne de texte, sans blocs.
>
> Au-delà de **500 passages** mis en forme, l'écrêtage est **annoncé** (`marksTruncated`) :
> une limite tue passerait pour un import raté. Et un fichier qui n'est pas un document
> texte est **refusé** avec un message.

---

## 6. Lire au pied : les trois modes de pédalier

Le mode se choisit dans l'onglet **Réglages**, section **Pédales**.

| Mode | Pédale droite | Pédale gauche | Pédale centrale |
|---|---|---|---|
| **Maintien** *(recommandé)* | enfoncée = avance | enfoncée = recule | sans fonction |
| **Impulsion** | une pression lance ; une seconde pression **sur la même pédale** met en pause | idem, en arrière | sans fonction |
| **Dynamique** | accélère vers l'avant tant qu'on appuie | ralentit, puis repart en arrière de plus en plus vite | **lecture / pause** |

- **Maintien** : pédale enfoncée = ça défile, relâchée = ça s'arrête.
- **Impulsion** : le pied n'a plus à rester posé. Appuyer sur l'**autre** pédale
  change de sens.
- **Dynamique** : appuyez d'abord sur **« Dynamique »**. *Ce que vous devez voir* :
  l'explication du mode s'affiche sous les trois boutons, et un curseur
  **« Montée en vitesse (mode dynamique) »** apparaît juste en dessous, réglé sur
  **10 s** — c'est la durée d'appui continu pour atteindre la vitesse maximale.
  **La vitesse atteinte est conservée** quand on relâche : on la pose une fois au
  pied, puis on lit. La vitesse se construisant au pied, le réglage **« Vitesse de
  lecture » ne sert pas dans ce mode**.

> En **Impulsion** et en **Dynamique**, la lecture et la pause se font **à la
> pédale** : la touche **Espace** et les boutons **« Lecture »** / **« Pause »** de
> l'onglet Contrôle n'y répondent pas.

### Apprendre leurs touches aux pédales

Trois pédales sont réglables : **droite (avancer)**, **gauche (reculer)** et
**centrale (lecture/pause — mode Dynamique)**. Pour chacune :
**« Réapprendre »** → appuyez **une fois** sur la pédale → la touche s'affiche →
**« Enregistrer »**.

Sont refusées : la touche **F** (réservée au plein écran), la touche **Échap**
(elle sert à quitter) et **une touche déjà attribuée à une autre pédale** ; les
collisions avec un raccourci de l'écran sont signalées.

> ⚠️ L'apprentissage écoute le clavier de **l'appareil qui affiche la page** : il
> faut le faire depuis le boîtier, ou depuis un ordinateur portable sur lequel le
> pédalier est branché. Depuis un téléphone, aucune touche ne sera détectée.

---

## 7. Réglages disponibles (depuis le téléphone)

- **Texte** : taille, interligne, marges latérales, alignement (**Gauche** ou **Centré**).
- **Couleurs** : couleur du texte, couleur du fond.
- **Vitesse de lecture** (onglet **Contrôle**) — sans effet en mode **Dynamique** (§ 6).
- **Miroir horizontal / vertical**, pour la vitre sans tain face caméra.
  **Le miroir ne s'applique qu'à l'écran principal** : les écrans secondaires
  restent toujours à l'endroit, on les lit directement.
- **Ligne de repère** de lecture.
- **Pédales** : mode, montée en vitesse, apprentissage des touches (§ 6).

> Il n'y a **plus de choix de police** : une seule subsiste, sans empattement
> (« sans »), la seule vraiment lisible en défilement.

---

## 8. Plusieurs appareils en même temps

### Tout se met à jour tout seul

Toutes les pages ouvertes **se mettent à jour seules**, sans rechargement :

- les **réglages** modifiés sur un appareil apparaissent sur les autres ;
- le **texte à l'antenne** suit partout ;
- la **liste des textes enregistrés** s'actualise à chaque ajout ou suppression.

Une seule exception, volontaire : **un texte en cours de saisie n'est jamais
écrasé**. Si quelqu'un diffuse un autre texte pendant que vous écrivez, un message
prévient (« Le texte a changé sur le boîtier ») et votre saisie reste intacte.

### 👀 Écran secondaire (régie, retour plateau)

Un autre appareil connecté au WiFi « Prompteur » peut suivre la lecture en direct,
avec le bouton **« Écran secondaire »** de l'accueil (adresse
`http://10.42.0.1:5000/view`, rappelée dans l'onglet **Contrôle**).

- Il **suit l'écran principal** : même texte, même position.
- Il est en **lecture seule** : ses pédales et son clavier sont ignorés, **sauf F**
  qui met la page en plein écran.
- On peut en connecter **plusieurs** en même temps.
- Le défilement reste **collé** à celui de l'écran principal : sa position est
  relue une quinzaine de fois par seconde, et le mouvement est anticipé entre deux
  lectures.

### ⚡ Où brancher les pédales

**Branchez toujours les pédales sur l'appareil qui affiche l'écran principal** (le
boîtier, le plus souvent). Branchées ailleurs, elles réagiraient avec un retard
visible.

---

## 9. Utilisation au quotidien

1. **Allumez le boîtier** → l'écran affiche le prompteur automatiquement.
2. **Sur le téléphone**, connectez-vous au WiFi :
   - Réseau : **Prompteur**
   - Mot de passe : celui **noté à l'installation**, unique à ce boîtier.
3. Ouvrez le navigateur du téléphone sur **http://10.42.0.1:5000** : c'est la
   télécommande.
4. **Collez le texte**, ou importez un fichier ou une clé USB, puis
   **« Envoyer à l'écran »**.
5. Les pédales étant branchées sur l'appareil qui affiche l'écran principal, lisez.

> Sur l'écran du boîtier, la touche **i** affiche **les adresses des deux écrans de
> lecture** : « Écran principal (PC / tablette) », qui se termine par **/display**,
> et « Écran spectateur / régie », qui se termine par **/view** — à ouvrir sur un PC
> ou une tablette connectés au WiFi « Prompteur ».
> **L'adresse de la télécommande (étape 3) est la même, sans ce qui suit le port :
> http://10.42.0.1:5000.**

---

## 10. Le look « pro » face caméra (optionnel)

Pour regarder l'objectif tout en lisant : montez devant la caméra un support à
**vitre sans tain** (une vitre semi-réfléchissante, aussi appelée *beam splitter*),
l'écran du boîtier posé à plat en dessous. Activez le **miroir horizontal** (§ 7)
pour que le texte se lise à l'endroit dans le reflet.

---

## 11. Dépannage

Chaque ligne va **du geste le plus simple au plus technique**. Les commandes se
tapent dans un terminal **sur le boîtier** ;
**[SAUVEGARDE-ET-RESTAURATION.md](SAUVEGARDE-ET-RESTAURATION.md)** explique comment
les faire exécuter par quelqu'un qui n'est pas technicien.

| Problème | Que faire, dans cet ordre |
|---|---|
| **L'écran du boîtier reste noir** | 1. Sur le boîtier : double-cliquez sur l'icône **« Le Prompteur »** du bureau. 2. Depuis le téléphone : barre **« Écran du boîtier »** → **« Afficher sur le boîtier »**. 3. Si l'écran ne revient pas, faites vérifier le service : `sudo systemctl status prompteur` — la réponse doit contenir **active (running)** en vert. |
| **Le prompteur a été fermé sur le boîtier** | Icône **« Le Prompteur »** du bureau, ou barre **« Écran du boîtier »** → **« Afficher sur le boîtier »**. |
| **« déjà utilisé par un autre appareil »** sur le bouton « Écran principal » | Un écran principal est déjà ouvert. En service, c'est celui du boîtier : tout va bien. Si c'est le vôtre, **revenez à sa fenêtre**. Sinon, prenez **« Écran secondaire »**, ou **« Prendre la main quand même »** — l'écran du boîtier cesserait alors de piloter. |
| L'écran affiche **« Un autre appareil a pris la main. »** | Quelqu'un a ouvert un écran principal ailleurs : le texte reste affiché, mais les pédales de cet écran ne font plus rien. Pour reprendre : page d'accueil → **« Écran principal »** → **« Prendre la main quand même »**. |
| **Les pédales ne font rien** | 1. Vérifiez que le pédalier est branché sur l'appareil qui affiche l'**écran principal** (§ 8). 2. Onglet **Réglages** → **Pédales** → réapprenez les touches (§ 6). 3. Vérifiez la programmation du pédalier lui-même. |
| Bandeau rouge **« Liaison avec le boîtier perdue »** | Le texte affiché reste lisible et les pédales fonctionnent. 1. Reconnectez l'appareil au WiFi **« Prompteur »**. 2. Si cela ne suffit pas : `sudo systemctl restart prompteur`. |
| Message **« Document trop volumineux pour le prompteur… Découpez-le en plusieurs séquences »** | Le document dépasse **300 000 caractères** ou **20 000 lignes** : découpez-le en plusieurs textes, enregistrés séparément (§ 5). |
| **Le WiFi « Prompteur » n'apparaît pas** | 1. Relancez la recherche de réseaux sur le téléphone, plus près du boîtier. 2. S'il reste absent : `sudo nmcli connection up Prompteur` sur le boîtier — le réseau réapparaît en quelques secondes. |
| **Rien de tout cela n'a marché** | Redémarrez le serveur : `sudo systemctl restart prompteur`. Pour comprendre ce qui se passe, lisez le journal du programme : `journalctl -u prompteur -f`. |

---

## 12. Ce qui protège le boîtier

- Le boîtier n'est joignable **que depuis son propre WiFi**, protégé par un mot de
  passe **unique à chaque boîtier**.
- **Rien ne sort du boîtier** : aucune connexion internet n'est utilisée, ni pour
  lire, ni pour envoyer un texte.
- Les textes et les réglages sont **conservés sur le boîtier** — voir
  **[SAUVEGARDE-ET-RESTAURATION.md](SAUVEGARDE-ET-RESTAURATION.md)** pour les
  sauvegarder et pour revenir en arrière si quelque chose se passe mal.
