# Sauvegarder et restaurer le boîtier

*Document technique, à l'usage de la personne qui entretient le boîtier.*
*Il sert avant toute modification du système — et le jour où quelque chose casse.*

---

## En une phrase

**Une seule chose est irremplaçable : les textes du journaliste et ses réglages.**
Tout le reste — le système, le logiciel, la configuration réseau — se **reconstruit à
l'identique en 45 minutes** à partir de GitHub et de `install/setup.sh`.

C'est ce qui rend le bricolage sans danger : on sauvegarde le petit (quelques kilo-octets,
trente secondes), et on accepte de refaire le gros si besoin.

| | Où c'est | Irremplaçable ? |
|---|---|---|
| Textes enregistrés | `~/prompteur/scripts/*.txt` | ✅ **oui** — n'existe nulle part ailleurs |
| Texte affiché + réglages | `~/prompteur/state.json` | ✅ **oui** — se reconstitue à la main, mais c'est fastidieux |
| Mot de passe WiFi du boîtier | dans NetworkManager | ⚠️ récupérable (voir annexe A), mais à noter |
| Système, logiciel, pare-feu, kiosque | partout | ❌ non — `git clone` + `setup.sh` |
| Fichier de démarrage `config.txt` | `/boot/firmware/config.txt` | ⚠️ à copier **avant** d'y toucher |

---

## Étape 0 — Accéder à la fenêtre noire

Le boîtier démarre directement sur le prompteur, en plein écran. Pour taper des commandes :

- [ ] **1.** Branchez un **clavier USB** sur le boîtier.
- [ ] **2.** Appuyez sur **Alt + F4** : le prompteur se ferme, le bureau apparaît.
- [ ] **3.** Appuyez sur **Ctrl + Alt + T** : la fenêtre noire s'ouvre.

> 📌 **Pour revenir au prompteur** à la fin : tapez `sudo reboot`. Le boîtier redémarre et
> le prompteur se réaffiche tout seul. **Rien n'est perdu** en faisant cela.

> ⚠️ **Quand on tape un mot de passe, rien ne s'affiche à l'écran** — ni étoiles, ni points.
> C'est normal et voulu. Tapez à l'aveugle, puis Entrée.

---

## 1. La sauvegarde qui compte — textes et réglages

**Trente secondes. À faire avant toute modification, et de temps en temps par précaution.**

Cette commande rassemble tout ce qui est irremplaçable dans un seul fichier, daté du jour :

```bash
cd ~/prompteur && tar czf ~/prompteur-sauvegarde-$(date +%F).tar.gz --exclude='*.py' --exclude='*.sh' scripts state.json
```

*(Les deux `--exclude` laissent de côté les outils du logiciel rangés dans le même dossier :
restaurés par-dessus une version plus récente, ils bloqueraient la mise à jour suivante.)*

**Ce que vous devez voir :** rien du tout. Aucune réponse = réussi.

Vérifiez que le fichier existe bien :

```bash
ls -lh ~/prompteur-sauvegarde-*.tar.gz
```

**Ce que vous devez voir :** une ligne avec la date du jour et une taille de quelques kilo-octets.

### Le mettre à l'abri sur une clé USB

Un fichier de sauvegarde resté sur la carte SD ne sert à rien le jour où la carte est
effacée. **Sortez-le du boîtier.**

- [ ] **1.** Branchez une clé USB sur le boîtier, attendez 5 secondes.
- [ ] **2.** Trouvez son nom :

```bash
ls /media/$USER/
```

**Ce que vous devez voir :** le nom de la clé, par exemple `SANDISK` ou `USB-KEY`.

- [ ] **3.** Copiez-y la sauvegarde — **remplacez `NOM_DE_LA_CLE`** par ce que la commande
      précédente a affiché :

```bash
cp ~/prompteur-sauvegarde-*.tar.gz /media/$USER/NOM_DE_LA_CLE/ && sync
```

**Ce que vous devez voir :** rien. Le `sync` garantit que l'écriture est terminée avant de
retirer la clé — **ne la retirez pas avant que la commande soit revenue**.

> 💡 **Encore plus simple, sans clé USB :** le journaliste garde de toute façon une copie de
> ses textes dans ses mails ou sur son ordinateur. C'est déjà une sauvegarde. Cette procédure
> sert surtout à conserver **les réglages** et l'organisation de la bibliothèque.

---

## 2. Avant de bricoler le système — copier le fichier de démarrage

**À faire impérativement avant toute modification liée à un écran, un overlay, ou le
démarrage.** C'est ce fichier qui, mal rempli, laisse le boîtier sans affichage.

```bash
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.avant-ecran
```

**Ce que vous devez voir :** rien. Vérifiez :

```bash
ls -l /boot/firmware/config.txt*
```

**Ce que vous devez voir :** deux fichiers, `config.txt` et `config.txt.avant-ecran`.

> ✍️ **Notez aussi sur papier ce que vous ajoutez**, ligne par ligne. Une sauvegarde dit
> comment revenir en arrière ; elle ne dit pas ce que vous avez essayé.

---

## 3. La sauvegarde complète — l'image de la carte SD

C'est la ceinture **et** les bretelles : une copie de la carte entière, qui se remet en
place à l'identique. Elle demande **un ordinateur et un lecteur de carte**, et le boîtier
doit être éteint.

- [ ] **1.** Éteignez proprement le boîtier, débranchez, **sortez la carte micro-SD**.
- [ ] **2.** Insérez-la dans l'ordinateur (fente SD + adaptateur, ou lecteur USB).
- [ ] **3.** Sur **Windows** : installez **Win32 Disk Imager** (gratuit). Choisissez un
      fichier de destination (par exemple `prompteur-complet.img`), sélectionnez la carte,
      puis cliquez sur **« Read »** *(et non « Write » — « Write » écraserait la carte)*.
- [ ] **4.** Comptez 15 à 30 minutes. Le fichier obtenu fait la taille de la carte
      (32 Go), même si elle est presque vide.

> ⚠️ **Le piège :** dans Win32 Disk Imager, **« Read » sauvegarde**, **« Write » restaure**.
> Se tromper de bouton efface la carte. Lisez deux fois avant de cliquer.

> 💡 **Franchement, est-ce utile ici ?** Modérément. Restaurer cette image prend autant de
> temps que de tout réinstaller proprement depuis GitHub, et l'image vieillit à chaque mise
> à jour. **Elle n'a de sens que pour figer un état dont on est sûr**, juste avant une
> manipulation risquée, quand on veut pouvoir revenir *exactement* au même point.

---

## 4. Restaurer

### 4.1 — Récupérer les textes et les réglages

La sauvegarde est un fichier `.tar.gz`. Sur un boîtier fraîchement réinstallé :

- [ ] **1.** Branchez la clé USB contenant la sauvegarde, attendez 5 secondes.
- [ ] **2.** Copiez-la dans le dossier personnel — **remplacez `NOM_DE_LA_CLE`** :

```bash
cp /media/$USER/NOM_DE_LA_CLE/prompteur-sauvegarde-*.tar.gz ~/
```

- [ ] **3.** Remettez en place **la plus récente** des sauvegardes :

```bash
cd ~/prompteur && tar xzf "$(ls -t ~/prompteur-sauvegarde-*.tar.gz | head -1)" --exclude='*.py' --exclude='*.sh'
```

- [ ] **4.** Redémarrez le logiciel pour qu'il relise l'état restauré :

```bash
sudo systemctl restart prompteur
```

**Ce que vous devez voir :** rien à l'écran de la fenêtre noire. Rouvrez la page Settings
depuis un téléphone : vos textes sont de retour dans « Mes textes enregistrés ».

### 4.2 — L'écran reste noir après une modification du démarrage

C'est le cas le plus fréquent quand on bricole un écran. **Le boîtier n'est pas mort** : il
démarre, le serveur tourne, le WiFi « Prompteur » se crée. Seul l'affichage manque.

**Méthode A — depuis le boîtier lui-même** (si vous avez un clavier et que le bureau
répond quand même) :

```bash
sudo cp /boot/firmware/config.txt.avant-ecran /boot/firmware/config.txt && sudo reboot
```

**Méthode B — depuis un autre ordinateur, par le réseau.** Connectez l'ordinateur au WiFi
« Prompteur », puis (en remplaçant `real` par le nom d'utilisateur du boîtier) :

```bash
ssh real@10.42.0.1
```

…puis tapez la commande de la méthode A.

**Méthode C — le filet qui marche toujours, sans écran ni réseau.** Éteignez, sortez la
carte SD, mettez-la dans un PC : **la partition de démarrage est lisible sous Windows**.
Ouvrez `config.txt` avec le **Bloc-notes**, supprimez les lignes ajoutées (ou recopiez le
contenu de `config.txt.avant-ecran`), enregistrez, remettez la carte.

> 📌 **C'est cette méthode C qui rend le bricolage sûr.** Quoi qu'il arrive au fichier de
> démarrage, on peut toujours le corriger depuis n'importe quel ordinateur, sans réseau et
> sans écran.

### 4.3 — Tout refaire à zéro

Si le système est trop abîmé, on reflashe et on recommence : voir **MISE-EN-ROUTE.md**
(45 min à 1 h). Pensez à **réutiliser le même mot de passe WiFi** qu'avant, pour que la
fiche collée sur le boîtier reste valable — et à restaurer les textes (§ 4.1) à la fin.

---

## 5. Mettre à jour le logiciel sans rien perdre

Le boîtier doit être connecté temporairement à Internet (câble Ethernet).

```bash
cd ~/prompteur && git pull && sudo reboot
```

Les textes et les réglages **ne sont pas touchés** : `scripts/` et `state.json` sont exclus
du dépôt, une mise à jour ne peut pas les écraser.

> 🆘 **Si `git pull` refuse en parlant de « local changes »** — c'est un faux conflit sans
> gravité (une permission de fichier qui a changé). On jette la modification et on
> recommence :
> ```bash
> git checkout -- install/ && git pull
> ```

---

## Annexe A — Retrouver le mot de passe du WiFi « Prompteur »

Il n'est affiché qu'une fois, à l'installation. S'il a été perdu, il est encore lisible
depuis le boîtier :

```bash
sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur
```

**Ce que vous devez voir :** le mot de passe en clair. **Notez-le sur la fiche du boîtier.**

Pour le remplacer par un autre :

```bash
sudo nmcli connection modify Prompteur wifi-sec.psk "NOUVEAU_MOT_DE_PASSE" && sudo nmcli connection up Prompteur
```

⚠️ Tous les téléphones et ordinateurs déjà connectés devront **oublier le réseau** et s'y
reconnecter avec le nouveau mot de passe. Et la fiche collée sur le boîtier devient fausse :
corrigez-la aussitôt.

---

## Annexe B — Faire exécuter ces commandes à distance

Situation courante : le boîtier est chez le journaliste, et c'est lui qui doit taper.

- **Envoyez les commandes par écrit** (message, mail) plutôt que de les dicter : une
  commande dictée au téléphone se déforme, surtout les tirets et les barres obliques.
- **Une commande à la fois.** Demandez-lui de renvoyer ce qui s'affiche **avant** de passer
  à la suivante — une photo de l'écran suffit, et vaut mieux qu'une description.
- **Prévenez-le pour le mot de passe** : rien ne s'affiche pendant la frappe. Sans
  l'avertissement, il croit que le clavier ne répond pas.
- **Rappelez-lui Alt + F4 puis Ctrl + Alt + T** pour ouvrir la fenêtre noire, et
  `sudo reboot` pour retrouver son prompteur à la fin.
- **Faites-lui faire la sauvegarde du § 1 en premier**, toujours. C'est trente secondes, et
  ça transforme n'importe quelle bêtise ultérieure en simple perte de temps.

---

*Le Prompteur — documentation d'entretien. Voir aussi `MISE-EN-ROUTE.md` (installation
complète), `MODE-EMPLOI.md` (usage quotidien) et `PROCEDURE-INSTALLATION.md` (version
technique condensée).*
