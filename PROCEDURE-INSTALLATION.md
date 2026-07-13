# Procédure technique d'installation — Le Prompteur

Mise en service complète **à partir du matériel neuf**, jusqu'à un boîtier
opérationnel qui démarre tout seul sur le prompteur.

> 🖨️ **Version imprimable (à cocher sur le terrain)** : [Procedure-Installation-Prompteur.pdf](Procedure-Installation-Prompteur.pdf)

- **Durée** : 30 à 45 min.
- **Niveau** : sait ouvrir un terminal et taper quelques commandes.
- **Important** : Internet n'est nécessaire **qu'une seule fois**, pour l'installation.
  En fonctionnement, le boîtier est **100 % hors-ligne** (il crée son propre WiFi).

---

## 0. Matériel et prérequis

**Le boîtier (à assembler) :**
- [ ] Raspberry Pi 5 (idéalement le **kit** : Pi + alimentation USB‑C 27 W + boîtier + ventilateur + **carte micro‑SD** + **câble micro‑HDMI → HDMI**)
- [ ] Un **écran HDMI** (moniteur, ou l'écran tactile officiel Raspberry Pi)
- [ ] Un **pédalier USB programmable** (ex. PCsensor FS2020U)

**Uniquement pour l'installation (pas en usage courant) :**
- [ ] Un **clavier + une souris USB** branchés sur le Pi (ou un accès **SSH** depuis un autre ordinateur)
- [ ] Un **accès Internet temporaire** : **câble Ethernet recommandé** (le plus simple), ou le WiFi de votre local
- [ ] Un ordinateur avec **lecteur de carte SD** — *seulement si la carte n'est pas déjà « pré‑installée »* (fente SD du PC + l'**adaptateur micro‑SD → SD** fourni avec la carte, ou un petit **lecteur USB** à quelques euros)

> 💡 **Résumé express** (pour les pressés, une fois le Pi démarré et connecté à Internet) :
> ```bash
> sudo apt update && sudo apt full-upgrade -y && sudo apt install -y git
> git clone https://github.com/AdrienClement38/prompteur.git
> cd prompteur && chmod +x install/setup.sh && ./install/setup.sh
> sudo reboot
> ```
> …puis programmer les pédales et tester. Le détail complet suit.

---

## 1. Préparer la carte micro‑SD

**Deux cas de figure :**

- ✅ **Carte pré‑installée** (recommandé — l'option « carte SD pré‑installée Raspberry Pi OS » du kit) :
  **rien à faire ici, aucun ordinateur nécessaire.** Insérez la carte dans le Pi et **passez à l'étape 2**.
- 🖥️ **Carte vierge** : à préparer **une seule fois depuis un ordinateur**. Pour y insérer la micro‑SD,
  utilisez la **fente SD** du PC avec l'**adaptateur micro‑SD → SD** (généralement fourni avec la carte),
  ou un petit **lecteur USB de carte**. Ensuite, la carte **reste dans le boîtier**.

### Préparer une carte vierge (« flasher » la carte)

> **« Flasher » une carte**, c'est y copier le système d'exploitation (Raspberry Pi OS) — un peu
> comme installer Windows sur un ordinateur. On le fait **une seule fois**, avec l'outil **gratuit et
> officiel « Raspberry Pi Imager »**. Comptez ~10 minutes.

1. **Installer l'outil.** Sur votre ordinateur (Windows ou Mac), allez sur **raspberrypi.com/software**,
   téléchargez **Raspberry Pi Imager** et installez‑le.
2. **Insérer la carte** micro‑SD dans le lecteur du PC (fente SD + adaptateur, ou lecteur USB).
3. **Ouvrir Raspberry Pi Imager** et remplir les **3 gros boutons** de l'écran principal :
   - **« CHOISIR L'APPAREIL »** → *Raspberry Pi 5*
   - **« CHOISIR L'OS »** → *Raspberry Pi OS (64‑bit)* (la version recommandée, **avec bureau**)
   - **« CHOISIR LE STOCKAGE »** → **votre carte SD**
     > ⚠️ Vérifiez bien que vous sélectionnez la **carte SD**, et pas un disque de votre PC :
     > **tout son contenu sera effacé**.
4. Cliquez sur **« SUIVANT »**, puis sur **« MODIFIER LES RÉGLAGES »** *(c'est ce qui pré‑configure le
   Pi pour qu'il fonctionne du premier coup, sans écran ni clavier si besoin)*. Renseignez :
   - **Nom d'hôte** : `prompteur`
   - **Nom d'utilisateur + mot de passe** → **notez‑les** (ils serviront à ouvrir le terminal)
   - Onglet **Services** : **cocher « Activer SSH »** (authentification par mot de passe)
   - **Langue / fuseau / clavier** : *France*
   - *(si vous n'utilisez pas Ethernet)* le **WiFi de votre local** (nom + mot de passe)

   Puis **« ENREGISTRER »**.
5. Cliquez **« OUI »** pour lancer l'écriture. Imager **copie le système puis le vérifie** (~5 à 10 min).
6. Au message **« Écriture réussie »**, **retirez la carte** du PC. Elle est prête → passez à l'étape 2.

---

## 2. Premier démarrage du Raspberry Pi

1. Insérez la carte SD dans le Pi.
2. Branchez l'**écran** : câble **micro‑HDMI → HDMI** sur le port **HDMI0** du Pi (le plus proche de la prise d'alimentation USB‑C).
3. Branchez le **clavier + souris** (ou préparez un accès SSH).
4. **Si vous installez par Ethernet** : branchez le câble réseau maintenant.
5. Branchez enfin l'**alimentation** : le Pi démarre sur le bureau.
6. Terminez l'assistant de premier démarrage si besoin (clavier FR, réseau) et **vérifiez que Internet fonctionne** (ouvrez une page web).

---

## 3. Deux réglages système importants

Ouvrez un terminal et lancez :

```bash
sudo raspi-config
```

1. **Démarrage automatique du bureau** *(indispensable pour que le prompteur s'affiche seul)* :
   `System Options` → `Boot / Auto Login` → **Desktop Autologin**
2. **Système graphique X11** *(recommandé — le mode kiosque est plus fiable qu'en Wayland)* :
   `Advanced Options` → `Wayland` → **X11**

Choisissez **Finish**, mais **ne redémarrez pas encore** (on le fera après l'installation).

---

## 4. Récupérer le logiciel du prompteur

Toujours dans le terminal (Internet requis) :

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git
git clone https://github.com/AdrienClement38/prompteur.git
cd prompteur
```

> **Sans Internet sur le Pi ?** Copiez le dossier `prompteur` depuis une clé USB, puis `cd` dedans.

---

## 5. Lancer l'installation automatique

```bash
chmod +x install/setup.sh
./install/setup.sh
```

Le script (avec `sudo` en interne) réalise **tout** :
- installe les dépendances (Flask, waitress, Chromium, antiword, unclutter, nftables, + `striprtf`/`pypdf`) ;
- crée le **service** qui lance le serveur au démarrage ;
- crée le **point d'accès WiFi** « Prompteur » (adresse `10.42.0.1`) ;
- pose un **pare‑feu** (le service n'est joignable que via ce WiFi) ;
- configure le **démarrage en mode kiosque** (Chromium plein écran).

⚠️ **Notez le mot de passe WiFi affiché à la fin** — il est **généré aléatoirement** (unique par boîtier).
Pour imposer le vôtre, relancez plutôt : `WIFI_PASS="votre_mot_de_passe" ./install/setup.sh`

Puis redémarrez :

```bash
sudo reboot
```

---

## 6. Vérifier le démarrage

Après le redémarrage, **l'écran doit afficher le prompteur tout seul** (fond noir, message d'accueil, et l'adresse à taper sur un PC/tablette).

Si l'écran reste noir → voir **Dépannage** (annexe A).

---

## 7. Configurer les pédales

Branchez le **pédalier USB** sur le Pi. Objectif : pédale **droite = touche Flèche bas**, pédale **gauche = touche Flèche haut**.

Deux méthodes, au choix :

- **A) Programmer le pédalier** (recommandé pour du matériel type PCsensor) : avec le petit logiciel du fabricant (sur un PC), assignez `Flèche bas` à la pédale droite et `Flèche haut` à la pédale gauche.
- **B) Adapter le logiciel au pédalier** : sur la télécommande (voir étape 8) → onglet **Réglages** → section **Pédales** → cliquez dans le champ « pédale droite », **appuyez sur la pédale** (elle est « apprise »), idem pour la gauche.

**Test** : maintenez la pédale droite → le texte défile ; relâchez → il s'arrête ; pédale gauche → il recule.

---

## 8. Connecter un téléphone / PC et tester

1. Sur le téléphone : rejoignez le WiFi **« Prompteur »** (mot de passe de l'étape 5).
2. Ouvrez le navigateur sur **http://10.42.0.1:5000**
3. Onglet **Texte** : collez un texte, **ou** importez un fichier (Word `.docx`, PDF, `.odt`, RTF, `.txt`) → **« Envoyer à l'écran »**.
4. Vérifiez le **défilement aux pédales** et les **réglages** (taille, vitesse, couleurs, miroir).

---

## 9. (Optionnel) Écran régie / spectateur

Sur un autre appareil connecté au WiFi « Prompteur » (le **PC de la régie**, par exemple), ouvrez :

```
http://10.42.0.1:5000/view
```

Il **suit l'écran principal en temps réel** (lecture seule). Plusieurs spectateurs possibles.

---

## 10. Checklist de validation

- [ ] Le prompteur s'affiche **seul** au démarrage du boîtier
- [ ] Le réseau WiFi **« Prompteur »** apparaît ; la connexion fonctionne
- [ ] **http://10.42.0.1:5000** s'ouvre depuis le téléphone
- [ ] Un texte envoyé **apparaît à l'écran**
- [ ] Pédales : **droite = avance**, **gauche = recule**, relâché = stop
- [ ] Un **.docx** importé garde ses **titres** (gros/gras) et ses paragraphes
- [ ] **http://10.42.0.1:5000/view** suit l'écran principal en direct
- [ ] Après extinction/rallumage, tout revient automatiquement

---

## Annexe A — Dépannage

| Problème | Commande / action |
|---|---|
| État du serveur | `sudo systemctl status prompteur` |
| Journaux en direct | `journalctl -u prompteur -f` |
| Redémarrer le serveur | `sudo systemctl restart prompteur` |
| Le WiFi « Prompteur » n'apparaît pas | `sudo nmcli connection up Prompteur` |
| Vérifier le pare‑feu | `sudo nft list table inet prompteur` |
| **Écran noir** (kiosque non lancé) | Vérifier que **Desktop Autologin** et **X11** sont bien activés (étape 3) ; `cat ~/.config/labwc/autostart` ; sinon relancer `./install/setup.sh` |
| Chromium introuvable | `sudo apt install -y chromium-browser` (ou `chromium`) |
| Changer le mot de passe WiFi | `sudo nmcli connection modify Prompteur wifi-sec.psk "NOUVEAU_MDP"` puis `sudo nmcli connection up Prompteur` |
| Retrouver l'adresse à l'écran | sur l'écran du boîtier, appuyer sur la touche **i** |

## Annexe B — Mettre à jour le logiciel plus tard

Nécessite un accès Internet temporaire (Ethernet, ou rebrancher un WiFi avec Internet) :

```bash
cd ~/prompteur
git pull
sudo systemctl restart prompteur
```

*(Sans Internet : recopier le dossier mis à jour via clé USB, puis `sudo systemctl restart prompteur`.)*

## Annexe C — Rappel des rôles réseau

| Adresse | Usage |
|---|---|
| `http://10.42.0.1:5000/` | Télécommande / import (téléphone, PC) |
| `http://10.42.0.1:5000/display` | Écran **meneur** (piloté aux pédales) — affiché en kiosque sur le boîtier |
| `http://10.42.0.1:5000/view` | Écran **spectateur / régie** (suit le meneur en direct) |

---

*Le Prompteur — logiciel libre, hors‑ligne. Code : github.com/AdrienClement38/prompteur*
