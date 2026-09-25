# Mettre le boîtier à jour

*Le boîtier est déjà installé et en service. Il s'agit seulement d'y installer ce qui a
été ajouté depuis.*

**30 minutes, une seule fois.** Quatre lignes à recopier, puis une liste à cocher.

> 🎁 **Ce que vous y gagnez :** le boîtier devient joignable depuis un ordinateur **relié à
> la même box que lui**, sans toucher à son clavier. *(Depuis un autre endroit, il faut une
> étape de plus : voir `ACCES-A-DISTANCE.md`.)*

---

## Avant de commencer

**Sur la table :** le boîtier, son écran, son alimentation · un **clavier USB** · un
**câble Ethernet** relié à votre box · votre téléphone · un **document Word** et un **PDF**
pour l'essai final.

**Deux renseignements à avoir sous la main** — cherchez-les maintenant, pas au milieu de la
procédure :

| | Où le trouver |
|---|---|
| **Le mot de passe du WiFi `Prompteur`** | Sur la **fiche collée au dos du boîtier** (pour l'essai final) |
| **Le nom du compte du Raspberry** | Dans la fenêtre noire, écrit juste avant le `@` |

> **Si la fiche du boîtier est vide**, profitez-en : après l'étape 1, cette ligne affiche
> le mot de passe du WiFi. **Notez-le sur la fiche.**
> ```bash
> sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur
> ```

> **⚠️ Pas la veille d'un tournage.** Rien n'est risqué — textes et réglages sont conservés
> — mais choisissez un jour où vous pouvez tout essayer deux fois.

---

## Étape 1 — Ouvrir la fenêtre noire

1. Branchez le **clavier** et le **câble Ethernet**.
2. Allumez le boîtier, attendez que le prompteur s'affiche.
3. **Alt + F4** *(le prompteur se ferme, le bureau apparaît)*.
4. **Ctrl + Alt + T** *(la fenêtre noire s'ouvre)*.

📸 **Notez le nom du compte** : c'est ce qui est écrit avant le `@`.

> **⚠️ Quand le boîtier demande votre mot de passe, rien ne s'affiche** — ni étoiles, ni
> points. C'est normal. Tapez à l'aveugle, puis **Entrée**. Valable pour toute la suite.

---

## Étape 2 — Récupérer les nouveautés

```bash
cd ~/prompteur && git pull
```

**✅ Attendu :** une liste de fichiers avec des `+` et des `-`, puis `xx files changed`.

> **🆘 `Your local changes would be overwritten`** — sans gravité. Tapez la ligne suivante,
> puis reprenez celle du dessus :
> ```bash
> git checkout -- install/
> ```
>
> **🆘 `Already up to date.`** — arrêtez-vous et signalez-le.

---

## Étape 3 — Redémarrer le logiciel

```bash
sudo systemctl restart prompteur
```

**✅ Attendu :** rien du tout. Aucune réponse = réussi.

---

## Étape 4 — Installer les nouveautés du boîtier

Cette ligne met à jour ce qui est installé sur le boîtier lui-même (service, WiFi,
accès à distance, icônes). **Le mot de passe du WiFi est conservé.**

```bash
./install/setup.sh
```

**✅ Attendu :** deux à trois minutes de lignes qui défilent, puis un **cadre entouré de
`=`** annonçant « Installation terminée ». La ligne du mot de passe se termine par
**« conservé (inchangé) »**.

📸 **Notez les deux lignes commençant par `ssh`.**

> **🛑 Si la ligne du mot de passe dit « NOUVEAU »** (le boîtier n'en avait pas) : c'est
> celui-là qu'il faut maintenant pour le WiFi. **Recopiez-le sur la fiche** avant d'aller
> plus loin.

> **🆘 Si une ligne dit que SSH n'a pas démarré** — sans conséquence pour le prompteur.
> Tapez `sudo raspi-config`, allez dans *Interface Options* → *SSH* → *Yes*, puis relancez
> la ligne ci-dessus.

---

## Étape 5 — Redémarrer le boîtier

```bash
sudo reboot
```

**✅ Attendu :** l'écran s'éteint, la framboise apparaît, puis en 30 à 60 secondes **le
prompteur revient tout seul**.

**Gardez le câble Ethernet branché** pour l'essai suivant.

---

## Étape 6 — Vérifier

**Arrêtez-vous à la première case qui ne se coche pas** plutôt que de continuer.

**Le boîtier**

- [ ] Le prompteur s'affiche **tout seul** au démarrage, les **pédales** font défiler
- [ ] **Échap** demande « Quitter la vue Journaliste ? », un second **Échap** affiche la
      vue Settings sur le grand écran
- [ ] L'icône **« Le Prompteur »** est sur le bureau du Raspberry

**Le téléphone** *(WiFi `Prompteur`, puis `http://10.42.0.1:5000`)*

- [ ] La page s'ouvre : en haut, **Settings · Spectateur · ⏻ Veille**
- [ ] **« Écran journaliste »** → **Journaliste** : le prompteur revient sur le grand écran,
      et ce bouton devient bleu
- [ ] Onglet **Contrôle** → **Lecture** : le texte défile ; **Pause** : il s'arrête
- [ ] **⏻ Veille** → **« Mettre en veille »** : le grand écran s'éteint ; **« Rallumer »** le
      rallume
- [ ] Sélectionnez des mots, appuyez sur **G** : ils passent en gras **sous vos yeux**
- [ ] **« Envoyer à l'écran »** : le gras apparaît aussi sur le grand écran
- [ ] Tapez une ligne commençant par `- ` *(tiret puis espace)*, envoyez : elle s'affiche
      **avec une puce**
- [ ] Onglet **Réglages** → **Pédales** : il y a bien **trois modes**

**Les documents**

- [ ] Importez le **document Word** : titres, gras et puces se retrouvent à l'écran
- [ ] Importez le **PDF** : même chose
- [ ] Importez une **photo** : elle est **refusée avec un message**

**L'accès à distance** *(depuis votre ordinateur, sur la même box — PowerShell suffit)*

```bash
ssh nom@prompteur.local
```

- [ ] Une session s'ouvre : `nom@prompteur:~ $`

> **🆘 `prompteur.local` introuvable ?** Connectez votre ordinateur au WiFi `Prompteur` et
> essayez `ssh nom@10.42.0.1` — cette adresse-là ne change jamais.

**Toutes les cases cochées ?** C'est fini. Débranchez le câble et le clavier.

---

## Si ça coince

| Ce que vous constatez | Quoi faire |
|---|---|
| **Le prompteur ne revient pas** | Attendez **une minute complète**, puis rebranchez l'alimentation et recomptez une minute |
| **L'écran affiche l'ancienne version** | L'étape 3 a été oubliée : `sudo systemctl restart prompteur` |
| **Le téléphone refuse le mot de passe du WiFi** | Regardez la ligne du mot de passe dans le cadre de l'étape 4 ; ou retrouvez-le avec la commande de la page 1, et corrigez la fiche |
| **`ssh` : « Connection refused »** | `sudo raspi-config` → *Interface Options* → *SSH* → *Yes* |
| **`ssh` : « Could not resolve hostname »** | Votre ordinateur n'est pas sur le même réseau que le boîtier |
| **Rien ne va plus** | Débranchez, 10 secondes, rebranchez, comptez une minute. Votre texte est conservé |

> **🔙 Revenir à la version d'avant cette mise à jour :**
> ```bash
> cd ~/prompteur && git reset --hard ORIG_HEAD && sudo reboot
> ```
> Textes et réglages ne sont pas touchés, et la mise à jour suivante (`git pull`) se fera
> normalement. **Une seule fois** : la relancer referait avancer le boîtier.

---

## Et ensuite

**Les mises à jour suivantes se font sans toucher au boîtier**, depuis un ordinateur relié
**à la même box que lui** :

```bash
ssh nom@prompteur.local
```
```bash
cd ~/prompteur && git pull && sudo reboot
```

*(La connexion se coupe au redémarrage : c'est normal. Une minute plus tard, le prompteur
est revenu, à jour.)*

**Ce qui a changé pour le journaliste** est expliqué dans **`MODE-EMPLOI.md`**, qui est à
jour : trois vues (Settings, Journaliste, Spectateur), veille, choix de ce qu'affiche le
grand écran, blocs « Info », mise en forme du texte, trois modes de pédales.

**Les autres documents :** `ACCES-A-DISTANCE.md` (prendre la main sur le boîtier),
`SAUVEGARDE-ET-RESTAURATION.md` (revenir en arrière), `ECRAN-TACTILE.md` (le petit écran),
`MISE-EN-ROUTE.md` (installation complète depuis zéro — vous n'en avez plus besoin).
