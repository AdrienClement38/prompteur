# Mise en route du Prompteur — pas à pas, sans rien y connaître

> **📦 Vous venez de recevoir les cartons. Voici ce qui vous attend.**
>
> Vous allez transformer un petit ordinateur gros comme un paquet de cartes (le
> « Raspberry Pi ») en **boîtier prompteur** : un appareil qui affiche un texte
> défilant sur un écran, piloté au pied avec des pédales, et réglé depuis un
> téléphone.
>
> - **Durée : comptez 1 heure à 1 h 30**, dont **une longue attente où il n'y a
>   rien à faire** (la mise à jour de l'appareil peut occuper à elle seule une
>   demi-heure). Ce n'est pas une heure de travail : c'est une heure de présence.
>   *(Le document technique `PROCEDURE-INSTALLATION.md` annonce 30 à 45 minutes :
>   c'est la durée pour une personne habituée, sans les vérifications détaillées
>   ni la répétition générale décrites ici.)*
> - **C'est une seule fois.** Une fois terminé, le boîtier se met en route tout
>   seul : on branche le courant, on attend une minute, c'est prêt.
> - **Le journaliste n'aura JAMAIS à refaire ce qui suit.** Lui, il branchera
>   l'appareil et se servira de son téléphone. Rien d'autre.
> - Vous n'avez **pas besoin de savoir programmer**. Vous allez recopier quelques
>   lignes de texte, exactement comme on recopie un numéro de téléphone.
> - **Vous pouvez vous interrompre** et reprendre plus tard : les moments où
>   c'est sans danger sont indiqués au fur et à mesure.
>
> **Le conseil le plus important de tout ce document :** ne faites pas cette
> installation la veille au soir d'un tournage. Faites-la un jour tranquille, où
> vous aurez le temps de tout tester deux fois.

> **🖨️ Ce document est fait pour être imprimé et suivi papier à la main.**
> Les renvois d'une partie à l'autre nomment toujours la partie en toutes lettres
> (« voir l'étape F »), pour rester utilisables sur papier. Le sommaire ci-dessous
> comporte une colonne vide : après impression, écrivez-y au stylo le numéro de
> page correspondant.

---

## Sommaire

| Repère | Partie | Page |
|---|---|---|
| **1** | Avant de commencer — ce qu'il faut avoir sous la main | ....... |
| **2** | Les trois informations à choisir avant de commencer | ....... |
| **A** | Préparer la carte mémoire (à sauter si elle est déjà prête) | ....... |
| **B** | Brancher le boîtier | ....... |
| **C** | Le premier démarrage | ....... |
| **D** | Ouvrir la fenêtre noire | ....... |
| **E** | Les trois réglages dans le menu bleu | ....... |
| **F** | Les lignes à recopier, une par une | ....... |
| **G** | Le redémarrage qui révèle tout | ....... |
| **G bis** | Sortir de l'écran prompteur, et y revenir | ....... |
| **G ter** | Éteindre le boîtier proprement | ....... |
| **H** | Connecter le téléphone | ....... |
| **I** | Le pédalier | ....... |
| **J** | Préparer la répétition générale | ....... |
| **K** | Checklist finale : la répétition générale | ....... |
| **L** | La roue de secours : la deuxième carte mémoire | ....... |
| **M** | Si ça ne marche pas | ....... |
| **N** | Mettre à jour ou réinstaller plus tard | ....... |
| **O** | Quand tout marche : à transmettre au journaliste | ....... |

---

## 1. Avant de commencer — ce qu'il faut avoir sous la main

Rassemblez **tout** ceci sur une table dégagée **avant** de brancher quoi que ce
soit. Rien n'est plus pénible que de partir chercher un câble au milieu de
l'installation.

**Le matériel commandé :**

- [ ] Le Raspberry Pi 5 et son boîtier (le petit ordinateur)
- [ ] Son alimentation USB-C (le chargeur fourni dans le kit — **utilisez celui-là**, pas un chargeur de téléphone pris au hasard)
- [ ] La carte micro-SD du kit (la petite carte mémoire, plus petite qu'un timbre)
- [ ] Le câble micro-HDMI (le câble qui relie le boîtier à l'écran)
- [ ] L'écran 7 pouces, **et son alimentation à lui s'il en a une**
- [ ] Le pédalier USB

**À ajouter, indispensable, et que vous devez trouver vous-même :**

- [ ] **Un clavier USB filaire** (avec un fil, pas en Bluetooth : le Bluetooth complique inutilement le premier démarrage)
- [ ] **Une souris USB filaire** (même remarque)
- [ ] **Un câble Ethernet** (le gros câble réseau, qui ressemble à un vieux câble de téléphone en plus large) **et une prise libre sur votre box Internet**
- [ ] Une multiprise
- [ ] **Une feuille de papier et un stylo** — vous allez noter des choses, et ce n'est pas facultatif
- [ ] Votre téléphone (celui qui servira de télécommande, ou le vôtre pour tester)
- [ ] **Une petite clé USB ordinaire**, vide ou presque : elle servira aux tests, et peut aussi vous éviter de recopier des lignes à la main (voir l'étape D)

> **📌 Le clavier et la souris ne repartiront PAS dans un tiroir.**
> On croit souvent qu'ils ne servent que le jour de l'installation. C'est faux :
> ce sont les deux seuls outils de dépannage du boîtier sur un tournage (voir la
> partie « Si ça ne marche pas »). **Ils resteront dans la sacoche du matériel.**

> **⚠️ Pourquoi le câble Ethernet plutôt que le WiFi de la maison ?**
> Pendant l'installation, le boîtier transforme sa propre antenne WiFi en réseau
> à lui. Si vous étiez connecté par le WiFi de la maison à ce moment-là, la
> connexion Internet se couperait **au milieu de l'installation** et tout
> s'arrêterait. Avec un câble Ethernet, cela n'arrive pas.
>
> **Si vous n'avez vraiment aucun câble Ethernet**, voici exactement comment
> faire : connectez le boîtier au WiFi de la maison au premier démarrage, faites
> normalement toutes les lignes de l'étape F **sauf la dernière (F7)**, puis
> lancez cette dernière ligne en sachant que **la connexion Internet du boîtier
> va se couper en cours de route** — c'est prévu et sans gravité, tout ce qu'il
> fallait télécharger l'a déjà été. Si la ligne s'arrête sur un message
> d'erreur : reconnectez le boîtier au WiFi de la maison (icône réseau en haut à
> droite du bureau), puis **relancez simplement cette même ligne F7**. On peut la
> relancer autant de fois qu'on veut, sans rien casser.

> **ℹ️ Internet est-il nécessaire ?**
> **Oui, mais seulement aujourd'hui**, pendant l'installation, pour télécharger le
> logiciel. Ensuite le boîtier fonctionne **totalement sans Internet**, pour
> toujours : sur un tournage, aucune connexion n'est nécessaire.

---

## 2. Les trois informations à choisir AVANT de commencer

Vous allez devoir choisir trois choses. **Les deux premières vous seront
demandées par l'appareil.** **La troisième, c'est vous qui l'imposerez**, en
l'écrivant dans la dernière ligne de l'étape F : aucun écran ne vous la
réclamera, ne l'attendez pas.

**Décidez-les maintenant, sur papier**, avant même de brancher : les inventer
dans la précipitation, devant un écran qui attend, est la principale cause
d'ennuis.

> **✍️ À NOTER SUR PAPIER — recopiez ce tableau et remplissez-le au stylo.**
> Cette feuille devra ensuite être remise au journaliste et rangée dans la
> sacoche du matériel.

| # | Ce que c'est | Qui vous la demande ? | Règles à respecter | Votre choix (à écrire) |
|---|---|---|---|---|
| 1 | **Nom d'utilisateur du boîtier**<br>(le nom du « propriétaire » de l'appareil) | L'appareil, à l'étape A ou C | Que des lettres minuscules, sans accent, sans espace.<br>Exemple : `prompteur` | ..................... |
| 2 | **Mot de passe du boîtier**<br>(redemandé chaque fois que l'on tape une ligne importante) | L'appareil, à l'étape A ou C | 8 caractères minimum, lettres sans accent et chiffres.<br>**Aucun symbole, aucun espace, aucun accent.**<br>Exemple : `boitier2026` | ..................... |
| 3 | **Mot de passe du WiFi du boîtier**<br>(celui que le téléphone tapera pour se connecter) | **Personne : c'est VOUS qui l'imposez**, dans la ligne F7 | **8 caractères minimum** (une douzaine, c'est parfait), lettres sans accent et chiffres **uniquement**.<br>Aucun espace, aucun symbole.<br>Exemple : `prompteur2026` | ..................... |

> **⚠️ PIÈGE — le mot de passe WiFi que l'on ne voit qu'une seule fois.**
> Si vous ne choisissez pas vous-même le mot de passe WiFi (information n° 3), le
> boîtier en invente un au hasard, de 16 caractères incompréhensibles, et il ne
> l'affiche **qu'une seule fois**, à la toute fin. Une fenêtre fermée trop vite,
> et le boîtier devient inutilisable depuis le téléphone.
> **La parade est simple : vous imposerez le vôtre**, comme expliqué à l'étape F.
> C'est la méthode recommandée dans tout ce document.

> **⚠️ PIÈGE — les symboles interdits dans le mot de passe WiFi.**
> Un mot de passe WiFi **de moins de 8 caractères** fait échouer l'installation
> **en plein milieu**. Et comme ce mot de passe sera écrit **entre guillemets, à
> l'intérieur d'une ligne à taper**, les symboles et les espaces y sèment la
> pagaille. Restez sur des lettres et des chiffres, comme dans l'exemple. Ce
> n'est pas moins sûr : douze lettres et chiffres, c'est largement suffisant pour
> un réseau qui ne va jamais sur Internet.

Deux informations complémentaires à noter aussi, sur la même feuille :

- Le **nom du réseau WiFi du boîtier** est toujours le même : **`Prompteur`**, avec un P majuscule. Vous n'avez pas à le choisir.
- Les **trois adresses** à recopier dans le navigateur d'un téléphone ou d'un ordinateur :

| À quoi ça sert | Adresse exacte à taper |
|---|---|
| **La télécommande** (sur le téléphone du journaliste) | `http://10.42.0.1:5000` |
| L'écran principal, celui qui obéit aux pédales | `http://10.42.0.1:5000/display` |
| Un écran de régie, qui suit sans piloter | `http://10.42.0.1:5000/view` |

---

## Étape A — Préparer la carte mémoire (à sauter si elle est déjà prête)

> **❓ Comment savoir si vous pouvez sauter cette étape ?**
> Regardez la description de votre kit ou l'emballage de la carte micro-SD. Si
> elle est annoncée comme **« pré-installée »**, « pre-loaded » ou « Raspberry Pi
> OS installé », **passez directement à l'étape B** : vous n'avez alors besoin
> d'aucun ordinateur.
> Dans le doute : essayez d'abord l'étape B. Si l'écran reste noir ou affiche un
> message d'erreur au démarrage, revenez ici.

Cette étape se fait **sur un ordinateur** (Windows ou Mac), pas sur le boîtier.

**A1 — Installer le programme qui prépare la carte**

- [ ] **A1a.** Sur l'ordinateur, ouvrez le site `raspberrypi.com/software`.
- [ ] **A1b.** Cliquez sur le bouton de téléchargement **qui correspond à votre ordinateur** : « for Windows » si vous êtes sur PC, « for macOS » si vous êtes sur Mac. (Ne prenez pas la version Linux.)
- [ ] **A1c.** Le fichier arrive dans votre dossier **Téléchargements**. Ouvrez ce dossier et **double-cliquez** sur le fichier qui vient d'arriver (son nom commence par `imager`).
- [ ] **A1d.** Windows ou le Mac affichera un **avertissement de sécurité** (« Voulez-vous autoriser cette application… », « Ouvrir ? »). C'est normal pour tout programme fraîchement téléchargé : **acceptez**, puis laissez l'installation aller au bout (bouton **Install** / **Installer**, puis **Terminer**).

**✅ Ce que vous devez voir :** un programme nommé **Raspberry Pi Imager** est
maintenant installé sur votre ordinateur.

**A2 à A9 — Écrire le système sur la carte**

- [ ] **A2.** Insérez la carte micro-SD dans l'ordinateur (avec l'adaptateur fourni si votre ordinateur n'a qu'une grande fente).
- [ ] **A3.** Ouvrez Raspberry Pi Imager. **✅ Ce que vous devez voir :** une fenêtre avec **trois gros boutons**.
- [ ] **A4.** **CHOISIR L'APPAREIL** → dans la liste, prenez **Raspberry Pi 5**.
- [ ] **A5.** **CHOISIR LE SYSTÈME D'EXPLOITATION** → prenez **Raspberry Pi OS (64-bit)**, la version **avec bureau** (celle qui montre un fond d'écran, pas la version « Lite »).
- [ ] **A6.** **CHOISIR LE STOCKAGE** → sélectionnez la carte micro-SD. Vérifiez deux fois : tout ce qu'elle contient sera effacé.
- [ ] **A7a.** Cliquez sur **SUIVANT**. **✅ Ce que vous devez voir :** une question apparaît au sujet des **réglages personnalisés**.
- [ ] **A7b.** Dans cette question, cliquez sur **MODIFIER LES RÉGLAGES**. **✅ Ce que vous devez voir :** une fenêtre avec plusieurs onglets et des cases à remplir.
- [ ] **A8.** Remplissez :
  - **nom d'hôte** (le nom de l'appareil sur le réseau) : `prompteur`
  - **nom d'utilisateur** et **mot de passe** : ceux du tableau, informations n° 1 et n° 2
  - **langue, fuseau horaire, clavier** : France / français
  - onglet **Services** : cochez **« Activer SSH »**. Cette case permettra un jour à un dépanneur informatique d'aider à distance depuis un autre ordinateur ; **elle ne vous servira pas aujourd'hui**, et elle n'ouvre rien sur votre propre ordinateur. *(Si vous ne trouvez pas cet onglet dans votre version du programme, passez : ce n'est pas indispensable.)*
- [ ] **A9a.** Cliquez sur **ENREGISTRER**.
- [ ] **A9b.** Répondez **OUI** à la question qui demande s'il faut **appliquer les réglages personnalisés**.
- [ ] **A9c.** Répondez **OUI** au second avertissement, celui qui prévient que **toutes les données de la carte vont être effacées**. *(Oui, il y a bien deux questions à la suite : c'est normal, ne vous arrêtez pas à la première.)*
- [ ] **A9d.** Attendez sans toucher à rien. Le programme écrit la carte, puis vérifie ce qu'il a écrit.

**✅ Ce que vous devez voir :** au bout de quelques minutes, le message
**« Écriture réussie »**. Le programme propose alors de retirer la carte : vous
pouvez la sortir de l'ordinateur.

> **❌ Ça ne marche pas ?**
> - **La carte n'apparaît pas dans la liste « CHOISIR LE STOCKAGE » :** ressortez-la
>   et réinsérez-la à fond (un petit « clic »), essayez **l'autre fente** ou un
>   **autre port USB**, et vérifiez que vous utilisez bien l'adaptateur fourni avec
>   la carte. Fermez puis rouvrez le programme après avoir réinséré la carte.
> - **Un message d'erreur pendant l'écriture, ou « vérification échouée » :**
>   relancez l'opération une fois depuis le début. Si l'erreur revient, la carte
>   est probablement défectueuse : prenez-en une autre (micro-SD de 16 Go ou plus,
>   d'une marque connue).
> - **Le programme réclame le mot de passe d'administrateur de votre ordinateur :**
>   c'est normal, il a besoin d'écrire directement sur la carte. Saisissez celui de
>   votre session habituelle.

---

## Étape B — Brancher le boîtier

> **⚠️ La règle d'or : l'alimentation USB-C se branche EN DERNIER.**
> Le Raspberry Pi 5 **démarre tout seul dès que le courant arrive** : il n'y a
> rien à allumer. Il faut donc que tout le reste soit déjà en place.
>
> Il possède aussi **un petit bouton rond, juste à côté de la prise USB-C**.
> Ce bouton ne sert **pas** à l'allumer aujourd'hui (le courant suffit) : c'est
> lui qui servira **plus tard à l'éteindre proprement**, comme expliqué dans la
> partie « Éteindre le boîtier proprement ». Selon le boîtier plastique du kit,
> il est accessible directement, par un petit trou, ou par un bouton reporté sur
> le dessus. **Repérez-le dès maintenant** : vous en aurez besoin ce soir.

Faites-le dans **cet ordre exact** :

- [ ] **B1.** Vérifiez que **rien n'est branché au courant** pour l'instant.
- [ ] **B2.** Insérez la **carte micro-SD** dans la fente prévue sous le Raspberry Pi (elle ne rentre que dans un sens, sans forcer).
- [ ] **B3.** Branchez le **câble micro-HDMI** côté boîtier. **⚠️ Attention, c'est le piège le plus fréquent :** le Raspberry Pi 5 a **deux** petits ports HDMI côte à côte. Il faut **celui qui est le plus proche de la prise d'alimentation USB-C**. Sur le mauvais port, l'écran reste désespérément noir alors que tout fonctionne parfaitement.
- [ ] **B4.** Branchez l'autre bout du câble sur l'**écran 7 pouces**.
- [ ] **B5.** Branchez le **clavier** et la **souris** sur deux ports USB du boîtier.
- [ ] **B6.** Branchez le **câble Ethernet** entre le boîtier et votre box Internet.
- [ ] **B7.** Vous pouvez brancher le **pédalier** dès maintenant sur un port USB, ou le garder pour plus tard : c'est sans importance.
- [ ] **B8.** **Allumez d'abord l'écran** (branchez son alimentation à lui s'il en a une, et vérifiez qu'il est bien réglé sur l'entrée « HDMI » s'il possède un sélecteur).
- [ ] **B9.** **Enfin**, branchez l'alimentation USB-C du Raspberry Pi.

**✅ Ce que vous devez voir :** si le boîtier plastique laisse voir le petit
voyant du Raspberry Pi, celui-ci s'allume — sa couleur dépend du modèle, et
beaucoup de boîtiers le masquent complètement, **ne vous inquiétez donc pas si
vous ne voyez aucune lumière**. **La vraie preuve, c'est l'image :** au bout de
quelques dizaines de secondes, une image apparaît sur l'écran (framboise, texte
qui défile, puis un bureau avec un fond d'écran).

> **⚠️ Écran resté noir ?** Ne débranchez pas en boucle. Dans l'ordre :
> (1) vérifiez que vous êtes bien sur **le port HDMI le plus proche de
> l'alimentation** ; (2) éteignez tout, rallumez **l'écran d'abord**, le boîtier
> ensuite (le boîtier lit les caractéristiques de l'écran au démarrage : un écran
> allumé après lui peut rester noir) ; (3) si vous en avez la possibilité, testez
> une fois sur une **télévision ordinaire** — cela vous dira tout de suite si le
> problème vient du petit écran ou du boîtier.

---

## Étape C — Le premier démarrage

> **🔀 Commencez par lire cet aiguillage : deux cas très différents.**
>
> **Cas 1 — vous venez de faire l'étape A** (vous avez rempli « MODIFIER LES
> RÉGLAGES » dans Raspberry Pi Imager) : **aucun assistant ne s'affichera.**
> Le boîtier démarre **directement sur un bureau avec un fond d'écran**, sans
> poser la moindre question. **C'est normal et c'est bon signe** : vos réponses
> sont déjà enregistrées sur la carte. Ne cherchez pas un écran qui n'existe pas,
> **passez directement au point C6** (vérification d'Internet).
>
> **Cas 2 — votre carte micro-SD était déjà prête à l'achat** (vous avez sauté
> l'étape A) : un **assistant de bienvenue** s'ouvre et pose des questions.
> C'est votre seule occasion de choisir la langue et de créer vos informations
> n° 1 et n° 2. **Suivez les points C1 à C5**, puis C6.

### Uniquement dans le cas 2 : l'assistant de bienvenue

> **⚠️ PIÈGE MAJEUR — le clavier qui écrit n'importe quoi.**
> Tant que vous n'avez pas choisi **France**, le clavier répond « à l'anglaise » :
> la touche **A** écrit **Q**, la touche **Z** écrit **W**, la touche **M** écrit
> un point-virgule, et les chiffres exigent la touche Majuscule.
> Un mot de passe tapé dans ces conditions devient **introuvable** ensuite.
> **Donc : choisissez France TOUT AU DÉBUT, avant de taper le moindre mot de passe.**

- [ ] **C1.** Premier écran : choisissez **France** partout — pays, langue, et clavier français.
- [ ] **C2.** Écran suivant : créez l'utilisateur avec **l'information n° 1** (nom) et **l'information n° 2** (mot de passe) de votre feuille.
  **Astuce indispensable :** cet écran propose une case du genre « masquer les caractères ». **Décochez-la**, pour VOIR ce que vous tapez réellement et vérifier que le clavier écrit bien ce que vous croyez.
- [ ] **C3.** Écran réseau : comme le câble Ethernet est branché, il n'y a normalement rien à faire. Si l'assistant demande un WiFi, vous pouvez passer.
- [ ] **C4.** Écran des mises à jour : acceptez si c'est proposé (cela peut prendre plusieurs minutes), ou passez, ce n'est pas bloquant.
- [ ] **C5.** Terminez l'assistant. Si un redémarrage est proposé, acceptez.

### Dans les deux cas : vérifier qu'Internet fonctionne

- [ ] **C6.** Sur le bureau, ouvrez le navigateur Internet (l'icône en forme de globe, dans la barre en haut à gauche) et affichez n'importe quelle page.

**✅ Ce que vous devez voir :** une vraie page Internet s'affiche. En haut à
droite de l'écran, l'icône du réseau montre les **deux petites flèches** de la
prise Ethernet, et non un point d'exclamation.

> **❌ Pas d'Internet ?** Vérifiez que le câble Ethernet est bien enfoncé des deux
> côtés (un petit « clic ») et que la prise choisie sur la box est active.
> N'allez pas plus loin tant que la page ne s'ouvre pas : les étapes suivantes
> ont besoin d'Internet.

---

## Étape D — Ouvrir la fenêtre noire

Les étapes qui suivent se font dans **le terminal** : une fenêtre noire dans
laquelle on tape du texte, ligne par ligne, et où l'appareil répond par du texte.
C'est simplement une autre façon de lui donner des ordres, sans souris. Vous
n'avez rien à comprendre de ce qui s'y affichera.

- [ ] **D1.** Dans la barre en haut de l'écran, cliquez sur **l'icône noire qui ressemble à `>_`**. (Si vous ne la trouvez pas, appuyez sur les trois touches **Ctrl + Alt + T** en même temps.)

**✅ Ce que vous devez voir :** une fenêtre noire s'ouvre, avec une ligne de texte
coloré qui se termine par le signe **`$`** et un petit rectangle qui clignote.
C'est là que vous allez taper.

> **⌨️ Trois pièges de clavier, à connaître avant de taper.**
> Sur un clavier français :
> - le **point** (`.`) et la **barre oblique** (`/`) sont sur la même zone en bas
>   à droite : la barre oblique demande la touche **Majuscule** ;
> - le **tiret** (`-`) est la touche à droite du `0` de la rangée du haut, **sans**
>   Majuscule ;
> - le **guillemet droit** (`"`) est sur la touche du **chiffre 3**, avec la touche
>   **Majuscule**. C'est bien ce guillemet-là qu'il faut, **jamais** les guillemets
>   « français » ni les guillemets courbes d'un traitement de texte.
>
> **Pour corriger sans tout retaper :** les flèches **gauche** et **droite**
> déplacent le curseur dans la ligne, la touche **Retour arrière** efface le
> caractère qui précède. Et si la ligne est vraiment ratée, **Ctrl + C** l'annule
> proprement : le signe `$` revient, et vous recommencez la ligne.

> **💡 Facultatif — l'astuce de la clé USB, pour ne rien recopier à la main.**
> Avant de venir, vous pouvez taper les lignes de l'étape F dans un simple
> fichier texte sur votre ordinateur, et copier ce fichier sur une clé USB.
> Branchez ensuite la clé sur le boîtier, ouvrez le fichier, **copiez** une ligne
> (Ctrl + C) et **collez-la dans la fenêtre noire avec `Ctrl + Maj + V`**
> (attention : `Ctrl + V` tout seul ne fait rien dans cette fenêtre).
> **Dans tous les cas, la dernière ligne (F7) devra être retapée avec VOTRE mot
> de passe WiFi** : ne collez jamais l'exemple tel quel.

---

## Étape E — Les trois réglages dans le menu bleu

Trois réglages doivent être changés pour que le prompteur s'affiche tout seul au
démarrage, et pour que l'écran ne s'endorme jamais. Ils se font dans un menu bleu
et gris, un peu vieillot.

Cette ligne ouvre le menu de réglages du Raspberry Pi. Tapez-la dans la fenêtre
noire, puis appuyez sur **Entrée** :

```
sudo raspi-config
```

> **⚠️ PIÈGE — « il me demande un mot de passe et rien ne s'affiche ! »**
> Le boîtier va vous demander votre mot de passe (l'information n° 2). Pendant
> que vous le tapez, **rien ne bouge à l'écran** : ni étoiles, ni points, ni
> curseur qui avance. **C'est normal, c'est fait exprès.** Tapez à l'aveugle,
> puis appuyez sur Entrée.

> **🧭 Se déplacer dans ce menu — la souris ne sert à rien ici.**
> - **Flèches haut/bas** : se déplacer dans la liste.
> - **Entrée** : valider la ligne sur laquelle on se trouve.
> - **Tab** : descendre sur les boutons du bas (`<Select>`, `<Back>`, `<Finish>`).
> - **Pour revenir en arrière** si vous vous êtes perdu dans un sous-menu :
>   appuyez sur **Tab** jusqu'à `<Back>` puis sur **Entrée** (la touche **Échap**
>   fait souvent la même chose). Vous ne pouvez rien casser en vous promenant
>   dans ce menu : seuls les choix validés comptent.

**Réglage n° 1 — le démarrage automatique (le plus important des trois)**

- [ ] **E1.** Avec les flèches, allez sur **System Options** → Entrée.

**Regardez maintenant la liste : selon la version de votre boîtier, ce réglage se
présente de DEUX façons différentes.** Les deux mènent exactement au même résultat.
Repérez celle que vous avez, puis suivez uniquement son cas.

> **🔀 Quel cas est le vôtre ?**
> - Vous voyez **une seule ligne** qui contient à la fois « Boot » et « Auto Login »
>   (par exemple `Boot / Auto Login`) → **cas 1**.
> - Vous voyez **deux lignes séparées**, l'une **Boot**, l'autre **Auto Login**
>   → **cas 2** (c'est la présentation des versions récentes).

***Cas 1 — une seule ligne « Boot / Auto Login »***

- [ ] **E2.** Allez sur **Boot / Auto Login** → Entrée.
- [ ] **E3.** Choisissez **Desktop Autologin** → Entrée.

***Cas 2 — deux lignes séparées, « Boot » et « Auto Login »***

**Il faut faire les deux**, l'une après l'autre. L'une seule ne suffit pas.

- [ ] **E2.** Allez sur **Boot** → Entrée, puis choisissez **Desktop** → Entrée.
      *(Vous revenez alors dans la liste System Options.)*
- [ ] **E3.** Allez sur **Auto Login** → Entrée, puis activez la connexion
      automatique **au bureau** : selon la version, cela s'appelle
      **Desktop Auto Login**, ou bien on vous pose une question à laquelle il faut
      répondre **`<Yes>`** (Oui) → Entrée.

**✅ Ce que vous devez voir après E3, dans les deux cas :** l'écran revient tout seul
au **grand menu bleu** de départ. Aucun message de confirmation n'apparaît : ce
retour au menu principal **est** la confirmation.

> **⚠️ PIÈGE — le mot qui compte est « Desktop ».** Partout dans ce réglage, il
> existe un équivalent « **Console** » (« Console Autologin », ou « Console » dans
> la ligne *Boot*). Si vous le prenez, le boîtier démarrera sur un écran noir de
> texte et le prompteur ne s'affichera **jamais**.
> Ne vous fiez pas non plus aux numéros de menu (S5, S6, B4, A6…) : ils changent
> d'une version à l'autre. Fiez-vous aux **mots**.

> **🆘 Dans le cas 2, si vous n'avez fait que « Boot → Desktop » et oublié
> « Auto Login » :** au redémarrage, le boîtier s'arrêtera sur un écran de
> connexion réclamant votre mot de passe, et le prompteur ne partira pas tout seul.
> Ce n'est pas grave : connectez-vous une fois à la main, puis refaites
> `sudo raspi-config` et complétez la ligne **Auto Login**.

**Réglage n° 2 — le mode d'affichage**

- [ ] **E4.** Revenu au menu principal, allez sur **Advanced Options** → Entrée.
- [ ] **E5.** Allez sur **Wayland** → Entrée.
- [ ] **E6.** Trois choix apparaissent (X11, Wayfire, Labwc). Choisissez **X11**, le premier, et rien d'autre → Entrée.

**✅ Ce que vous devez voir après E6 :** de nouveau le **grand menu bleu**.

> **❌ Vous ne trouvez ni « Wayland » ni « X11 » dans Advanced Options ?**
> **Ce n'est pas grave, et ce n'est pas une erreur de votre part** : certaines
> versions du système ne proposent plus ce choix. **Sautez ce réglage n° 2** et
> passez au réglage n° 3. Le réglage vraiment indispensable est le n° 1
> (Desktop Autologin) ; le prompteur sait aussi démarrer sans celui-ci, et vous
> le vérifierez de toute façon à l'étape G.
> *(Si vous voulez tenter votre chance : sortez du menu par `<Finish>`, faites la
> ligne F1 puis la ligne F2 de l'étape F — la mise à jour —, redémarrez, puis
> rouvrez `sudo raspi-config` et regardez à nouveau. Si l'entrée reste absente,
> continuez sans elle.)*

**Réglage n° 3 — empêcher l'écran de s'endormir**

- [ ] **E7.** Revenu au menu principal, allez sur **Display Options** → Entrée.
- [ ] **E8.** Allez sur **Screen Blanking** (l'extinction automatique de l'écran) → Entrée.
- [ ] **E9.** À la question **« Would you like to enable screen blanking? »** (voulez-vous que l'écran s'éteigne tout seul ?), répondez **NON** (`<No>`).

**✅ Ce que vous devez voir :** un petit message confirme que l'extinction
automatique est désactivée, puis vous revenez au grand menu bleu.
*(Si vous ne trouvez pas cette ligne, passez : le programme d'installation prend
aussi cette précaution de son côté. Vous vérifierez le résultat par le test des
15 minutes, dans la checklist finale.)*

**Sortir du menu**

- [ ] **E10.** Avec la touche **Tab**, descendez sur **`<Finish>`** et validez avec Entrée.
- [ ] **E11.** **Si** la question **« Would you like to reboot now? »** (voulez-vous redémarrer maintenant ?) apparaît : répondez **NON** (`<No>`). **Si elle n'apparaît pas, c'est normal aussi** : continuez simplement.

**✅ Ce que vous devez voir :** vous retrouvez la fenêtre noire avec le signe `$`.
La vraie preuve que ces réglages ont fonctionné viendra à l'étape G.

---

## Étape F — Les lignes à recopier, une par une

Voici le cœur de l'installation : **sept lignes, une par une, dans cet ordre**,
en appuyant sur **Entrée** après chacune.

**Cochez chaque case dès que la ligne avec le signe `$` est revenue** : c'est
votre seul repère si vous êtes interrompu. Ne tapez jamais la ligne suivante
avant que le `$` ne soit revenu.

> **⏸️ Si vous devez vous interrompre.**
> Vous pouvez vous arrêter **entre deux lignes**, une fois le `$` revenu :
> éteignez alors proprement le boîtier (voir la partie « Éteindre le boîtier
> proprement »), et reprenez plus tard à la ligne suivante — il suffira de rouvrir
> la fenêtre noire et, à partir de la ligne F5, de retaper d'abord `cd prompteur`.
> **En revanche, ne coupez JAMAIS le courant pendant qu'une ligne travaille**,
> en particulier F2 et F7 : cela peut abîmer la carte mémoire. Si cela arrive
> malgré tout, rallumez et **relancez la même ligne depuis le début** : c'est sans
> danger.

> **🗣️ Les messages affichés vous tutoient et sont souvent en anglais.**
> C'est l'appareil qui raconte ce qu'il fait ; il ne s'adresse pas vraiment à
> vous. **Ne suivez que ce document**, pas les phrases qui défilent à l'écran.

> **🛑 LE PIÈGE LE PLUS GRAVE DE TOUTE L'INSTALLATION — le mot `sudo`.**
> Certaines lignes commencent par le mot `sudo`, d'autres non. **Recopiez-les
> exactement telles qu'elles sont écrites** : n'ajoutez jamais `sudo` devant une
> ligne qui n'en a pas. Les lignes **F4, F5, F6 et F7 ne prennent pas `sudo`**.
> L'erreur est particulièrement tentante — et particulièrement sournoise — sur la
> **ligne F7** : avec un `sudo` devant, l'installation **semble parfaitement
> réussir**, le beau cadre final s'affiche, mais après le redémarrage le prompteur
> ne s'affichera **jamais** et l'écran restera sur le bureau. *(La raison, si elle
> vous intéresse : le programme inscrit le démarrage automatique dans le dossier
> de la personne qui le lance ; avec `sudo`, il l'inscrit dans le dossier de
> l'administrateur, où personne n'ira le chercher.)*
> **Si l'erreur a été faite :** rien n'est cassé. Retapez simplement la ligne F7
> correctement, **sans `sudo`**, puis faites le redémarrage de l'étape G.

**F1 —** met à jour la liste des logiciels disponibles. *(Rapide : quelques dizaines de secondes.)*

- [ ] **F1**

```
sudo apt update
```

*✅ Des lignes défilent, puis le signe `$` revient.*

**F2 —** installe réellement ces mises à jour. **C'est la plus longue de toute la procédure.**

- [ ] **F2**

```
sudo apt full-upgrade -y
```

*✅ **Comptez de 10 à 40 minutes**, selon votre connexion Internet et l'âge de la
carte. C'est normal, ne touchez à rien, **même si l'affichage reste immobile une
ou deux minutes** sur un pourcentage. Le `$` finit toujours par revenir.*

> **⚠️ PIÈGE — un écran bleu ou violet occupe toute la fenêtre, avec une question en anglais.**
> Cela arrive parfois pendant cette mise à jour (question sur un fichier de
> configuration ou sur des programmes à redémarrer). **La souris ne sert à rien**
> dans cet écran. Déplacez-vous avec la touche **Tab**, laissez le bouton déjà
> mis en évidence (c'est le bon choix par défaut) et appuyez sur **Entrée**.
> La mise à jour reprend toute seule.

**F3 —** installe l'outil qui sait aller chercher le logiciel du prompteur.

- [ ] **F3**

```
sudo apt install -y git
```

*✅ Quelques lignes défilent, puis le `$` revient.*

**F4 —** télécharge le logiciel du prompteur depuis Internet. *(Pas de `sudo`.)*

- [ ] **F4**

```
git clone https://github.com/AdrienClement38/prompteur.git
```

*✅ Plusieurs lignes défilent et la dernière se termine par **100 %**. Le texte
peut être en français ou en anglais, peu importe. **La vraie preuve, c'est que la
ligne avec le signe `$` revient**, sans les mots « error » ni « fatal ».*

**F5 —** entre dans le dossier qui vient d'être téléchargé. *(Pas de `sudo`.)*

- [ ] **F5**

```
cd prompteur
```

*✅ Le texte au début de la ligne change et se termine maintenant par
**`prompteur $`**. C'est le signe visible que vous êtes au bon endroit.*

> **❌ La réponse est « No such file or directory » ?** C'est que vous n'êtes pas
> parti du bon dossier. Tapez d'abord `cd` tout seul suivi d'Entrée (cela vous
> ramène chez vous), puis retapez `cd prompteur`.

**F6 —** autorise le programme d'installation à se lancer. *(Pas de `sudo`.)*

- [ ] **F6**

```
chmod +x install/setup.sh
```

*✅ Rien ne s'affiche du tout : c'est normal, et c'est bon signe.*

**F7 —** lance l'installation complète, **en imposant votre mot de passe WiFi**. *(Pas de `sudo` !)*

⚠️ **Remplacez `prompteur2026` par VOTRE information n° 3**, en gardant tout le
reste identique :

- [ ] **F7**

```
WIFI_PASS="prompteur2026" ./install/setup.sh
```

> **⌨️ La ligne la plus délicate du document — comment la taper sans faute.**
> Voici la **ligne modèle**. La partie en gras — et elle seule — est à remplacer
> par votre mot de passe ; tout le reste se recopie caractère pour caractère :
>
> `WIFI_PASS="`**`prompteur2026`**`" ./install/setup.sh`
>
> - Le **guillemet droit** (`"`) se tape avec **Majuscule + touche du chiffre 3**.
>   N'utilisez ni les guillemets « français », ni ceux d'un traitement de texte.
> - **Aucun espace** avant ni après le signe `=`.
> - **Un espace obligatoire** entre le guillemet fermant et le `./`.
> - Rien d'autre à changer : ni majuscules, ni tirets, ni la fin de la ligne.
> - **Pour corriger :** flèches gauche/droite et touche **Retour arrière**. Pour
>   tout abandonner et recommencer la ligne proprement : **Ctrl + C**.

> **⚠️ PIÈGE — « ça s'est arrêté, l'appareil a planté ! » (non : il vous parle).**
> L'installation redemande souvent votre mot de passe (information n° 2), au
> début ou **en plein milieu** du défilement — c'est normal, l'autorisation
> donnée tout à l'heure a une durée limitée. Comme à l'étape E, **rien ne
> s'affichera pendant que vous le tapez** : tapez-le à l'aveugle, puis Entrée, et
> le défilement repart. Cela peut se produire une ou plusieurs fois.
>
> **Comment faire la différence entre « ça travaille » et « ça attend » :**
> - des lignes défilent, ou un petit curseur clignote tout seul en bas → **ça
>   travaille**, ne touchez à rien, même pendant plusieurs minutes ;
> - tout est immobile et **la dernière ligne se termine par deux points** (par
>   exemple `[sudo] Mot de passe de prompteur :`) → **ça attend** : tapez votre
>   mot de passe puis Entrée.

Pendant l'installation, des lignes commençant par **`==>`** défilent, dans cet
ordre : installation des programmes, création du service (le petit programme qui
démarre tout seul à chaque allumage), configuration du WiFi, pare-feu (le filtre
qui empêche toute connexion venue d'ailleurs), puis l'affichage plein écran.
Comptez plusieurs minutes sur la première.

**✅ CE QUE VOUS DEVEZ VOIR — c'est le moment décisif :**
un **cadre entouré de signes `=`** s'affiche, avec les mots **« Installation
terminée »**, une adresse, le nom du WiFi **`Prompteur`** et son mot de passe.

> **✍️ À NOTER SUR PAPIER — MAINTENANT, avant de continuer.**
> Vérifiez dans ce cadre que le mot de passe WiFi affiché est bien **celui que
> vous avez choisi**. Recopiez-le sur votre feuille.
> **Et par sécurité : photographiez ce cadre avec votre téléphone.** Cela prend
> trois secondes et cela peut vous sauver une soirée.
>
> La dernière ligne de ce cadre vous invite à redémarrer le Raspberry Pi :
> **c'est exactement l'étape G, juste en dessous. Il n'y a rien à faire de plus
> que de continuer ce document.**

> **❌ Le cadre ne s'affiche pas ?** L'installation a échoué. **Ne redémarrez
> surtout pas.** Regardez le **dernier message affiché** dans la fenêtre noire :
> - S'il parle du mot de passe WiFi (« too short », « passphrase »…) : votre mot
>   de passe fait moins de 8 caractères ou contient un symbole. Choisissez-en un
>   autre, uniquement lettres et chiffres, et **relancez la ligne F7**.
> - S'il parle de réseau (« could not resolve », « network unreachable »…) :
>   Internet s'est coupé. Vérifiez le câble Ethernet, puis **relancez la ligne F7**.
> - Dans tous les cas, **relancer la ligne F7 est sans danger** : on peut la
>   relancer autant de fois qu'on veut, avec le même mot de passe entre guillemets.

> **💡 Le bon moment — et le plus simple — pour apprendre leurs touches aux pédales.**
> Si vous voulez mettre toutes les chances de votre côté, c'est **maintenant**,
> avant le redémarrage : le bureau est encore accessible normalement et le
> logiciel du prompteur tourne déjà.
> Branchez le pédalier sur le boîtier, ouvrez le navigateur du bureau (icône en
> forme de globe) à l'adresse `http://localhost:5000`, puis suivez la marche à
> suivre décrite à l'**étape I, paragraphe I.2**. Une fois fait, revenez ici.
> *(Ce n'est pas obligatoire : beaucoup de pédaliers fonctionnent sans aucun
> réglage, et vous le saurez à l'étape I.)*

---

## Étape G — Le redémarrage qui révèle tout

Cette dernière ligne redémarre le boîtier.

```
sudo reboot
```

L'écran s'éteint, la framboise apparaît, puis **en 30 à 60 secondes** le
prompteur s'affiche **tout seul**. Ne touchez à rien pendant ce temps.

**✅ CE QUE VOUS DEVEZ VOIR — la signature d'une installation réussie :**

- Un **fond entièrement noir** avec du **gros texte blanc**, commençant par
  **« Bienvenue sur ton prompteur… »** (c'est un texte de démonstration ; il sera
  remplacé dès le premier envoi depuis le téléphone, et il vous tutoie sans que
  cela ait la moindre importance).
- Une fine **ligne rouge horizontale** en travers de l'écran, avec un petit
  triangle rouge à chaque bout. **Cette ligne doit traverser l'écran d'un bord à
  l'autre** : c'est un excellent test de cadrage de l'écran.
- **Pendant 12 secondes**, un cadre gris en haut, avec les adresses.
- **Pendant 6 secondes**, un bandeau d'aide en bas à gauche.
- En haut à droite, un petit badge **« ⏸ 70 »** qui, lui, reste affiché en permanence.
- **Aucune barre de navigateur, aucun onglet, aucune flèche de souris.** C'est
  exactement ce qu'il faut.

> **❌ Le prompteur ne s'affiche pas ?** D'abord, **attendez deux minutes montre
> en main** : un premier démarrage peut être lent. Ensuite, selon ce que vous
> voyez :
>
> **Vous voyez le bureau (fond d'écran, barre en haut).** Deux causes, dans
> l'ordre de fréquence :
> 1. la ligne **F7** a été lancée **avec `sudo`**. Ouvrez la fenêtre noire (icône
>    `>_` en haut, ou **Ctrl + Alt + T**), tapez `cd prompteur`, puis relancez la
>    ligne F7 **sans `sudo`**, avec le même mot de passe entre guillemets, puis
>    tapez `sudo reboot` ;
> 2. dans le menu bleu, **« Console »** a été choisi au lieu de **Desktop** —
>    refaites le réglage n° 1 de l'étape E, puis `sudo reboot` ;
> 3. *(si votre menu avait deux lignes séparées)* la ligne **Boot** a bien été
>    réglée sur **Desktop**, mais la ligne **Auto Login** a été oubliée — c'est
>    d'ailleurs le cas si le boîtier vous a réclamé votre mot de passe avant
>    d'arriver au bureau. Refaites le réglage n° 1 de l'étape E, cas 2, puis
>    `sudo reboot`.
>
> **L'écran reste noir, ou affiche un texte blanc sur fond noir sans jamais
> arriver au bureau :** éteignez proprement (voir « Éteindre le boîtier
> proprement »), attendez 10 secondes, rallumez, et laissez **une minute
> complète** sans rien toucher.
>
> **L'écran affiche une page blanche ou un message d'erreur en anglais du
> navigateur** (du genre « This site can't be reached ») : voir la partie « Si ça
> ne marche pas », la solution tient en une touche.

**Deux vérifications immédiates, au clavier branché sur le boîtier :**

- [ ] **G1.** Appuyez sur la touche **i**. → Le cadre des adresses réapparaît (et disparaît si vous rappuyez). *Cela prouve que le logiciel tourne bien.*
- [ ] **G2.** **Maintenez la flèche du bas** enfoncée. → Le texte monte, et le badge en haut à droite passe de **⏸** à **▶︎**. Relâchez : le texte s'arrête. Puis maintenez la **flèche du haut** : le texte redescend, nettement plus vite, et le badge affiche **◀︎**. *Cela prouve que le défilement fonctionne, avant même de brancher les pédales.*

> **✍️ À NOTER SUR PAPIER :** le logiciel se trouve désormais dans le dossier
> `/home/<votre-nom-d-utilisateur>/prompteur` sur le boîtier.
> **Ne déplacez jamais ce dossier et ne le renommez jamais** : l'appareil sait où
> il est, et le déplacer casserait le démarrage automatique de l'écran.
> Dans ce dossier, deux choses méritent d'être connues d'un dépanneur : le
> sous-dossier **`scripts`** contient tous les textes enregistrés par le
> journaliste (un fichier par texte), et le fichier **`state.json`**, juste à
> côté, contient le texte affiché et tous les réglages.

---

## Étape G bis — Sortir de l'écran prompteur, et y revenir

À partir de maintenant, l'écran du boîtier est **occupé en permanence par le
prompteur** : plus de barre en haut, plus de menu, plus de flèche de souris.
C'est voulu. Mais plusieurs dépannages demandent de retrouver le bureau. Voici
les gestes, à faire **avec le clavier branché sur le boîtier** :

- [ ] **1.** Essayez d'abord **Ctrl + Alt + T** : la fenêtre noire s'ouvre parfois **par-dessus** le prompteur. C'est le geste le plus doux : le prompteur reste vivant derrière.
- [ ] **2.** Si cela ne suffit pas, appuyez sur **Alt + F4** : l'affichage plein écran se ferme et **le bureau réapparaît**, avec sa barre en haut et le menu framboise à gauche.
- [ ] **3.** Pour **faire revenir le prompteur** : ouvrez la fenêtre noire et tapez la ligne ci-dessous, ou coupez et remettez simplement le courant après une extinction propre.

```
sudo reboot
```

> **✅ Rassurez-vous : fermer l'affichage ne casse rien.** Le prompteur revient
> **à chaque démarrage**, tout seul, avec le dernier texte envoyé. En revanche il
> ne revient **pas** tout seul dans la minute : tant que vous n'avez pas
> redémarré, l'écran reste sur le bureau. **Ne faites donc ce geste que si vous
> êtes prêt à redémarrer** — jamais pendant une prise.

---

## Étape G ter — Éteindre le boîtier proprement

C'est le geste que le journaliste répétera à chaque fin de tournage. **Il ne faut
jamais se contenter de débrancher** : une coupure brutale pendant que l'appareil
écrit peut abîmer la carte mémoire et obliger à tout réinstaller.

**La méthode normale, avec le petit bouton du boîtier :**

- [ ] **1.** Appuyez **brièvement** (moins d'une seconde) sur le **petit bouton rond situé à côté de la prise d'alimentation USB-C**.
- [ ] **2.** Selon le modèle, soit l'écran s'éteint tout seul au bout de quelques secondes, soit **une petite fenêtre de confirmation apparaît** : dans ce cas, **appuyez une deuxième fois brièvement** sur le bouton (ou cliquez sur **Shutdown** si vous avez une souris).
- [ ] **3.** Attendez que **l'écran soit éteint**, puis **comptez 20 secondes**.
- [ ] **4.** Débranchez l'alimentation.

> **⚠️ Ne maintenez JAMAIS ce bouton enfoncé plusieurs secondes :** cela coupe
> brutalement le courant, exactement comme un arrachage de prise.

> **🧪 À vérifier une fois, pendant la répétition générale :** que ce bouton soit
> bien accessible sur **votre** boîtier plastique, et comment il réagit
> (extinction directe, ou fenêtre de confirmation). **Notez-le sur la fiche** du
> journaliste : c'est un geste qu'il fera tous les jours.

**Si le bouton n'est pas accessible sur votre boîtier**, il reste deux solutions,
avec le clavier branché :

- Faites **Alt + F4** pour revenir au bureau (voir l'étape G bis), puis **menu framboise en haut à gauche → Shutdown**.
- Ou, dans la fenêtre noire (**Ctrl + Alt + T**), tapez cette ligne, qui éteint proprement :

```
sudo poweroff
```

> **📌 Cohérence avec le mode d'emploi du journaliste.** Le document
> `MODE-EMPLOI.md`, remis au journaliste, décrit l'extinction. **Vérifiez le
> comportement réel de votre boîtier, choisissez UNE méthode, et corrigez à la
> main le mode d'emploi imprimé** pour qu'il dise exactement la même chose que la
> fiche de la sacoche. Deux consignes différentes valent moins que zéro.

---

## Étape H — Connecter le téléphone

Le boîtier fabrique maintenant **son propre réseau WiFi**, appelé `Prompteur`.
C'est par lui, et uniquement par lui, que le téléphone pilote le prompteur.
Ce réseau **ne donne pas accès à Internet** : c'est normal, et c'est même le but.

- [ ] **H1.** Sur le téléphone, ouvrez la liste des réseaux WiFi. Un réseau nommé exactement **`Prompteur`** doit apparaître (laissez-lui jusqu'à une minute après l'allumage du boîtier).

> **⚠️ PIÈGE — le mot de passe refusé alors qu'il est bon.**
> C'est l'échec n° 1 sur téléphone : le clavier met **automatiquement une
> majuscule à la première lettre**, et ajoute parfois un espace à la fin.
> **Avant de valider, appuyez sur le petit œil** (ou « afficher le mot de passe »)
> pour le lire en clair, et vérifiez caractère par caractère : pas de majuscule
> indésirable, pas d'espace.
> Si le téléphone refuse quand même : demandez-lui d'**« oublier ce réseau »**,
> puis reconnectez-vous en retapant le mot de passe lentement.

- [ ] **H2.** Connectez-vous avec votre mot de passe (information n° 3).

**✅ Ce que vous devez voir :** le réseau **`Prompteur`** passe en tête de la liste
des réseaux, avec en dessous la mention **« Connecté »** — souvent suivie de
« sans Internet » ou « pas d'accès à Internet ». **Cette mention est normale et
attendue.**

- [ ] **H3.** **Le téléphone va se plaindre qu'il n'y a pas d'Internet. Il faut lui répondre de rester quand même :**
  - **Sur Android :** un message du genre « Ce réseau n'a pas d'accès à Internet » apparaît → répondez **Oui / Rester connecté**.
  - **Sur Android également, et c'est souvent oublié :** dans les réglages WiFi, ouvrez les **options avancées** (ou les trois points, ou « Wi-Fi intelligent » / « Paramètres intelligents » sur les Samsung) et **désactivez le passage automatique aux données mobiles** (« Basculer vers les données mobiles », « Passer automatiquement au réseau mobile »). Sans cela, le téléphone repart en 4G au bout de quelques minutes, malgré votre « rester connecté ».
  - **Sur iPhone :** ignorez l'alerte, puis allez dans **Réglages → Données cellulaires** et **désactivez « Assistance Wi-Fi »**.

> **⚠️ PIÈGE — le téléphone qui repart tout seul en 4G.**
> Sans les réglages H3, le téléphone quitte le réseau du boîtier au bout de
> quelques minutes et la télécommande cesse de répondre — parfois en plein
> tournage. **Faites ces réglages aujourd'hui, une fois pour toutes**, sur le
> téléphone du journaliste lui-même.

- [ ] **H4.** Ouvrez le navigateur du téléphone et tapez **l'adresse complète** :

```
http://10.42.0.1:5000
```

> **⚠️ PIÈGE — la barre d'adresse qui lance une recherche.**
> Si vous tapez `10.42.0.1:5000` sans le `http://` du début, beaucoup de
> téléphones croient à une recherche Google… qui échoue, puisqu'il n'y a pas
> d'Internet. **Tapez l'adresse en entier**, `http://` compris.

**✅ Ce que vous devez voir :** une page avec le mot **Prompteur** en haut, la
phrase « Télécommande — connecté au boîtier, sans internet », et **trois onglets :
Texte, Contrôle, Réglages**. La grande zone de texte **n'est pas vide** : elle
contient déjà le texte de bienvenue, ce qui prouve que le téléphone a bien parlé
au boîtier.

> **ℹ️ La pastille verte à côté du mot « Prompteur » est purement décorative.**
> Elle est verte en permanence, même si le téléphone a perdu le réseau. **Ne vous
> y fiez jamais.** La seule preuve qu'un texte est réellement parti, c'est la
> **bulle de confirmation** décrite au point H7.

**H5 — Mettre la télécommande sur l'écran d'accueil du téléphone**

Le journaliste n'aura ainsi plus jamais à taper cette adresse. La manipulation
dépend du téléphone :

- [ ] **Sur iPhone (navigateur Safari) :** appuyez sur le bouton **Partager** (le carré avec une flèche vers le haut, en bas de l'écran) → faites défiler → **« Sur l'écran d'accueil »** → **Ajouter**.
- [ ] **Sur Android (navigateur Chrome) :** appuyez sur les **trois points** en haut à droite → **« Ajouter à l'écran d'accueil »** (parfois rangé dans « Partager ») → **Ajouter**.

**✅ Ce que vous devez voir :** une **nouvelle icône** apparaît sur l'écran
d'accueil du téléphone. Un seul appui dessus ouvre la télécommande.

- [ ] **H6.** **Réglez le verrouillage automatique du téléphone sur 5 minutes, ou sur « Jamais », les jours de tournage** (iPhone : Réglages → Luminosité et affichage → Verrouillage automatique ; Android : Paramètres → Affichage → Mise en veille de l'écran). Sinon l'écran s'éteint entre deux prises, et il faut déverrouiller — parfois recharger la page — au pire moment.

- [ ] **H7. Le test de liaison.** Dans l'onglet **Texte**, effacez ce qu'il y a et tapez un mot, par exemple `BONJOUR`. Appuyez sur le bouton vert **« Envoyer à l'écran »**.

**✅ Ce que vous devez voir :** une petite bulle apparaît en bas du téléphone —
une bulle du type **« Texte envoyé à l'écran »**, suivie d'un signe de validation
— et le mot s'affiche sur l'écran du boîtier **en moins d'une seconde**.

> **⚠️ RÈGLE À RETENIR ET À TRANSMETTRE : pas de bulle = ce n'est pas parti.**
> Si l'appui sur « Envoyer à l'écran » n'affiche **aucune** bulle de
> confirmation, c'est que le téléphone a perdu le réseau du boîtier. Aucun autre
> message n'apparaîtra. La parade : vérifier que le téléphone est bien sur le
> WiFi `Prompteur`, **recharger la page**, et recommencer.

> **🆘 Si le téléphone lâche, n'importe quel autre appareil le remplace.**
> Batterie vide, téléphone cassé, appel qui n'en finit pas : **un deuxième
> téléphone, une tablette ou un ordinateur portable font exactement le même
> travail.** Il suffit de connecter cet appareil au WiFi `Prompteur` et d'ouvrir
> la même adresse `http://10.42.0.1:5000` : on y retrouve les trois onglets et
> toute la bibliothèque de textes du boîtier — rien n'est stocké dans le
> téléphone. **Faites l'essai avec un deuxième appareil pendant la répétition
> générale**, et écrivez-le sur la fiche de la sacoche.

---

## Étape I — Le pédalier

C'est la partie qui inquiète le plus, et c'est souvent la plus simple.

> **ℹ️ Si votre pédalier a trois pédales, celle du milieu ne sert à rien :** le
> prompteur n'en utilise que deux, la droite (avancer) et la gauche (reculer).
> Ce n'est ni une panne ni un oubli.

### I.1 — D'abord : essayer sans rien régler

Certains pédaliers envoient déjà, d'origine, exactement les touches attendues par
le prompteur (flèche du bas et flèche du haut). Dans ce cas, il n'y a **rien à
faire du tout**. C'est donc par là qu'il faut commencer.

- [ ] **I1.** Branchez le pédalier sur un port USB du **boîtier**.
- [ ] **I2.** Assurez-vous qu'un texte est bien affiché à l'écran.
- [ ] **I3.** **Maintenez la pédale de droite enfoncée.**

**✅ Ce que vous devez voir :** le texte monte, et le badge en haut à droite de
l'écran passe de **⏸** à **▶︎**. Vous relâchez : le texte s'arrête net et le
badge revient sur **⏸**.
Testez ensuite la **pédale de gauche** : le texte redescend, visiblement plus
vite, et le badge affiche **◀︎**.

**Si cela fonctionne : c'est terminé pour le pédalier.** Passez au paragraphe
I.3. N'allez surtout pas régler ce qui marche déjà.

### I.2 — Si les pédales ne font rien : leur apprendre leurs touches

Le prompteur sait « apprendre » quelle touche envoie chaque pédale. Cet
apprentissage se fait dans l'onglet **Réglages** de la télécommande, tout en bas,
dans la carte **« Pédales »**.

> **⚠️ Ce que fait réellement le champ d'apprentissage — à lire avant de cliquer.**
> Ces deux champs enregistrent **la première touche appuyée, quelle qu'elle
> soit** — y compris Échap, Tab ou une lettre. Il n'existe **aucun bouton
> d'annulation**. Donc : **ne cliquez dedans que si vous voulez vraiment
> réapprendre une pédale**, et appuyez alors immédiatement sur la pédale.
> **Pour annuler sans rien changer** : cliquez ailleurs dans la page, puis
> **rechargez la page** — tant qu'aucune touche n'a été appuyée, rien n'a été
> modifié, même si le champ affiche encore « … appuie sur la pédale ».
>
> **Depuis un téléphone, cet apprentissage ne peut de toute façon pas
> fonctionner** : le champ écoute le clavier de **l'appareil qui affiche la
> page**, or les pédales sont branchées sur le boîtier. Leurs appuis n'arrivent
> jamais jusqu'au téléphone.

**La bonne méthode — aucun logiciel à installer, aucun PC Windows requis.**

**Méthode 1 (la plus sûre) — depuis un ordinateur portable, Mac compris**

- [ ] Branchez le pédalier **sur cet ordinateur portable** (pas sur le boîtier).
- [ ] Connectez cet ordinateur au WiFi `Prompteur`, exactement comme le téléphone.
- [ ] Ouvrez `http://10.42.0.1:5000` dans son navigateur. **✅ Vous devez voir la même page à trois onglets que sur le téléphone.**
- [ ] Onglet **Réglages** → carte **Pédales** → cliquez dans le champ **« Touche pédale droite (avancer) »**. **✅ Le champ se vide et affiche « … appuie sur la pédale ».**
- [ ] **Appuyez sur la pédale de droite.** **✅ Une bulle du type « Touche enregistrée : ArrowDown » apparaît, et le champ affiche ce nom.**
- [ ] Recommencez avec le champ **« Touche pédale gauche (reculer) »** et la pédale de gauche.
- [ ] **Rebranchez le pédalier sur le boîtier** : le réglage est mémorisé **par le boîtier**, pas par l'ordinateur. Retestez comme au paragraphe I.1.

**Méthode 2 — sur le boîtier lui-même**

Elle demande de quitter momentanément l'écran du prompteur, ce qui n'est pas
gênant mais impose un redémarrage ensuite.

- [ ] Le clavier et la souris étant branchés sur le boîtier, appuyez sur **Alt + F4** pour retrouver le bureau (voir l'étape G bis). **✅ Le bureau réapparaît, avec sa barre en haut.**
- [ ] Ouvrez le navigateur du bureau (icône en forme de globe) et tapez l'adresse `http://localhost:5000`. **✅ La page à trois onglets s'affiche.**
- [ ] Faites l'apprentissage comme dans la méthode 1, avec le pédalier branché sur le boîtier.
- [ ] **Pour faire revenir le prompteur :** ouvrez la fenêtre noire (**Ctrl + Alt + T**) et tapez `sudo reboot`. **✅ Au bout d'une minute, l'écran prompteur revient tout seul avec le dernier texte.**

> **✍️ À NOTER SUR PAPIER :** les noms exacts des deux touches apprises. Les
> valeurs d'origine sont **`ArrowDown`** pour la pédale droite (avancer) et
> **`ArrowUp`** pour la pédale gauche (reculer).
>
> **Pour revenir un jour aux réglages d'origine** (ces deux mots ne se tapent pas
> au clavier : les champs n'acceptent que la touche réellement appuyée) :
> branchez **un clavier** sur le boîtier, ouvrez la télécommande, onglet
> **Réglages** → carte **Pédales**, cliquez dans le champ **« Touche pédale
> droite »** et appuyez sur la touche **Flèche bas** du clavier ; puis cliquez
> dans le champ **« Touche pédale gauche »** et appuyez sur la touche **Flèche
> haut**. Les mots `ArrowDown` et `ArrowUp` doivent alors s'afficher : c'est la
> preuve que tout est remis d'origine.

> **⚠️ PIÈGE — ne donnez pas à une pédale une touche déjà utilisée** (Espace, R,
> M, H, I, + ou -) : la pédale prendrait la place du raccourci, qui cesserait de
> fonctionner. **Et surtout jamais la touche F** : avec F, ce serait **la pédale
> elle-même qui cesserait complètement de fonctionner**, ce qui est bien plus
> difficile à comprendre. En cas de doute, revenez aux flèches du haut et du bas.

### I.3 — Le mode des pédales : laissez « Maintien »

Dans la même carte **Pédales**, un choix propose **« Maintien »** ou
**« Impulsion »**. **Laissez « Maintien »**, qui est le réglage d'usine (le bouton
actif est celui qui est coloré en bleu).

> **⚠️ PIÈGE — le mode « Impulsion » est dangereux en direct.**
> En mode Maintien : on garde la pédale enfoncée, le texte avance ; on relâche,
> il s'arrête. C'est ce que l'on veut.
> En mode Impulsion, la pédale de gauche **ne fait pas reculer** : elle renvoie
> d'un coup **au tout début du texte**. En plein tournage, c'est la pire fausse
> manœuvre possible. N'essayez ce mode qu'à froid, jamais un jour de tournage.

### I.4 — Si une pédale lâche en plein tournage

Câble arraché, pédalier défaillant : **le prompteur reste utilisable sans les
pédales.** C'est à dire au journaliste, et à faire essayer une fois.

- Sur le téléphone, onglet **Contrôle** : le bouton **« Lecture »** lance le
  défilement **automatique**, le curseur **« Vitesse de lecture »** l'ajuste, et
  **« Pause »** l'arrête. Le bouton **« Début »** revient au tout début (et met en
  pause).
- ⚠️ Dans ce mode automatique, **la pédale ne coupe plus le défilement** : c'est
  « Pause » qu'il faut appuyer.
- Avec le clavier branché sur le boîtier : **barre d'espace** = lecture/pause,
  **+** et **-** = vitesse, **R** = retour au début.

### I.5 — Et le logiciel du fabricant du pédalier ?

Le pédalier est livré avec un logiciel de programmation **qui ne fonctionne que
sous Windows**. **Vous n'en avez pas besoin** : les deux méthodes ci-dessus
suffisent et ne demandent aucun PC Windows. Ne le gardez qu'en tout dernier
recours, pour un dépanneur informatique, si les pédales refusaient absolument
d'envoyer quoi que ce soit.

---

## Étape J — Préparer la répétition générale

Cinq minutes de préparation, sans lesquelles la checklist qui suit tourne court.

- [ ] **J1. Mettez de vrais documents sur le téléphone, MAINTENANT.** Le test d'import se fait depuis le téléphone (bouton **« Fichier »**), donc le document doit **déjà se trouver dans le téléphone**. Or, une fois connecté au réseau `Prompteur`, **le téléphone n'a plus Internet** : impossible d'aller chercher une pièce jointe dans un mail à ce moment-là. **Avant de rejoindre le réseau du boîtier**, enregistrez sur le téléphone **un vrai document Word (.docx)** et **un vrai PDF** (depuis un mail ou un espace de stockage).
- [ ] **J2. Préparez la clé USB de test :** copiez ce même document Word **à la racine de la clé, c'est-à-dire visible dès l'ouverture de la clé, pas rangé dans un dossier**. *(Le boîtier sait aussi chercher dans les sous-dossiers, mais un fichier à la racine est trouvé plus vite et à coup sûr.)*
- [ ] **J3.** Prévoyez **un deuxième appareil** (tablette, autre téléphone, ordinateur portable) pour tester la solution de repli de l'étape H.
- [ ] **J4.** Ayez sous la main **le journaliste lui-même**, si possible : les réglages de confort de lecture se règlent avec ses yeux, pas avec les vôtres.

---

## Étape K — Checklist finale : la répétition générale

Ne considérez le boîtier comme prêt **qu'après avoir coché toutes ces cases**.
Ce test simule un vrai tournage : c'est une demi-heure qui vous évitera une
catastrophe en direct.

**Le boîtier**

- [ ] J'éteins proprement le boîtier, comme décrit dans la partie **« Éteindre le boîtier proprement »** (appui court sur le petit bouton rond à côté de la prise USB-C), j'attends que l'écran soit éteint, je compte 20 secondes, puis je débranche.
- [ ] **Je note sur la fiche** ce que fait exactement ce bouton sur ce boîtier-là (extinction directe, ou fenêtre de confirmation à valider par un deuxième appui).
- [ ] Je rebranche. **Sans toucher à rien**, au bout d'une minute, le prompteur revient tout seul avec **le dernier texte envoyé**.
- [ ] **Je refais ce test d'extinction/rallumage une deuxième fois.** (Oui, vraiment.)
- [ ] **Le test des 15 minutes :** je laisse le boîtier allumé **un quart d'heure sans y toucher**, avec un texte affiché. **L'écran doit rester allumé et le texte visible.** S'il devient noir tout seul, voir la partie « Si ça ne marche pas ».

> **⚠️ PIÈGE — ne débranchez jamais brutalement.** Une coupure de courant pendant
> que l'appareil écrit peut abîmer la carte mémoire et obliger à tout
> recommencer. Éteignez toujours par la méthode ci-dessus.

**Le téléphone**

- [ ] Le téléphone retrouve le WiFi `Prompteur` tout seul et **y reste** : je le laisse **dix minutes** sans y toucher, puis je vérifie que la page répond encore (appui sur « Pause » : le badge de l'écran change).
- [ ] Le raccourci de la télécommande est bien sur l'écran d'accueil du téléphone, et il ouvre la page d'un seul appui.
- [ ] J'envoie un vrai texte de tournage → bulle du type **« Texte envoyé à l'écran »** et le texte apparaît en moins d'une seconde.
- [ ] Le texte apparaît **calé tout en haut** et **à l'arrêt** (badge ⏸).
- [ ] **Le deuxième appareil** (tablette, autre téléphone, ordinateur) se connecte au réseau `Prompteur` et ouvre la même télécommande : c'est la roue de secours si le téléphone du journaliste lâche.

**Les fichiers — à faire AUJOURD'HUI, tant que le câble Ethernet est encore branché**

- [ ] Onglet Texte → bouton **« Fichier »** → j'importe **le document .docx que j'ai mis sur le téléphone à l'étape J** → bulle du type **« Importé : … »** et le texte apparaît, avec ses titres en plus gros.
- [ ] Même test avec **le PDF** préparé à l'étape J → le texte apparaît réellement à l'écran.
  *(Si le PDF ne passe pas alors que le .docx passe, **n'insistez pas** et ne relancez pas l'installation : cela ne changerait rien. Préparez les textes en .docx — c'est de toute façon le format recommandé — et notez-le sur la fiche du journaliste. Si le PDF est vraiment indispensable, un dépanneur pourra taper sur le boîtier, Internet branché : `sudo pip3 install --break-system-packages pypdf` puis `sudo systemctl restart prompteur`.)*
- [ ] Je branche la clé USB préparée à l'étape J **sur le boîtier** → bouton **« Clé USB »** → le fichier apparaît dans la liste → **« Charger »** → le texte s'affiche.
  *(Ce test-là ne dépend d'aucun réseau : c'est la solution de secours quand le téléphone ne répond plus.)*

**Les pédales**

- [ ] Pédale droite maintenue → le texte monte, badge **▶︎**. Relâchée → il s'arrête, badge **⏸**.
- [ ] Pédale gauche maintenue → le texte redescend, plus vite, badge **◀︎**.
- [ ] Le mode est bien sur **« Maintien »** (bouton bleu).
- [ ] J'ai essayé une fois la solution de repli sans pédales : bouton **« Lecture »** puis **« Pause »** depuis l'onglet Contrôle.

**Le confort de lecture — à régler MAINTENANT, jamais pendant une prise**

- [ ] Dans l'onglet **Réglages**, j'ajuste **taille du texte**, **interligne** et **marges** à la bonne distance de lecture, avec le journaliste si possible.
  *(Ces barres n'agissent qu'au moment où l'on **relâche** le doigt : glissez, lâchez, puis regardez le grand écran.)*
- [ ] Couleurs : **texte blanc sur fond noir** (la combinaison sûre).
- [ ] **Miroir horizontal : laissé éteint**, sauf s'il y a réellement une vitre sans tain.
- [ ] Je note ces réglages sur la feuille, pour pouvoir les remettre si quelqu'un y touche.

**L'écran de régie (seulement si un deuxième écran est prévu)**

- [ ] Sur le deuxième appareil, connecté au WiFi `Prompteur`, je tape `http://10.42.0.1:5000/view`
- [ ] Un badge **JAUNE « SPECTATEUR — suit l'écran principal »** apparaît en haut à gauche, et cet écran suit le boîtier en direct.

> **⚠️ PIÈGE — l'adresse à ne pas confondre.** Un deuxième écran doit **toujours**
> utiliser l'adresse qui se termine par **`/view`**. Avec `/display`, les deux
> écrans se disputeraient le pilotage et le défilement deviendrait incohérent.

**Le repérage physique, pour tous les montages à venir**

- [ ] Je colle **une pastille de couleur** (ou un morceau de gaffer) **sur le bon port HDMI du boîtier** ET **sur la fiche du câble micro-HDMI** correspondante : la consigne de montage devient « on branche couleur sur couleur », et le piège du mauvais port disparaît pour toujours.
- [ ] Mieux encore : je laisse le **câble micro-HDMI branché en permanence côté boîtier**, et on ne débranche que du côté de l'écran.

**LE TEST QUI VAUT TOUS LES AUTRES — en configuration réelle de tournage**

Tout ce qui précède a été fait avec le clavier, la souris et le câble Ethernet
branchés — une configuration **qui n'existera jamais sur un tournage**. Ce
dernier test est donc le seul qui prouve vraiment quelque chose.

- [ ] Je **débranche le clavier, la souris et le câble Ethernet**. Il ne reste que **l'écran, le pédalier et l'alimentation**.
- [ ] J'éteins proprement, puis je rallume.
- [ ] **Sans toucher à rien pendant une minute :** le prompteur revient seul, avec le dernier texte.
- [ ] Le téléphone retrouve le réseau `Prompteur` et ouvre la télécommande depuis son raccourci.
- [ ] J'envoie un texte : il s'affiche en moins d'une seconde.
- [ ] Les deux pédales répondent (▶︎ et ◀︎).
- [ ] J'enchaîne une « prise » complète : texte envoyé, défilement à la pédale, arrêt, retour au début (bouton **« Début »**), nouvelle prise. Tout répond.

> **Si un seul de ces points échoue, l'installation n'est pas terminée.**
> Reprenez la partie « Si ça ne marche pas » avant de remettre le matériel.

**Puis, pour la sacoche**

- [ ] Je **rebranche le clavier et la souris** (ou je les range dans la sacoche) : ce sont les outils de dépannage du tournage. **Le câble Ethernet, lui, ne sert plus** : rangez-le quand même dans la sacoche, il sera nécessaire le jour d'une mise à jour.

---

## Étape L — La roue de secours : la deuxième carte mémoire

**À faire le jour de l'installation, pas après.**

La panne n° 1 des Raspberry Pi, c'est la **carte mémoire** : une coupure de
courant mal placée, ou simplement l'usure, et le boîtier ne démarre plus. Sur un
plateau, refaire toute l'installation est impossible : il faudrait une heure, un
clavier, une souris, un écran, un câble Ethernet et Internet.

**La parade tient dans une carte à 10-15 €.**

- [ ] Une fois la répétition générale validée, préparez **une deuxième carte micro-SD**, soit en refaisant toute la procédure sur cette carte, soit en **copiant la première carte** avec Raspberry Pi Imager (fonction de copie/clonage, sur l'ordinateur, avec les deux cartes ou en deux temps).
- [ ] **Étiquetez-la** : « Prompteur — carte de secours » **et la date**.
- [ ] Rangez-la dans la sacoche, **avec la fiche papier**.
- [ ] Testez-la une fois : éteignez le boîtier, échangez la carte, rallumez, vérifiez que le prompteur revient. Puis remettez la carte d'origine.

> **📌 À dire au journaliste :** en cas de panne totale au démarrage, il suffit
> d'éteindre, **d'échanger la carte mémoire** (la fente est sous le boîtier) et de
> rallumer. **Sans cette carte de secours, une panne = un tournage sans
> prompteur.**

---

## Étape M — Si ça ne marche pas

> **🔑 Deux gestes reviennent souvent dans ce tableau :** retrouver le bureau du
> boîtier (**Alt + F4**) et rouvrir la fenêtre noire (**Ctrl + Alt + T**). Les
> deux sont expliqués en détail dans la partie **« Sortir de l'écran prompteur,
> et y revenir »**. Ils demandent un **clavier branché sur le boîtier** : c'est la
> raison pour laquelle le clavier reste dans la sacoche.

| Ce que vous constatez | Ce qu'il faut faire |
|---|---|
| **L'écran reste noir au démarrage** | Le câble micro-HDMI est sur le mauvais port. Rebranchez-le sur celui **le plus proche de la prise d'alimentation USB-C**. Sinon : éteignez tout, allumez **l'écran d'abord**, le boîtier ensuite. En dernier recours, testez sur une télévision ordinaire. |
| **L'image est décalée, coupée sur les bords, ou minuscule** | C'est fréquent avec les petits écrans HDMI. Dans l'ordre : (1) si l'écran possède ses propres boutons de réglage, cherchez-y un mode « plein écran » / « auto » / « 16:9 » ; (2) éteignez le boîtier, allumez **l'écran d'abord**, puis le boîtier ; (3) contrôle simple : **la ligne rouge doit traverser l'écran d'un bord à l'autre** — sinon l'image est mal cadrée. Si rien n'y fait, signalez le problème à un dépanneur **avec la marque et le modèle exacts de l'écran**. |
| **Le boîtier démarre sur le bureau, pas sur le prompteur** | Trois causes possibles : (1) la ligne **F7** a été lancée avec `sudo` — ouvrez la fenêtre noire, tapez `cd prompteur`, relancez la ligne F7 **sans** `sudo` (même mot de passe entre guillemets), puis `sudo reboot` ; (2) dans le menu bleu, « Console » a été choisi au lieu de **Desktop** — refaites le réglage n° 1 de l'étape E ; (3) si votre menu avait **deux lignes séparées**, la ligne **Auto Login** a été oubliée — refaites le réglage n° 1 de l'étape E, cas 2. |
| **L'écran affiche une page blanche, ou un message d'erreur en anglais du navigateur** (« This site can't be reached ») | Le boîtier a démarré plus vite que son propre programme : l'affichage s'est ouvert trop tôt et **ne se répare pas tout seul**. Branchez le clavier de la sacoche et appuyez sur **F5** (ou **Ctrl + R**) pour recharger la page. Si le prompteur ne revient pas : éteignez proprement, attendez 10 secondes, rallumez, et laissez **une minute complète** sans rien toucher. |
| **L'écran devient noir tout seul au bout de quelques minutes** | C'est la mise en veille. Refaites le **réglage n° 3 de l'étape E** (Display Options → Screen Blanking → NON), puis redémarrez. Vérifiez aussi la mise en veille **propre à l'écran 7 pouces**, s'il en a une dans ses propres boutons. |
| **Le réseau WiFi `Prompteur` n'apparaît pas sur le téléphone** | Attendez d'abord **une minute complète** après l'allumage. Toujours rien : sur le boîtier, ouvrez la fenêtre noire (**Ctrl + Alt + T**) et tapez la ligne ci-dessous, qui rallume le réseau du boîtier. Attendez 30 secondes et regardez à nouveau la liste des WiFi du téléphone.<br>`sudo nmcli connection up Prompteur`<br>Si le réseau n'apparaît toujours pas, **alors seulement** : rebranchez le câble Ethernet et relancez la **ligne F7** de l'étape F. *(Attention : voir l'adresse s'afficher sur l'écran du boîtier ne prouve PAS que le WiFi fonctionne — la seule preuve valable est de voir le réseau dans la liste du téléphone.)* |
| **Le téléphone refuse le mot de passe WiFi** | La cause la plus courante est la **majuscule automatique** ajoutée par le clavier du téléphone à la première lettre, ou un **espace** en fin de saisie. Appuyez sur le petit **œil** pour afficher le mot de passe en clair et relisez-le caractère par caractère. En dernier recours : demandez au téléphone d'**« oublier ce réseau »**, puis reconnectez-vous. |
| **Le mot de passe WiFi est perdu** | Sur le boîtier, revenez au bureau (**Alt + F4**), ouvrez la fenêtre noire (**Ctrl + Alt + T**) et tapez la ligne ci-dessous : le mot de passe s'affiche en clair. Notez-le, puis `sudo reboot` pour retrouver le prompteur.<br>`sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur` |
| **La page de la télécommande ne s'ouvre pas** | Vérifiez que le téléphone est bien sur le WiFi `Prompteur` (et pas en 4G), puis tapez l'adresse **en entier** : `http://10.42.0.1:5000` |
| **« Erreur de connexion au boîtier » sur le téléphone** | Le téléphone a quitté le réseau du boîtier. Reconnectez-le, refaites les réglages du point **H3** de l'étape H, puis rechargez la page. |
| **J'appuie sur « Envoyer à l'écran » et il ne se passe rien du tout** | Pas de bulle de confirmation = rien n'est parti. Le téléphone a perdu le WiFi. Reconnectez-le, **rechargez la page**, recommencez. |
| **Les pédales ne répondent plus** | L'écran du boîtier n'écoute plus le clavier (quelque chose est passé devant). **Si une souris est branchée :** cliquez une fois n'importe où sur l'écran du boîtier, puis réessayez la pédale — le badge en haut à droite doit repasser sur ▶︎. **Sinon — et c'est le cas normal en tournage :** éteignez le boîtier avec son bouton d'alimentation et rallumez-le ; une minute plus tard tout est revenu, avec le dernier texte envoyé. **Prévoyez toujours ces deux minutes de marge avant une prise.** *(Ce geste de la souris explique pourquoi une petite souris filaire doit toujours rester dans la sacoche.)* |
| **Le texte s'est figé, ça ne défile plus** | Vous êtes probablement arrivé à la fin du texte : l'appareil refuse d'aller plus loin, c'est normal. Appuyez sur le bouton **« Début »** du téléphone (ou la touche **R** du clavier du boîtier) pour revenir en haut. Attention, cela met aussi en pause. |
| **Le texte démarre trop bas sur l'écran** | C'est voulu : la première ligne est placée sous la ligne rouge de repère, et le texte monte vers elle dès le premier appui sur la pédale. Il n'y a rien à corriger. |
| **L'écran est illisible (texte noir sur fond noir)** | Quelqu'un a choisi deux couleurs identiques. Onglet **Réglages** → carte **Couleurs** → appuyez sur la pastille **blanche** pour le texte et **noire** pour le fond. C'est réparé immédiatement. |
| **Le texte est à l'envers** | **Le plus simple :** rappuyez une fois sur la touche **M** du clavier branché au boîtier, le texte se remet à l'endroit. **Si vous n'avez pas de clavier :** sur le téléphone, onglet **Réglages** → **Affichage**, **ALLUMEZ** l'interrupteur « Miroir horizontal » puis **ÉTEIGNEZ-le** (deux appuis) — c'est le deuxième appui qui remet l'écran d'aplomb. *(Un appui sur M à l'insu du téléphone laisse l'interrupteur affiché « éteint » alors que l'écran est en miroir : il n'y a donc rien à éteindre, il faut faire les deux appuis.)* |
| **Un document importé donne un écran vide (« Aucun texte »)** | Le PDF est un **document scanné** : c'est une photo de page, il ne contient aucun texte lisible par la machine. Repartez du document Word d'origine, ou copiez-collez le texte à la main dans la télécommande. |
| **« Import impossible », sans autre explication** | Le fichier dépasse la taille limite (5 Mo par fichier, 6 Mo pour l'envoi complet). Un PDF avec des photos y arrive très vite. Utilisez plutôt un **.docx**, bien plus léger. |
| **Un message technique en anglais parle de « decrypted »** | Le document est **protégé par un mot de passe**. Ouvrez-le sur un ordinateur, enregistrez-le sans mot de passe, réessayez. |
| **Le texte importé est du charabia** | Le format n'est pas reconnu (fichier `.pages` d'Apple, `.jpg`, `.zip`…). Depuis un Mac ou un iPhone, exportez toujours en **Word (.docx)** ou en PDF avant d'importer. |
| **La clé USB n'est pas détectée** | Branchez la clé **sur le boîtier** (jamais sur le téléphone), **avant** d'appuyer sur le bouton « Clé USB », attendez 5 secondes, réessayez. Utilisez **une clé USB ordinaire, du type de celles que l'on achète en supermarché** — évitez les disques durs externes et les clés chiffrées. Le plus sûr est de placer le document **à la racine de la clé, c'est-à-dire visible dès l'ouverture de la clé**. Sur une clé contenant des milliers de photos, la recherche s'arrête avant d'avoir tout parcouru et le document peut ne jamais apparaître. |
| **Dans la liste de la clé USB, un fichier commence par `._`** | Ce sont des doublons invisibles créés par les Mac. Choisissez la ligne dont le nom **ne commence pas** par un point. |
| **Un texte enregistré a disparu** | La petite croix rouge de la liste « Mes textes enregistrés » supprime **immédiatement, sans confirmation et sans corbeille**. Aucune récupération n'est possible : c'est pourquoi il faut toujours garder une copie des textes ailleurs. |
| **Le défilement part tout seul et ne s'arrête pas quand je relâche la pédale** | Quelqu'un a appuyé sur le bouton **« Lecture »** du téléphone, qui lance un défilement automatique que la pédale n'arrête pas. Appuyez sur **« Pause »** ou **« Début »** sur le téléphone, ou sur la **barre d'espace** du clavier branché au boîtier. |
| **La télécommande affiche un texte qui n'est plus celui de l'écran** | La page du téléphone ne se met pas à jour toute seule. **Rechargez-la** dans le navigateur : c'est le geste de secours universel côté téléphone. |
| **Le boîtier redémarre tout seul, ou un petit éclair apparaît en haut de l'écran** | C'est un problème d'**alimentation**. Utilisez **l'alimentation d'origine** du kit (pas un chargeur de téléphone), et **n'alimentez rien d'autre sur les ports USB du boîtier** — surtout pas l'écran, qui doit avoir sa propre alimentation secteur. |
| **Le boîtier ne démarre plus du tout : la framboise tourne en boucle, ou des messages d'erreur défilent au démarrage** | La carte mémoire est probablement abîmée. **Éteignez, échangez la carte mémoire contre la carte de secours** (voir l'étape L), rallumez, et prévenez la personne qui a installé le boîtier. Sans carte de secours, il n'y a pas de réparation possible sur un plateau. |
| **Je dois réinstaller ou mettre à jour plus tard** | Voir la partie suivante, **« Mettre à jour ou réinstaller plus tard »** : il y a un piège à connaître avant de commencer. |

---

## Étape N — Mettre à jour ou réinstaller plus tard

> **⚠️ LE PIÈGE DE LA MISE À JOUR — à lire avant tout.**
> Si vous relancez l'installation **sans remettre votre mot de passe WiFi entre
> guillemets**, le programme en **fabrique un nouveau au hasard** : l'ancien cesse
> de fonctionner, et le téléphone du journaliste ne se connectera plus — panne
> incompréhensible, découverte le jour du tournage suivant.
> **Reprenez toujours EXACTEMENT le même mot de passe qu'à l'origine** (celui de
> votre fiche).

La marche à suivre, dans l'ordre :

- [ ] **N1.** Rebranchez le **câble Ethernet** (sans Internet, la mise à jour échoue dès la première ligne) et le **clavier**.
- [ ] **N2.** Revenez au bureau (**Alt + F4**), puis ouvrez la fenêtre noire (**Ctrl + Alt + T**).
- [ ] **N3.** Entrez dans le dossier du logiciel :

```
cd prompteur
```

- [ ] **N4.** Récupérez la dernière version du logiciel :

```
git pull
```

- [ ] **N5.** Relancez l'installation **avec le même mot de passe WiFi qu'à l'origine**, sans `sudo` :

```
WIFI_PASS="votremotdepasse" ./install/setup.sh
```

- [ ] **N6.** Redémarrez :

```
sudo reboot
```

- [ ] **N7.** **Refaites toute la répétition générale** (étape K). **Jamais la veille d'un tournage.**

> **💡 Vous voulez seulement changer le mot de passe WiFi ?** Inutile de tout
> réinstaller. Deux lignes suffisent, dans la fenêtre noire :
> `sudo nmcli connection modify Prompteur wifi-sec.psk "NOUVEAUMOTDEPASSE"` puis
> `sudo nmcli connection up Prompteur`. Pensez à corriger la fiche papier **et** à
> reconnecter le téléphone.

---

## Étape O — Quand tout marche : à transmettre au journaliste

L'installation est finie. Il reste le plus important : que la personne qui va
s'en servir soit tranquille.

- [ ] **J'imprime le fichier `MODE-EMPLOI.md`** (le mode d'emploi quotidien du journaliste, dans le même dossier que ce document). Il contient les branchements, l'envoi d'un texte, les réglages, l'extinction, le dépannage, et **une fiche à découper prête à coller sur le boîtier**. Je découpe cette fiche, je la colle sur le boîtier, et je range le reste dans la sacoche.
- [ ] **Je complète à la main** les cases de cette fiche imprimée avec les informations ci-dessous.

### O.1 — La fiche qui reste dans la sacoche

Elle doit porter, écrit gros :

- **Le nom, le prénom et le numéro de téléphone de la personne qui a installé le boîtier** (vous), et **la date d'installation**. *(Le mode d'emploi du journaliste renvoie à « la personne qui a installé le boîtier, coordonnées sur la fiche » : sans ce numéro, la phrase ne sert à rien.)* **Collez aussi ce numéro directement sur le boîtier.**
- Une case **« dernière mise à jour, le : …… »**, à remplir à chaque intervention.
- Le **nom du WiFi** : `Prompteur` — et son **mot de passe**.
- Les **trois adresses** : `http://10.42.0.1:5000` (téléphone), `/display` (écran principal), `/view` (régie).
- Le **nom d'utilisateur et le mot de passe du boîtier** (informations n° 1 et n° 2) — utiles uniquement à un dépanneur, mais indispensables le jour où.
- **Comment éteindre** : le geste exact constaté sur ce boîtier (appui court sur le petit bouton rond près de la prise d'alimentation, écran éteint, 20 secondes, puis débrancher).
- Les **touches des pédales** : `ArrowDown` à droite, `ArrowUp` à gauche (ou celles que vous avez apprises).
- Les **réglages de confort** notés pendant la répétition (taille, interligne, marges, vitesse).
- La **combinaison de couleurs de secours** : texte blanc, fond noir.
- Le **geste de secours universel côté téléphone** : *« si la page semble figée, notamment après un déverrouillage de l'écran, rechargez-la dans le navigateur »*.
- La **solution de repli** : *« n'importe quel autre téléphone, tablette ou ordinateur connecté au WiFi Prompteur ouvre la même télécommande à la même adresse »*.
- Les **formats acceptés**, tels que la télécommande les affiche elle-même :
  **« Formats acceptés : Word (.doc, .docx), PDF, LibreOffice (.odt), RTF, texte (.txt) »** — avec cette précision : **le .docx est celui qui passe le mieux ; éviter les PDF, et surtout les PDF scannés.**
- **En cas de panne au démarrage : échanger la carte mémoire** contre la carte de secours rangée dans la sacoche.

### O.2 — Ce qui reste en permanence dans la sacoche

- [ ] **Une petite souris USB filaire** — *indispensable : c'est la réparation n° 1 quand les pédales ne répondent plus.*
- [ ] **Un clavier USB filaire** — dépannage et raccourcis (recharger l'écran, revenir au début, afficher les adresses).
- [ ] L'**alimentation du boîtier** et celle de **l'écran**.
- [ ] Le **câble micro-HDMI** (idéalement laissé branché côté boîtier).
- [ ] Le **pédalier**.
- [ ] La **carte mémoire de secours**, étiquetée et datée.
- [ ] Le **câble Ethernet** (inutile en tournage, indispensable le jour d'une mise à jour).
- [ ] Une **rallonge et une multiprise**.
- [ ] La **fiche papier** et le **mode d'emploi imprimé**.
- [ ] Une **clé USB** contenant les textes du jour.

### O.3 — Les raccourcis clavier, à imprimer et coller au dos du boîtier

| Touche | Effet |
|---|---|
| **Flèche bas** (maintenue) | Le texte avance — exactement comme la pédale droite |
| **Flèche haut** (maintenue) | Le texte recule, plus vite — comme la pédale gauche |
| **Espace** | Lecture / pause du défilement automatique |
| **+** (ou `=`) | Plus vite (par pas de 10) — **réglage provisoire** |
| **-** (ou `_`) | Moins vite — **réglage provisoire** |
| **R** | Revenir au début (et met en pause) |
| **F5** (ou `Ctrl + R`) | Recharger l'écran, s'il affiche une page blanche ou une erreur |
| **i** | Affiche ou masque les adresses |
| **H** | Affiche ou masque le bandeau d'aide |
| **M** | Miroir — **à ne pas toucher par erreur** (rappuyer dessus le remet à l'endroit) |
| **F** | Plein écran — **inutile sur le boîtier, à éviter** |

> **ℹ️ « Réglage provisoire » veut dire :** les touches **+**, **-** et **M** du
> clavier ne changent l'affichage **que sur le moment**. Le téléphone n'en sait
> rien, et tout revient en arrière dès le prochain réglage envoyé depuis le
> téléphone, ou au redémarrage. **Pour une vitesse et un miroir qui restent,
> réglez-les depuis le téléphone.**

> **Les autres touches n'ont pas d'effet sur le prompteur.** Évitez seulement
> **Alt + F4** et **Ctrl + W**, qui ferment l'affichage : il faudrait alors
> redémarrer le boîtier pour le faire revenir.

### O.4 — Les six règles à énoncer à voix haute, en montrant

Faites-lui une vraie démonstration, avec un de ses propres textes. Et énoncez ces
six règles, qui résument tout ce qui peut mal tourner :

1. **« Envoyer à l'écran » = ça passe à l'antenne. « Enregistrer » = ça range dans la bibliothèque.** Ce sont deux gestes différents : envoyer n'enregistre pas, enregistrer n'affiche rien.
2. **Pas de bulle de confirmation = ce n'est pas parti.** C'est la seule preuve qu'un texte a bien été envoyé.
3. **Ne jamais toucher la petite croix rouge** de la liste des textes enregistrés : elle efface définitivement, sans rien demander. Pour rappeler un texte, c'est le bouton **bleu « Charger »**.
4. **Ne rien charger, ni importer, ni corriger pendant une prise** : tout cela remplace instantanément le texte à l'écran et remet le défilement tout en haut.
5. **Ne pas cliquer dans les deux cases du bas de l'onglet Réglages** (les touches des pédales) : la première touche appuyée y devient la nouvelle touche de la pédale, et il n'y a pas d'annulation. Depuis un téléphone, cet apprentissage ne peut de toute façon pas fonctionner.
6. **Récupérez toujours vos textes AVANT de rejoindre le réseau `Prompteur`.** Tant que le téléphone est sur ce réseau, **il n'a plus Internet** : ni mail, ni messagerie, ni document en ligne.
   *La manœuvre, quand un texte arrive à la dernière minute :* quitter le réseau `Prompteur` (repasser en 4G) → ouvrir le mail → **copier** le texte → revenir sur le réseau `Prompteur` → ouvrir la télécommande → **coller** dans la zone de texte → **« Envoyer à l'écran »**.

### O.5 — Ce qu'il faut lui faire faire lui-même, devant vous

Une démonstration qu'il se contente de regarder ne suffit pas. Faites-lui
exécuter, de ses mains :

- [ ] Se connecter au WiFi `Prompteur` et ouvrir la télécommande depuis son raccourci.
- [ ] Coller un texte et l'envoyer à l'écran.
- [ ] Faire défiler à la pédale, s'arrêter, revenir au début.
- [ ] Importer un de ses documents Word depuis le téléphone, **et** charger un document depuis la clé USB branchée sur le boîtier.
- [ ] **Éteindre proprement** le boîtier (le geste du petit bouton), et le rallumer, en constatant que son texte revient tout seul.

### O.6 — Où poser le matériel sur un plateau

- Le boîtier a un **petit ventilateur audible** : posez-le **à un ou deux mètres du micro** et hors du champ de la caméra.
- **Jamais dans un sac fermé, jamais en plein soleil** : enfermé, il chauffe et ralentit. Laissez ses ouvertures dégagées.
- Prévoyez **un support pour l'écran 7 pouces** (petit trépied de table, pince, ou bras) : rien de tel n'est fourni dans le kit. Réglez-le **à hauteur des yeux, juste sous l'axe de la caméra**.
- **Vérifiez ce placement pendant la répétition générale, avec le journaliste.**

### O.7 — L'électricité sur un tournage

- Il faut **au moins deux prises secteur** : une pour le boîtier, une pour l'écran (plus une troisième si le téléphone doit rester en charge).
- **L'écran se branche sur sa propre alimentation secteur**, jamais sur un port USB du boîtier : cela provoquerait des baisses de tension et des redémarrages inopinés.
- **Scotchez au gaffer** le câble d'alimentation au pied de la table et au sol. La prise USB-C ne se verrouille pas : **un pied dans le câble coupe le courant net**, avec le risque d'abîmer la carte mémoire.
- Ne faites jamais passer les câbles là où l'équipe circule.

### O.8 — Les habitudes de préparation à lui recommander

- Préparer les textes en **.docx** (Word ou LibreOffice) : c'est le format qui passe le mieux — léger, paragraphes propres, titres conservés. **Éviter les PDF**, et surtout les PDF scannés.
- Donner aux fichiers des **noms simples** (lettres, chiffres, espaces, tirets) : ce nom vient automatiquement remplir le champ **Titre** de la télécommande, et c'est sous ce nom que le texte sera rangé dans « Mes textes enregistrés ». **Il n'apparaît pas sur le grand écran.**
- **Toujours remplir le champ Titre** avant d'enregistrer.
- Vérifier **avant** le tournage qu'aucun document n'est protégé par mot de passe.
- Préparer une **petite clé USB dédiée**, avec les textes du jour **à la racine, c'est-à-dire visibles dès l'ouverture de la clé**, comme roue de secours : la clé, elle, ne demande **aucun réseau**.
- **Garder une copie des textes ailleurs** (mail, ordinateur) : **la bibliothèque du boîtier n'est pas une sauvegarde**, et la suppression d'un texte y est immédiate et définitive.
- **De temps en temps**, faire recopier par un dépanneur le dossier `scripts` du boîtier (tous les textes enregistrés) et le fichier `state.json` (les réglages) sur une clé USB — ou refaire une carte de secours à jour.
- **Tester les pédales avant chaque tournage**, et non au moment de tourner.

---

> **📘 Les trois documents du projet, et à qui chacun s'adresse.**
> - **`MISE-EN-ROUTE.md`** (ce document) : pour **vous**, la personne qui installe
>   le boîtier. Une seule fois.
> - **`MODE-EMPLOI.md`** : pour **le journaliste**, tous les jours. À imprimer et
>   à remettre avec le matériel, fiche découpée et collée sur le boîtier.
> - **`PROCEDURE-INSTALLATION.md`** (et sa version imprimable
>   `Procedure-Installation-Prompteur.pdf`) : pour **un dépanneur informatique** —
>   commandes exactes, détail de ce que fait le programme d'installation,
>   dépannage avancé.
>
> Le fichier **`README.md`** présente quant à lui le projet dans son ensemble
> ainsi que la liste du matériel.
