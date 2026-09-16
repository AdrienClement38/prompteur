# Se connecter au boîtier à distance

*Pour vous, pas pour le journaliste. Objectif : prendre la main sur le boîtier depuis votre
ordinateur, sans lui demander de toucher à un clavier.*

> **📍 La condition à connaître avant tout : être sur le même réseau.** Ce guide permet de se
> connecter depuis un ordinateur relié **à la même box** que le boîtier, ou au **WiFi du
> boîtier lui-même**. **Depuis un autre endroit — de chez vous si le boîtier est chez le
> journaliste — ça ne marche pas**, et ce n'est pas une panne : la box du journaliste bloque
> les connexions qui viennent de l'extérieur, comme toutes les box. Voir la dernière partie,
> « Depuis un autre endroit ».

---

## Pourquoi ça ne marchait pas

**Raspberry Pi OS est livré avec SSH désactivé.** Il n'y avait donc rien à joindre, quelle
que soit la façon de s'y prendre. Ce n'était ni le câble, ni le pare-feu du boîtier — celui-ci
ne ferme que le port du prompteur, jamais celui de SSH.

`install/setup.sh` l'active désormais, installe le service de nom réseau, et donne au
boîtier un nom stable : **`prompteur`**. Il faut donc **relancer ce script une fois** sur le
boîtier pour que l'accès devienne possible (c'est l'étape 4 de `MISE-A-JOUR.md`).

---

## Les deux chemins, du plus sûr au plus pratique

### Chemin n° 1 — par le WiFi du boîtier *(marche toujours, même sans internet)*

C'est le plus fiable : **l'adresse ne change jamais**, aucune box, aucun routeur.

1. Sur votre ordinateur, connectez-vous au WiFi **`Prompteur`** *(mot de passe : la fiche
   collée au dos du boîtier)*.
2. Ouvrez un terminal — sur Windows, **PowerShell** suffit, rien à installer.
3. Tapez, en remplaçant `nom` par le nom du compte du Raspberry :

```bash
ssh nom@10.42.0.1
```

> 💡 **Vous ne connaissez pas le nom du compte ?** C'est celui choisi au premier démarrage
> du Raspberry. `install/setup.sh` l'affiche à la ligne `==> Utilisateur:`. Sur le boîtier,
> une fenêtre noire (**Ctrl + Alt + T**) l'affiche aussi, à gauche de l'invite.

### Chemin n° 2 — par le câble Ethernet *(si le boîtier est relié à votre box)*

```bash
ssh nom@prompteur.local
```

Le nom `prompteur.local` évite d'avoir à connaître l'adresse : celle que distribue la box
change d'un rebranchement à l'autre, le nom non. Il fonctionne depuis **Windows 10 et 11,
macOS et Linux** sans rien installer.

> 🆘 **Si `prompteur.local` est introuvable**, c'est que le nom réseau n'est pas encore en
> place — le boîtier n'a pas encore rejoué `setup.sh`. Utilisez alors le chemin n° 1, ou
> l'adresse numérique : sur l'écran du prompteur, la touche **i** affiche l'adresse du
> boîtier.

---

## La première connexion

La toute première fois, l'ordinateur affiche un avertissement de ce genre :

```
The authenticity of host 'prompteur.local' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxx.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**C'est normal.** Répondez `yes`, puis tapez le mot de passe du compte. **Rien ne s'affiche
pendant que vous tapez le mot de passe** — ni étoiles, ni points. C'est voulu.

**✅ Ce que vous devez voir ensuite :** une invite du type `nom@prompteur:~ $`. Vous êtes sur
le boîtier.

Pour en sortir : `exit`.

---

## Ce que vous pourrez faire de là

| Ce que vous voulez | La ligne à taper |
|---|---|
| Installer une mise à jour | `cd ~/prompteur && git pull && sudo systemctl restart prompteur` |
| Voir si le serveur tourne | `systemctl status prompteur` |
| Lire les dernières erreurs | `journalctl -u prompteur -n 50 --no-pager` |
| Retrouver le mot de passe WiFi | `sudo nmcli -s -g 802-11-wireless-security.psk connection show Prompteur` |
| Voir les adresses du boîtier | `hostname -I` |
| Redémarrer le boîtier | `sudo reboot` |

> ⚠️ **Ce que SSH ne fait pas : voir l'écran.** Vous pilotez le système, pas l'affichage. Pour
> relancer le prompteur à l'écran depuis SSH, il faut passer par son script :
> ```bash
> ~/prompteur/install/kiosk.sh --restart
> ```

---

## Si ça ne marche toujours pas

Dans l'ordre, la première ligne qui répond « non » est la cause.

| Vérification | La commande, sur le boîtier | Réponse attendue |
|---|---|---|
| **1.** SSH tourne-t-il ? | `systemctl is-active ssh` | `active` |
| **2.** Le nom est-il posé ? | `hostname` | `prompteur` |
| **3.** Le service de nom tourne-t-il ? | `systemctl is-active avahi-daemon` | `active` |
| **4.** Quelle adresse a le boîtier ? | `hostname -I` | une ou deux adresses |

**Si la n° 1 répond autre chose qu'`active`** — activez SSH à la main, une fois :

```bash
sudo raspi-config
```

*Interface Options* → *SSH* → *Yes*. Puis relancez `./install/setup.sh`.

> 📌 **Deux causes fréquentes, côté votre ordinateur et non côté boîtier :**
> - **Vous n'êtes pas sur le même réseau.** Le chemin n° 2 exige que votre PC et le boîtier
>   soient reliés à **la même box**. Si votre PC est en WiFi et le boîtier en Ethernet sur
>   cette box, c'est bon ; s'ils sont sur deux réseaux différents, rien ne passera.
> - **Vous êtes resté connecté au WiFi `Prompteur`.** Ce réseau n'a pas internet et ne mène
>   qu'au boîtier : `prompteur.local` n'y répond pas, mais `10.42.0.1` oui.

---

## Depuis un autre endroit

**Avec ce qui est en place aujourd'hui : non.** Tout ce qui précède suppose d'être sur le même
réseau que le boîtier. Depuis chez vous, alors que le boîtier est chez le journaliste, votre
ordinateur ne le trouve pas : la box du journaliste refuse les connexions qui viennent
d'internet. C'est son rôle, et c'est aussi ce qui protège le boîtier.

Pour passer au travers, il faut une **étape de plus** — un service qui établit la liaison
depuis le boîtier vers l'extérieur, là où la box laisse passer. Elle n'est pas en place :
elle demande de créer un compte, et elle change une règle de départ du projet (un boîtier
qui ne dépend de personne). C'est donc une décision à prendre, pas un réglage à faire en
passant.

> 💡 **En attendant**, il existe une solution qui ne demande rien : **demander au
> journaliste de brancher le câble Ethernet et d'appeler**. Vous le guidez au téléphone pour
> les deux lignes de mise à jour, ou vous passez en personne.

---

## Un mot sur la sécurité

Le boîtier autorise son utilisateur à lancer n'importe quelle commande en administrateur
**sans redemander de mot de passe** — c'est ce qui permet à l'installation de se dérouler
sans intervention. Conséquence directe : **qui obtient le mot de passe du compte obtient tout
le boîtier.**

Deux précautions qui coûtent une minute :

- **Un vrai mot de passe de compte**, pas `raspberry`. À changer sur le boîtier avec
  `passwd`.
- **Le câble Ethernet ne reste branché que le temps utile.** Débranché, le boîtier n'est
  joignable que par son propre WiFi, protégé en WPA2 — et c'est son mode de travail normal.

---

*Voir aussi : `MISE-A-JOUR.md` (installer les nouveautés sur le boîtier),
`MISE-EN-ROUTE.md` (installation complète depuis zéro) et `PIEGES.md`.*
