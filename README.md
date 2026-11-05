# deutschlx

A small German-learning assistant for **macOS, Windows and Linux**. Every 30 minutes a
compact card appears with one German noun (article, plural, meaning, example sentence,
translation and the verbs in the sentence). You write your own German sentence, your local
Ollama model (`qwen3.5:9b`) checks it, and the card shows either **Sehr gut!** or the
**Corrected sentence**. Press **OK** and the card closes. The next one appears 35 minutes
after that moment.

## How it behaves

- The card appears only after Ollama has finished creating the vocabulary, so you never see a loading screen.
- It appears only when the screen is on and unlocked. If the screen is asleep or locked when a card is due, it waits until you are back.
- The 30 minutes are counted from the moment you press **OK**.
- Words do not repeat (history is kept in your user data folder).
- If Ollama is not running, the app waits 60 seconds and tries again. It does not crash.
- A menu-bar / system-tray icon lets you **Practice now**, **Pause / Resume** or **Quit**.

## Requirements

1. Python 3.10 or newer
2. [Ollama](https://ollama.com) installed and running
3. The model: `ollama pull qwen3.5:9b`

## Quick start

### Run Desktop assistant
macOS / Linux:

```bash
cd deutschlx/desktop/
chmod +x run.sh
./run.sh
```

Windows (double-click `run_windows.bat`, or in a terminal):

```bat
cd deutschlx/desktop/
run_windows.bat
```

The scripts create a `.venv`, install the dependencies and start the app. The first card
appears a few seconds later (`FIRST_SESSION_DELAY_MINUTES = 0` in `desktop/config.py`).

Manual way:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate      Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Start automatically at login

Run this from the activated virtual environment (so the right Python is registered):

```bash
python main.py --install-autostart
python main.py --uninstall-autostart     # to remove it
```

- macOS: a LaunchAgent in `~/Library/LaunchAgents`
- Windows: a small script in the Startup folder (uses `pythonw`, so no console window)
- Linux: a `.desktop` file in `~/.config/autostart`

## Settings

Edit `desktop/config.py` and restart: interval, first-card delay, card width, model name, Ollama
address, vocabulary level and themes. Set `THINK_WHEN_CHECKING = True` for stricter (but
slower) sentence checking.

## Logs and data

Folder: macOS `~/Library/Application Support/deutschlx`, Windows `%APPDATA%\deutschlx`,
Linux `~/.local/share/deutschlx`. It contains `logs/deutschlx.log`, `logs/crash.log`
(written if the process ever crashes hard) and `history.json`.

## Screen on / unlocked detection

| System | How |
| --- | --- |
| macOS | CoreGraphics display-asleep flag and the session "screen is locked" flag (needs `pyobjc-framework-Quartz`, installed automatically) |
| Windows | Lock screen via `OpenInputDesktop`; monitor on/off via power notifications |
| Linux | `loginctl` LockedHint, GNOME ScreenSaver (D-Bus), and `xset q` on X11 |

If a check is unavailable, the app assumes the screen is active and writes a warning to the log.
On Linux, detection depends on your desktop; it is most reliable on GNOME and KDE.

## Notes

- Linux: Qt 6 may need `sudo apt install libxcb-cursor0`. The tray icon needs a tray-capable desktop (GNOME needs the AppIndicator extension). "Always on top" may be ignored on Wayland.
- The card does not steal keyboard focus; click it to type. Drag it by its background to move it.
- Closing the card with the OS shortcut (Alt+F4 / Cmd+W) counts as pressing OK.
