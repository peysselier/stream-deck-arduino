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
