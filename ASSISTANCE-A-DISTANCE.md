# Assistance à distance

*Accéder au boîtier depuis n'importe où — terminal et écran, dans un navigateur — dès qu'il
est branché à internet et que le journaliste l'autorise.*

> **🔒 Le principe.** L'assistance est **coupée par défaut**. C'est le journaliste qui l'ouvre
> et la referme, depuis le boîtier. **Tant qu'elle est ouverte, la personne qui aide voit
> l'écran, y compris le texte du prompteur.**

---

## Une seule fois — relier le boîtier à votre compte

### 1. Vous : créer votre compte *(2 minutes)*

Créez un **compte Raspberry Pi**, gratuit, sur **id.raspberrypi.com**. C'est ce compte qui vous
donnera accès au boîtier.

### 2. Le journaliste : installer l'assistance *(5 minutes)*

Boîtier allumé, **clavier** et **câble Ethernet** branchés :

1. **Alt + F4**, puis **Ctrl + Alt + T** *(la fenêtre noire s'ouvre)*.
2. Recopiez, puis **Entrée** :

```bash
cd ~/prompteur && git pull && ./install/assistance.sh installer
```

**✅ Attendu :** `Icônes « Assistance à distance » posées sur le bureau`.

3. Sur le bureau, double-cliquez **« Assistance à distance — activer »**.
4. Une fenêtre affiche **un lien**. **Envoyez-le vous** (photo ou SMS), sans fermer la fenêtre.

### 3. Vous : approuver

Ouvrez le lien reçu sur votre ordinateur, connectez-vous avec votre compte, validez. **La
fenêtre du boîtier affiche alors « ASSISTANCE ACTIVÉE ».** C'est fini pour la mise en place.

---

## À chaque fois — l'assistance au quotidien

| | Le journaliste | Vous |
|---|---|---|
| **1** | Branche le **câble Ethernet** | |
| **2** | Double-clique **« Assistance à distance — activer »** | |
| **3** | Vous appelle | Ouvrez **connect.raspberrypi.com**, choisissez le boîtier |
| **4** | | **Screen sharing** pour l'écran, **Remote shell** pour le terminal |
| **5** | Double-clique **« Assistance à distance — couper »** quand vous avez fini | |

> 💡 Pour atteindre le bureau, le journaliste quitte le prompteur avec **Échap** (deux fois), ou
> **Alt + F4**. L'icône **« Le Prompteur »** le rouvre ensuite.

---

## Si ça coince

| Ce que vous constatez | Pourquoi, et quoi faire |
|---|---|
| **« Le boîtier n'a pas internet »** | Le câble Ethernet n'est pas branché, ou la box ne répond pas. Attendez une minute après l'avoir branché |
| **« Raspberry Pi Connect n'est pas installé »** | Dans la fenêtre noire, câble branché : `sudo apt install -y rpi-connect`, puis redémarrer |
| **Le boîtier n'apparaît pas sur connect.raspberrypi.com** | L'assistance est coupée, ou le câble débranché. Faites refaire l'étape 2 |
| **Le lien a expiré avant d'être ouvert** | Relancez l'icône « activer » : un nouveau lien s'affiche |

Pour savoir où on en est, dans la fenêtre noire :

```bash
~/prompteur/install/assistance.sh etat
```

---

## Pourquoi un service extérieur

Le boîtier et votre ordinateur sont **chacun derrière une box**, et une box refuse les
connexions qui arrivent d'internet. Deux machines dans ce cas ne peuvent pas se joindre
directement, quel que soit le logiciel : il faut que **le boîtier appelle un relais** — ce que
sa box laisse passer, comme une page web — et que ce relais vous mette en relation.

Raspberry Pi Connect est ce relais : **officiel, gratuit, déjà installé** sur le boîtier, et
**rien à régler sur la box du journaliste**. L'alternative serait de louer et d'entretenir
votre propre serveur relais.

---

*Sur place, sur le même réseau que le boîtier, SSH direct reste possible sans rien de tout
cela : voir `ACCES-A-DISTANCE.md`.*
