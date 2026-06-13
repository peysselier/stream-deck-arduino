# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A DIY USB stream deck: an Arduino (with an SSD1306 OLED display, 10 buttons, and a potentiometer)
talks over serial to a Python script running on the PC. The Python script controls Spotify/YouTube/Twitch
focus, system audio (volume + output device switching), and browser windows on a second monitor.

- `script.py` — main Python controller, run on the PC.
- `stream_deck/stream_deck.ino` — Arduino firmware (Adafruit_GFX / Adafruit_SSD1306 libraries required).
- `config.json` — runtime configuration, including API credentials (Spotify, YouTube, Twitch) and
  machine-specific paths (serial port, browser path, audio device names). **Contains live secrets —
  never print its contents or commit changes that expose them.**

## Running

```
python script.py
```

Requires these packages installed (no requirements file currently exists):
`pyserial`, `pycaw`, `spotipy`, `requests`.

Also requires `nircmd` available on PATH for audio device switching (`set_default_audio_device`).

The Arduino firmware is uploaded separately via the Arduino IDE/CLI to the board at `stream_deck/stream_deck.ino`.

## Architecture

### Serial protocol (Arduino <-> Python)

The Arduino and `script.py` communicate over a line-based serial protocol at the baud rate in
`config.json` (`serial_port` / `baud_rate`). Note: the `.ino` initializes `Serial.begin(9600)` while
`config.json` currently specifies 115200 — keep these in sync if changing either side.

Arduino -> Python:
- `BTN:<index>:<state>` — button index (0-11) and state (0/1). Button 0 (Spotify) is a toggle;
  all others, including 1 (YouTube), 2 (Twitch), and 9 (2nd Google account), are momentary
  (fire once with state 1 on press).
- `VOL:<0-100>` — potentiometer-derived volume change.

Python -> Arduino (sent every poll cycle via `send_display_update`):
- `SRC:<SP|YT|TW|-->` — currently active media source.
- `L1:<text>` / `L2:<text>` — two lines of "now playing" info shown on the OLED (truncated to 21 chars).
- `SVOL:<0-100>` — current system volume, drawn as a bar on the OLED.

### Python side (`script.py`)

- `CONFIG` is loaded once from `config.json` at import time; all credentials/paths/device names are
  read from there — don't hardcode values that belong in config.
- `button_state[12]` tracks the on/off state of each of the 12 buttons; `BUTTON_NAMES` maps indices
  to human-readable names (index = Arduino button index from the `BTN:` message).
- `forced_media` + `get_active_media()` determine which media source currently "owns" the OLED
  display and the Suivant/Pause/Précédent buttons. Pressing YouTube (1) or Twitch (2) sets
  `forced_media` and opens the corresponding site in the second-screen browser window (sticky until
  another media button is pressed); toggling Spotify (0) sets/clears `forced_media`. If `forced_media`
  is unset, `get_active_media()` falls back to Spotify if its toggle is on, else `None`.
- Two daemon threads run forever:
  - `serial_reader` — owns the global `ser` connection, reconnects on `serial.SerialException`,
    parses incoming `BTN:`/`VOL:` lines and dispatches to `handle_button` / `set_system_volume`.
  - `media_poller` — every 3s, fetches "now playing" info for whichever media source is currently
    active (`fetch_spotify_info` via Spotify Web API, `fetch_youtube_info`/`fetch_twitch_info` via
    Chrome window-title scraping through PowerShell) and pushes a full display update via
    `send_display_update`.
- `handle_button(btn_index, state)` is the central dispatch for all 12 buttons — add new button
  behaviors here, matching the index used in the `.ino` comments (`p2`..`p13` -> indices 0-11).
- Adding a new audio output device: append its exact device name to `audio_devices` in `config.json`;
  `set_default_audio_device(index)` maps button presses to entries in that list via `nircmd`.

### Arduino side (`stream_deck.ino`)

- Pins `p2`-`p13` map to button indices 0-11 sent in `BTN:` messages.
- Button p2 (Spotify) is an edge-triggered toggle with local state (`toggle_b2`); all others,
  including p3 (YouTube), p4 (Twitch), and p11 (2nd Google account), are momentary
  edge-triggered (fire once on press).
- The potentiometer on `A0` sends `VOL:<percent>` only when the value changes by more than 1, to avoid
  flooding the serial line.
- Incoming `SRC:`/`L1:`/`L2:`/`SVOL:` messages update the OLED state on the next `loop()` iteration.
