"""Start deutschlx automatically at login (macOS, Windows, Linux)."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

import config

MAIN = Path(__file__).resolve().parent / "main.py"
LABEL = "com.deutschlx.app"


def _mac_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _win_script() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft/Windows/Start Menu/Programs/Startup/deutschlx.vbs"


def _linux_desktop() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart" / "deutschlx.desktop"


def install() -> str:
    python = sys.executable
    if sys.platform == "darwin":
        path = _mac_plist()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "Label": LABEL,
            "ProgramArguments": [python, str(MAIN)],
            "WorkingDirectory": str(MAIN.parent),
            "RunAtLoad": True,
            "KeepAlive": False,
            "LimitLoadToSessionType": "Aqua",
            "StandardOutPath": str(config.data_dir() / "launchd.out.log"),
            "StandardErrorPath": str(config.data_dir() / "launchd.err.log"),
        }
        with open(path, "wb") as f:
            plistlib.dump(data, f)
        uid = str(os.getuid())
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(path)],
                       capture_output=True)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(path)],
                       capture_output=True)
        return str(path)

    if sys.platform == "win32":
        pyw = Path(python).with_name("pythonw.exe")     # no console window
        exe = str(pyw if pyw.exists() else python)
        command = f'"{exe}" "{MAIN}"'
        path = _win_script()
        path.parent.mkdir(parents=True, exist_ok=True)
        escaped = command.replace('"', '""')
        path.write_text(
            f'CreateObject("WScript.Shell").Run "{escaped}", 0, False\n',
            encoding="utf-8")
        return str(path)

    path = _linux_desktop()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\nType=Application\nName=deutschlx\n"
        f'Exec="{python}" "{MAIN}"\nX-GNOME-Autostart-enabled=true\n'
        "Terminal=false\n", encoding="utf-8")
    return str(path)


def uninstall() -> str:
    if sys.platform == "darwin":
        path = _mac_plist()
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)],
                       capture_output=True)
    elif sys.platform == "win32":
        path = _win_script()
    else:
        path = _linux_desktop()
    if path.exists():
        path.unlink()
    return str(path)
