# 🎬 Prompteur — téléprompteur à pédales, hors-ligne

Un boîtier **dédié** (Raspberry Pi) qui fait défiler ton texte à l'écran, piloté
aux **pédales** (gauche = reculer, droite = avancer). Tu importes ton texte
**depuis ton téléphone** (le boîtier crée son propre WiFi) ou **par clé USB**.
**Aucune connexion internet n'est nécessaire.**

---

## 1. Liste de courses (matériel)

| Élément | Rôle | Prix indicatif |
|---|---|---|
| **Raspberry Pi 5** (4 Go) ou **Pi 4** | Le cerveau du boîtier | ~60–70 € |
| Carte **microSD 32 Go** (classe A1/A2) | Le « disque dur » | ~8 € |
| Alimentation officielle USB-C | — | ~12 € |
| Boîtier + ventilateur | Protection | ~10 € |
| **Écran** : écran tactile officiel 7″ **ou** petit moniteur HDMI | Affiche le texte | ~60–70 € |
| **Pédalier USB programmable** (ex. PCsensor à 2–3 pédales) | Pédales gauche/droite | ~15–40 € |
| *(optionnel)* Vitre sans tain + support | Look « pro » face caméra | ~40–150 € |

> 💡 Les pédales doivent être **programmables pour envoyer des touches clavier**
> (flèche haut/bas, PageUp/PageDown, Espace…). C'est le cas de la plupart des
> pédales USB de transcription et des « page turners » pour musiciens.
> Par défaut : **pédale droite = Flèche bas**, **pédale gauche = Flèche haut**
> (réglable dans l'appli, avec « apprentissage » de la touche).

---

## 2. Tester le logiciel TOUT DE SUITE (sur ton PC, avant d'avoir le Pi)

Tu peux vérifier que tout fonctionne dans ton navigateur, sans matériel :

```bash
pip install flask
python server.py
```

Puis ouvre dans ton navigateur :

- **L'écran du prompteur** : http://localhost:5000/display
- **La télécommande / import** : http://localhost:5000/

Ouvre les deux dans deux onglets côte à côte : ce que tu envoies depuis la
télécommande apparaît sur l'écran. Sur l'écran, teste les touches :

| Touche | Effet |
|---|---|
| **Flèche bas** (maintenue) | avance (= pédale droite) |
| **Flèche haut** (maintenue) | recule (= pédale gauche) |
| **Espace** | lecture / pause automatique |
| **+ / −** | plus vite / moins vite |
| **M** | miroir (pour la vitre sans tain) |
| **F** | plein écran |
| **R** | retour au début |

> C'est juste pour l'aperçu : en vrai, le logiciel tournera sur le boîtier Pi,
> pas sur ton PC.

---

## 3. Installation sur le Raspberry Pi

1. **Prépare la carte SD** avec *Raspberry Pi Imager* → « Raspberry Pi OS (64-bit) »
   (la version avec bureau). Note le nom d'utilisateur et le mot de passe que tu choisis.
2. **Copie ce dossier `Prompteur`** sur le Pi (clé USB, ou `scp`), par ex. dans
   `/home/<ton-user>/Prompteur`.
3. Ouvre un terminal sur le Pi, dans le dossier, et lance :

   ```bash
   chmod +x install/setup.sh
   ./install/setup.sh
   sudo reboot
   ```

Le script installe tout, crée le WiFi du boîtier, et fait démarrer l'écran
automatiquement. **Après le redémarrage, le prompteur s'affiche tout seul.**

---

## 4. Utilisation au quotidien

1. **Allume le boîtier** → l'écran affiche le prompteur automatiquement.
2. **Sur ton téléphone**, connecte-toi au WiFi :
   - Réseau : **Prompteur**
   - Mot de passe : **unique par boîtier**, généré et **affiché à la fin de l'installation**
     (note-le ; tu peux imposer le tien avec `WIFI_PASS=monsecret ./install/setup.sh`)
3. Ouvre le navigateur du téléphone sur : **http://10.42.0.1:5000**
4. **Colle ton texte** (ou importe un `.txt` / une clé USB) → **« Envoyer à l'écran »**.
5. **Branche les pédales** en USB sur le boîtier et lis :
   pédale droite = avancer, pédale gauche = reculer.

### Import par clé USB
Branche une clé contenant des fichiers `.txt` sur le boîtier, puis dans la
télécommande : onglet **Texte → Clé USB → Charger**.

---

## 5. Deux façons d'afficher le prompteur (+ latence minimale)

Le texte est servi par le boîtier : **tout appareil connecté au boîtier peut
afficher le prompteur.** Tu as donc deux options, au choix ou en même temps :

- 🖥️ **Écran HDMI** branché directement sur le Raspberry (s'affiche automatiquement au démarrage).
- 💻 **PC / tablette** connecté au WiFi « Prompteur », qui ouvre
  `http://10.42.0.1:5000/display` dans un navigateur (touche **F11** = plein écran).

> L'adresse exacte à taper s'affiche **directement sur l'écran** au démarrage
> (et à tout moment avec la touche **i**).

### ⚡ Règle d'or : latence quasi nulle

Le défilement réagit aux pédales **en local, dans l'appareil qui affiche** : le
réseau n'intervient **jamais** dans le circuit « appui sur la pédale → texte qui
bouge » (latence ≈ une image d'écran, ~15 ms, imperceptible).

**➡️ Branche toujours les pédales sur l'appareil qui affiche le texte.**

| Configuration | Latence |
|---|---|
| Écran HDMI du Raspberry **+ pédales sur le Raspberry** | ✅ quasi nulle |
| PC affiche via l'IP **+ pédales sur le PC** | ✅ quasi nulle |
| PC affiche via l'IP **mais pédales sur le Raspberry** | ❌ à éviter (passerait par le réseau) |

La petite synchro (0,3 s) ne sert **qu'à** recevoir le texte importé depuis le
téléphone ; elle n'a **aucun** effet sur la réactivité des pédales.

## 6. Réglages disponibles (depuis le téléphone)

- Taille du texte, interligne, marges, alignement, police
- Couleurs du texte et du fond
- Vitesse de lecture
- **Miroir horizontal/vertical** (pour la vitre sans tain face caméra)
- Ligne de repère de lecture
- **Mode pédale** :
  - **Maintien** : pédale enfoncée = ça défile ; relâchée = ça s'arrête *(recommandé)*
  - **Impulsion** : une pression lance/arrête ; la pédale gauche revient au début
- **Apprentissage des touches** de pédale : clique dans le champ puis appuie sur
  la pédale pour enregistrer la touche qu'elle envoie.

---

## 7. Le look « pro » face caméra (optionnel)

Pour regarder l'objectif tout en lisant : monte un **support à vitre sans tain
(beam splitter)** devant la caméra, l'écran du boîtier posé à plat en dessous.
Active le **miroir horizontal** dans les réglages pour que le texte se lise à
l'endroit dans le reflet.

---

## 8. Dépannage

| Problème | Solution |
|---|---|
| L'écran reste noir | Vérifie le service : `sudo systemctl status prompteur` |
| Le WiFi « Prompteur » n'apparaît pas | `sudo nmcli connection up Prompteur` |
| Les pédales ne font rien | Onglet Réglages → réapprends les touches ; vérifie la programmation de la pédale |
| Redémarrer le serveur | `sudo systemctl restart prompteur` |
| Voir les logs | `journalctl -u prompteur -f` |

---

## 9. Sécurité & fiabilité (durcissement)

Le boîtier étant destiné à un usage professionnel, plusieurs protections sont en place :

- **Pare-feu** : le port du prompteur n'est joignable que depuis le WiFi du boîtier
  (interface `wlan0`) et en local — même si le Pi est un jour branché en Ethernet
  (règles `nftables` réappliquées à chaque démarrage).
- **Mot de passe WiFi unique** par appareil (généré aléatoirement à l'installation).
  C'est la barrière d'accès principale, l'API étant sans authentification par conception.
- **Serveur de production** (`waitress`) au lieu du serveur de développement, pour tenir
  sur de longues sessions et résister aux connexions lentes/coupées.
- **Limites d'entrée** : corps de requête plafonné (6 Mo), réglages validés et bornés
  côté serveur, import USB confiné à la clé (liens symboliques ignorés).
- **Robustesse écran** : les pédales sont relâchées si l'écran perd le focus (pas de
  défilement « collé »), bornes de défilement correctes, état d'affichage cohérent.
- **Ménagement de la carte SD** : les commandes de pilotage (lecture/pause/vitesse) ne
  sont pas réécrites sur disque à chaque appui.

Pour lancer en mode développement (rechargement + traces) : `PROMPTEUR_DEBUG=1 python server.py`.

## Structure du projet

```
Prompteur/
├── server.py            # serveur (affichage + télécommande + import)
├── requirements.txt
├── templates/
│   ├── display.html     # écran du prompteur (boîtier)
│   └── remote.html      # télécommande / import (téléphone)
├── static/
│   ├── display.js       # défilement + gestion des pédales
│   └── remote.js        # logique de la télécommande
├── install/
│   ├── setup.sh         # installation automatique sur le Pi
│   └── kiosk.sh         # lancement de l'écran en kiosque
├── scripts/             # tes textes enregistrés (.txt)
└── state.json           # texte courant + réglages (créé au 1er lancement)
```
