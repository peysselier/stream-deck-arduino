import serial
import threading
import time
import subprocess
import os
import json
import ctypes
from ctypes import c_int
from ctypes.wintypes import LPCWSTR
import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
import comtypes.client
from pycaw.pycaw import AudioUtilities
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import sys
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
sys.stderr.reconfigure(line_buffering=True, encoding="utf-8")

# Empêche l'apparition d'une fenêtre console pour tous les processus externes lancés.
CREATE_NO_WINDOW = 0x08000000

# ──────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

SERIAL_PORT = CONFIG["serial_port"]
BAUD_RATE = CONFIG["baud_rate"]

SPOTIFY_CLIENT_ID     = CONFIG["spotify"]["client_id"]
SPOTIFY_CLIENT_SECRET = CONFIG["spotify"]["client_secret"]
SPOTIFY_REDIRECT_URI  = CONFIG["spotify"]["redirect_uri"]

SPOTIFY_PATH = os.path.join(os.environ["APPDATA"], "Spotify", "Spotify.exe")

BROWSER_PATH = CONFIG["browser_path"]
MAIN_PROFILE = CONFIG["main_profile"]
SECOND_GOOGLE_PROFILE = CONFIG["second_profile"]
SCREEN2_POSITION = CONFIG["screen2_position"]

AUDIO_DEVICES = CONFIG["audio_devices"]

# ──────────────────────────────────────────
# AUDIO WINDOWS (pycaw 20251023)
# ──────────────────────────────────────────
_speakers = AudioUtilities.GetSpeakers()
volume_iface = _speakers.EndpointVolume

# ──────────────────────────────────────────
# CHANGEMENT DE PÉRIPHÉRIQUE PAR DÉFAUT (sans nircmd)
# ──────────────────────────────────────────
CLSID_POLICY_CONFIG = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")

class IPolicyConfig(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")
    _methods_ = (
        COMMETHOD([], HRESULT, 'GetMixFormat'),
        COMMETHOD([], HRESULT, 'GetDeviceFormat'),
        COMMETHOD([], HRESULT, 'ResetDeviceFormat'),
        COMMETHOD([], HRESULT, 'SetDeviceFormat'),
        COMMETHOD([], HRESULT, 'GetProcessingPeriod'),
        COMMETHOD([], HRESULT, 'SetProcessingPeriod'),
        COMMETHOD([], HRESULT, 'GetShareMode'),
        COMMETHOD([], HRESULT, 'SetShareMode'),
        COMMETHOD([], HRESULT, 'GetPropertyValue'),
        COMMETHOD([], HRESULT, 'SetPropertyValue'),
        COMMETHOD(
            [], HRESULT, 'SetDefaultEndpoint',
            (['in'], LPCWSTR, 'wszDeviceId'),
            (['in'], c_int, 'eRole'),
        ),
        COMMETHOD([], HRESULT, 'SetEndpointVisibility'),
    )

def set_default_endpoint(device_name):
    """Bascule le périphérique de sortie par défaut (3 rôles) par son FriendlyName."""
    target_id = None
    for device in AudioUtilities.GetAllDevices():
        if device.FriendlyName == device_name:
            target_id = device.id
            break
    if not target_id:
        print(f"[Audio] Périphérique introuvable: {device_name}")
        return
    policy_config = comtypes.client.CreateObject(CLSID_POLICY_CONFIG, interface=IPolicyConfig)
    for role in (0, 1, 2):  # console, multimedia, communications
        policy_config.SetDefaultEndpoint(target_id, role)

def set_system_volume(level_0_100):
    scalar = max(0.0, min(1.0, level_0_100 / 100.0))
    volume_iface.SetMasterVolumeLevelScalar(scalar, None)

def get_system_volume():
    return int(volume_iface.GetMasterVolumeLevelScalar() * 100)

# ──────────────────────────────────────────
# ÉTAT GLOBAL
# ──────────────────────────────────────────
button_state = [0] * 12
forced_media = None
ser = None
sp = None

media_info = {
    "spotify": {"line1": "", "line2": ""},
    "youtube": {"line1": "", "line2": ""},
    "twitch":  {"line1": "", "line2": ""},
}

# ──────────────────────────────────────────
# SPOTIFY
# ──────────────────────────────────────────
def init_spotify():
    global sp
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-read-playback-state user-modify-playback-state"
        ))
        print("[Spotify] Connecté")
    except Exception as e:
        print(f"[Spotify] Erreur init: {e}")
        sp = None

def get_spotify_device_id(playback=None):
    if playback and playback.get('device'):
        return playback['device']['id']
    devices = sp.devices().get('devices', [])
    if not devices:
        print("[Spotify] Aucun appareil actif, ouvre Spotify")
        return None
    return devices[0]['id']

def spotify_play_pause():
    if not sp: return
    try:
        playback = sp.current_playback()
        if playback and playback['is_playing']:
            sp.pause_playback()
        else:
            device_id = get_spotify_device_id(playback)
            if device_id:
                sp.start_playback(device_id=device_id)
    except Exception as e:
        print(f"[Spotify] play/pause: {e}")

def spotify_next():
    if not sp: return
    try:
        device_id = get_spotify_device_id(sp.current_playback())
        if device_id:
            sp.next_track(device_id=device_id)
    except Exception as e:
        print(f"[Spotify] next: {e}")

def spotify_prev():
    if not sp: return
    try:
        device_id = get_spotify_device_id(sp.current_playback())
        if device_id:
            sp.previous_track(device_id=device_id)
    except Exception as e:
        print(f"[Spotify] prev: {e}")

def fetch_spotify_info():
    if not sp: return
    try:
        playback = sp.current_playback()
        if playback and playback['is_playing']:
            track = playback['item']
            media_info["spotify"]["line1"] = track['name']
            media_info["spotify"]["line2"] = track['artists'][0]['name']
        else:
            media_info["spotify"]["line1"] = "En pause"
            media_info["spotify"]["line2"] = ""
    except:
        pass

# ──────────────────────────────────────────
# YOUTUBE (détection via titre fenêtre)
# ──────────────────────────────────────────
def fetch_youtube_info():
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-Process | Where-Object {$_.MainWindowTitle -like "*YouTube*"} | Select-Object -First 1 -ExpandProperty MainWindowTitle'],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=2,
            creationflags=CREATE_NO_WINDOW
        )
        title = result.stdout.strip()
        if title:
            title = title.replace(" - YouTube", "").replace(" - Google Chrome", "")
            media_info["youtube"]["line1"] = title[:21]
            media_info["youtube"]["line2"] = "YouTube"
        else:
            media_info["youtube"]["line1"] = "YouTube actif"
            media_info["youtube"]["line2"] = ""
    except:
        media_info["youtube"]["line1"] = "YouTube actif"
        media_info["youtube"]["line2"] = ""

# ──────────────────────────────────────────
# TWITCH (détection via titre fenêtre)
# ──────────────────────────────────────────
def fetch_twitch_info():
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-Process | Where-Object {$_.MainWindowTitle -like "*Twitch*"} | Select-Object -First 1 -ExpandProperty MainWindowTitle'],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=2,
            creationflags=CREATE_NO_WINDOW
        )
        title = result.stdout.strip()
        if title:
            title = title.replace(" - Twitch", "").replace(" - Google Chrome", "")
            media_info["twitch"]["line1"] = title[:21]
            media_info["twitch"]["line2"] = "Twitch"
        else:
            media_info["twitch"]["line1"] = "Twitch actif"
            media_info["twitch"]["line2"] = ""
    except:
        media_info["twitch"]["line1"] = "Twitch actif"
        media_info["twitch"]["line2"] = ""

# ──────────────────────────────────────────
# NAVIGATEUR
# ──────────────────────────────────────────
def open_in_second_screen(url):
    subprocess.Popen([
        BROWSER_PATH,
        f"--profile-directory={MAIN_PROFILE}",
        f"--window-position={SCREEN2_POSITION}",
        "--window-size=1920,1080",
        url
    ], creationflags=CREATE_NO_WINDOW)

def open_second_google_account(url="https://www.google.com"):
    subprocess.Popen([
        BROWSER_PATH,
        f"--profile-directory={SECOND_GOOGLE_PROFILE}",
        f"--window-position={SCREEN2_POSITION}",
        url
    ], creationflags=CREATE_NO_WINDOW)

# ──────────────────────────────────────────
# PÉRIPHÉRIQUE AUDIO (nircmd)
# ──────────────────────────────────────────
def set_default_audio_device(index):
    if index < len(AUDIO_DEVICES):
        device_name = AUDIO_DEVICES[index]
        try:
            set_default_endpoint(device_name)
        except Exception as e:
            print(f"[Audio] Erreur changement de périphérique: {e}")

# ──────────────────────────────────────────
# LOGIQUE DE PRIORITÉ MÉDIA
# ──────────────────────────────────────────
def get_active_media():
    if forced_media:
        return forced_media
    if button_state[0] == 1:
        return "spotify"
    return None

def send_display_update():
    media = get_active_media()
    vol = get_system_volume()
    if media:
        src = {"spotify": "SP", "youtube": "YT", "twitch": "TW"}[media]
        l1 = media_info[media]["line1"]
        l2 = media_info[media]["line2"]
    else:
        src = "--"
        l1 = "Aucun media"
        l2 = ""
    if ser and ser.is_open:
        try:
            ser.write(f"SRC:{src}\n".encode())
            time.sleep(0.01)
            ser.write(f"L1:{l1}\n".encode())
            time.sleep(0.01)
            ser.write(f"L2:{l2}\n".encode())
            time.sleep(0.01)
            ser.write(f"SVOL:{vol}\n".encode())
        except Exception as e:
            print(f"[Série] Erreur écriture: {e}")

# ──────────────────────────────────────────
# ACTIONS BOUTONS
# ──────────────────────────────────────────
BUTTON_NAMES = [
    "Spotify",      # 0
    "YouTube",      # 1
    "Twitch",       # 2
    "Suivant",      # 3
    "Pause",        # 4
    "Précédent",    # 5
    "Casque 1",     # 6
    "Casque 2",     # 7
    "Écran",        # 8
    "2ème compte",  # 9
    "Réservé 10",   # 10
    "Réservé 11",   # 11
]

def handle_button(btn_index, state):
    global forced_media, button_state
    button_state[btn_index] = int(state)

    nom = BUTTON_NAMES[btn_index] if btn_index < len(BUTTON_NAMES) else f"BTN{btn_index}"
    print(f"[BOUTON] {nom} (#{btn_index}) → {'ON' if state == 1 else 'OFF'}")

    # Bouton 0 : Spotify
    if btn_index == 0:
        if state == 1:
            forced_media = "spotify"
            subprocess.Popen([SPOTIFY_PATH], creationflags=CREATE_NO_WINDOW)
        else:
            if forced_media == "spotify":
                forced_media = None

    # Bouton 1 : YouTube
    elif btn_index == 1:
        if state == 1:
            forced_media = "youtube"
            open_in_second_screen("https://www.youtube.com")

    # Bouton 2 : Twitch
    elif btn_index == 2:
        if state == 1:
            forced_media = "twitch"
            open_in_second_screen("https://www.twitch.tv")

    # Bouton 3 : Suivant
    elif btn_index == 3:
        media = get_active_media()
        if media == "spotify":
            spotify_next()

    # Bouton 4 : Pause
    elif btn_index == 4:
        media = get_active_media()
        if media == "spotify":
            spotify_play_pause()

    # Bouton 5 : Précédent
    elif btn_index == 5:
        media = get_active_media()
        if media == "spotify":
            spotify_prev()

    # Bouton 6 : Casque 1
    elif btn_index == 6:
        set_default_audio_device(0)

    # Bouton 7 : Casque 2
    elif btn_index == 7:
        set_default_audio_device(1)

    # Bouton 8 : Écran
    elif btn_index == 8:
        set_default_audio_device(2)

    # Bouton 9 : Navigateur second compte Google
    elif btn_index == 9:
        if state == 1:
            open_second_google_account()

    # Boutons 10 et 11 : réservés
    elif btn_index in [10, 11]:
        print(f"[BTN{btn_index}] Réservé")

# ──────────────────────────────────────────
# BOUCLE SÉRIE
# ──────────────────────────────────────────
def serial_reader():
    global ser
    # COM doit être initialisé sur ce thread pour que comtypes/pycaw
    # (set_default_endpoint, etc.) fonctionnent ici.
    comtypes.CoInitialize()
    # Laisse le temps à l'OS de finir d'initialiser le port série au démarrage,
    # pour éviter un PermissionError("Accès refusé") sur la première tentative.
    time.sleep(1.5)
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"[Série] Connecté sur {SERIAL_PORT}")
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                print(f"[SERIE reçu] {line}")
                if line.startswith("BTN:"):
                    parts = line.split(":")
                    if len(parts) == 3:
                        btn = int(parts[1])
                        state = int(parts[2])
                        handle_button(btn, state)
                elif line.startswith("VOL:"):
                    vol = int(line.split(":")[1])
                    set_system_volume(vol)
                    print(f"[VOL] {vol}%")
        except serial.SerialException as e:
            print(f"[Série] Déconnecté: {e}, reconnexion dans 3s...")
            if ser and ser.is_open:
                ser.close()
            time.sleep(3)
        except Exception as e:
            print(f"[Série] Erreur: {e}")
            if ser and ser.is_open:
                ser.close()
            time.sleep(1)

# ──────────────────────────────────────────
# BOUCLE DE POLLING MÉDIA
# ──────────────────────────────────────────
def media_poller():
    while True:
        try:
            media = get_active_media()
            if media == "spotify": fetch_spotify_info()
            elif media == "youtube": fetch_youtube_info()
            elif media == "twitch": fetch_twitch_info()
            send_display_update()
        except Exception as e:
            print(f"[Poller] Erreur: {e}")
        time.sleep(3)

# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
if __name__ == "__main__":
    init_spotify()

    t1 = threading.Thread(target=serial_reader, daemon=True)
    t2 = threading.Thread(target=media_poller, daemon=True)
    t1.start()
    t2.start()

    print("Stream Deck actif. Ctrl+C pour quitter.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt.")