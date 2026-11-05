"""deutschlx settings. Edit the values below, then restart the app."""

import os
import sys
from pathlib import Path

APP_NAME = "deutschlx"

# ---- Ollama -------------------------------------------------------------
MODEL = "qwen3.5:9b"
OLLAMA_HOST = "http://localhost:11434"
REQUEST_TIMEOUT_SECONDS = 180      # the first request may load the model
KEEP_ALIVE = "10m"                 # keep the model in memory between cards
THINK_WHEN_GENERATING = False      # True = slower, sometimes better vocabulary
THINK_WHEN_CHECKING = False        # True = slower, stricter sentence checking

# ---- Timing -------------------------------------------------------------
INTERVAL_MINUTES = 30              # wait counted from the moment you press OK
FIRST_SESSION_DELAY_MINUTES = 0    # 0 = first card right after the app starts
RETRY_SECONDS = 60                 # wait before retrying if Ollama fails
POLL_SECONDS = 5                   # how often the app checks the clock

# ---- Card ---------------------------------------------------------------
CARD_WIDTH = 440
CARD_MARGIN = 24                   # distance from the screen corner
GRAB_FOCUS = False                 # True = card steals keyboard focus when shown

# ---- Vocabulary ---------------------------------------------------------
LEVEL = "B1"
THEMES = [
    "work", "travel", "food and drink", "health", "technology", "family",
    "city life", "nature and weather", "education", "money", "free time",
    "feelings", "home", "society", "media", "shopping", "transport",
    "culture", "sport", "law and politics",
]
HISTORY_WORDS_IN_PROMPT = 60       # recent words the model must avoid
HISTORY_MAX = 1000                 # words remembered on disk


def data_dir() -> Path:
    """Per-user folder for the log files and the word history."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    folder = base / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder
