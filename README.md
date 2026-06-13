# 🎛️ Stream Deck DIY

![Status](https://img.shields.io/badge/status-en%20d%C3%A9veloppement-orange)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6)

Un stream deck fait maison à base d'Arduino, relié en USB à un PC Windows.  
12 boutons + un potentiomètre pilotent Spotify, YouTube, Twitch, l'audio système
et des fenêtres de navigateur sur un second écran, avec un retour visuel sur un écran OLED.

---

## 📑 Table des matières

- [Présentation](#-présentation)
- [Architecture](#-architecture)
- [Fonctionnalités (mapping des boutons)](#-fonctionnalités-mapping-des-boutons)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration des APIs](#-configuration-des-apis)
- [Périphériques audio mappés](#-périphériques-audio-mappés)
- [Lancement](#-lancement)
- [Structure des fichiers](#-structure-des-fichiers)
- [Notes techniques](#-notes-techniques)

---

## 📖 Présentation

Ce projet transforme un Arduino en stream deck personnalisé :

- **Ce que c'est** : un boîtier Arduino avec 12 boutons, un potentiomètre et un écran OLED I2C, connecté en USB (port série) à un PC Windows.
- **Ce qu'il fait** : contrôle Spotify (lecture/pause/suivant/précédent), ouvre YouTube et Twitch dans une fenêtre de navigateur dédiée sur le second écran, bascule entre plusieurs périphériques de sortie audio, ouvre un second profil Google Chrome, et affiche en temps réel le morceau en cours / la source active / le volume sur l'écran OLED.
- **Composants** :
  - Arduino (branché sur `COM3`)
  - 12 boutons (pins `p2`–`p13`)
  - Écran OLED I2C 0.96" (SSD1306, 128x64)
  - Potentiomètre pour le contrôle du volume (pin `A0`)

---

## 🏗️ Architecture

```
Arduino (boutons + potentiomètre + OLED)

│

│  USB Série (COM3, protocole ligne par ligne)

▼

script.py  ◄──────────────► Windows APIs (pycaw / comtypes)

│

▼

Spotify (Web API) / YouTube / Twitch (titre fenêtre) / Audio / Google Chrome
```

`script.py` est lancé et supervisé par `launcher.pyw`, qui fournit une fenêtre de logs
et une icône dans la barre des tâches (tray).

---

## 🎮 Fonctionnalités (mapping des boutons)

| # | Bouton | Pin Arduino | Type | Action |
|---|--------|-------------|------|--------|
| 0 | Spotify | p2 | Toggle | Lance Spotify et définit Spotify comme source active. Désactivé au second appui. |
| 1 | YouTube | p3 | Momentané | Ouvre `youtube.com` dans Chrome sur le second écran. |
| 2 | Twitch | p4 | Momentané | Ouvre `twitch.tv` dans Chrome sur le second écran. |
| 3 | Suivant | p5 | Momentané | Piste suivante sur Spotify. |
| 4 | Pause | p6 | Momentané | Lecture/pause sur Spotify. |
| 5 | Précédent | p7 | Momentané | Piste précédente sur Spotify. |
| 6 | Casque 1 | p8 | Momentané | Bascule la sortie audio vers `audio_devices[0]`. |
| 7 | Casque 2 | p9 | Momentané | Bascule la sortie audio vers `audio_devices[1]`. |
| 8 | Écran | p10 | Momentané | Bascule la sortie audio vers `audio_devices[2]`. |
| 9 | 2ème compte | p11 | Momentané | Ouvre Chrome avec le second profil Google, sur le second écran. |
| 10 | Réservé | p12 | Momentané | Aucune action (log uniquement). |
| 11 | Réservé | p13 | Momentané | Aucune action (log uniquement). |

Le potentiomètre (A0) envoie en continu le volume système (0–100 %) dès qu'il varie de plus de 1 %.

L'écran OLED affiche en permanence : la source active (`SP`/`YT`/`TW`/`--`), le volume (barre + pourcentage), et deux lignes d'info (titre/artiste pour Spotify, titre de fenêtre pour YouTube/Twitch).

---

## ✅ Prérequis

### Matériel

- Arduino Uno ou compatible avec port USB
- 12 boutons poussoirs
- Écran OLED I2C 0.96" (SSD1306, 128x64)
- Potentiomètre linéaire
- PC Windows avec port USB libre (apparaissant comme `COM3`)

### Logiciel

- **Python 3.13** (via Microsoft Store ou python.org)
- Bibliothèques Python :

```
pycaw pyserial spotipy comtypes requests pystray pillow
```

- **Arduino IDE** avec les librairies `Adafruit_GFX` et `Adafruit_SSD1306`

### APIs

- **Spotify** : application créée sur le dashboard développeur, redirect URI sur `http://127.0.0.1:8888/callback`
- **YouTube Data API** : clé API (Google Cloud Console)
- **Twitch** : Client ID + token OAuth (Twitch Developer Console)

---

## 🚀 Installation

1. Cloner le dossier du projet sur le PC Windows.
2. Installer les dépendances Python :

```bash
pip install pycaw pyserial spotipy comtypes requests pystray pillow
```

3. Remplir `config.json` avec tes identifiants API ainsi que :
   - `serial_port` : port COM de l'Arduino (ex. `"COM3"`)
   - `browser_path`, `main_profile`, `second_profile` : chemin Chrome et noms des profils
   - `screen2_position` : position du second écran (ex. `"-1920,0"`)
   - `audio_devices` : noms exacts des périphériques de sortie audio

4. Flasher l'Arduino : ouvrir `stream_deck/stream_deck.ino` dans l'Arduino IDE, sélectionner la bonne carte/port, et téléverser.  
   ⚠️ Fermer `script.py` avant de téléverser pour libérer le port COM.

5. Lancer via le raccourci bureau (généré par `create_shortcut.ps1`) ou directement `launcher.pyw`.

---

## 🔑 Configuration des APIs

### Spotify

1. Créer une application sur [developer.spotify.com](https://developer.spotify.com/dashboard)
2. Récupérer `Client ID` et `Client Secret`
3. Ajouter l'URI de redirection : `http://127.0.0.1:8888/callback`
4. Renseigner dans `config.json` → `spotify.client_id`, `spotify.client_secret`, `spotify.redirect_uri`

### YouTube Data API

1. Créer un projet sur [Google Cloud Console](https://console.cloud.google.com/)
2. Activer "YouTube Data API v3"
3. Générer une clé API publique
4. Renseigner dans `config.json` → `youtube_api_key`

### Twitch

1. Créer une application sur la [Twitch Developer Console](https://dev.twitch.tv/console)
2. Récupérer le `Client ID`
3. Générer un token OAuth via [twitchtokengenerator.com](https://twitchtokengenerator.com/)
4. Renseigner dans `config.json` → `twitch.client_id`, `twitch.access_token`

---

## 🔊 Périphériques audio mappés

| Index | Périphérique | Bouton | Usage |
|-------|-------------|--------|-------|
| 0 | `Haut-parleurs (High Definition Audio Device)` | Casque 1 (#6) | Casque principal |
| 1 | `Haut-parleurs (USB Audio Device)` | Casque 2 (#7) | Second casque |
| 2 | `1 - PL2770H (AMD High Definition Audio Device)` | Écran (#8) | Sortie moniteur |

Les noms doivent correspondre **exactement** au `FriendlyName` du périphérique dans Windows.

---

## ▶️ Lancement

1. Double-clic sur le raccourci bureau **"Stream Deck"**.
2. La fenêtre du launcher s'ouvre et démarre automatiquement `script.py`.
3. Fermer la fenêtre la réduit dans la **barre des tâches (tray)** — le script continue en arrière-plan.
4. Clic droit sur l'icône du tray → **Quitter** pour tout arrêter.

---

## 📂 Structure des fichiers

```
stream_deck/

├── README.md               # Ce fichier

├── CLAUDE.md               # Notes/contexte pour l'assistant IA

├── config.json             # Configuration (ports, credentials API, profils, devices)

├── script.py               # Script principal (lecture série, logique métier)

├── launcher.pyw            # Interface graphique de supervision + icône tray

├── create_shortcut.ps1     # Crée le raccourci bureau "Stream Deck"

├── logo.png                # Icône utilisée par le launcher / le raccourci

├── launcher.lock           # Verrou d'instance unique (généré au lancement)

├── .cache                  # Cache du token Spotify (généré par spotipy)

├── .vscode/

│   └── settings.json       # Configuration Python pour VS Code

└── stream_deck/

└── stream_deck.ino     # Firmware Arduino (boutons, potentiomètre, OLED)
```

---

## 🛠️ Notes techniques

- Le **redirect URI Spotify** doit être `http://127.0.0.1:8888/callback` (et non `localhost`), conformément à la politique Spotify depuis avril 2025.
- **Fermer `script.py`** avant de téléverser un nouveau firmware, sinon le port `COM3` est occupé.
- `launcher.pyw` lance `script.py` avec le flag **`-u`** pour désactiver le buffering et afficher les logs en temps réel.
- Tous les appels `subprocess` utilisent **`creationflags=CREATE_NO_WINDOW`** pour éviter des fenêtres console parasites.
- Le baud rate doit être identique entre `stream_deck.ino` et `config.json`.
