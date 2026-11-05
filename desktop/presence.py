"""Is the screen on and unlocked?  Works on macOS, Windows and Linux.

If a platform check is unavailable the app assumes the screen is active
(and writes one warning to the log) so that cards still appear.
"""

import logging
import os
import re
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)
_warned = set()
_display_on = True      # kept up to date by the Windows watcher


def _warn_once(key, message):
    if key not in _warned:
        _warned.add(key)
        log.warning(message)


def is_screen_active() -> bool:
    try:
        if sys.platform == "darwin":
            return _mac_active()
        if sys.platform == "win32":
            return _windows_active()
        return _linux_active()
    except Exception:
        log.exception("Screen check failed; assuming the screen is active.")
        return True


# ---- macOS ------------------------------------------------------------------
def _mac_active() -> bool:
    try:
        import Quartz
    except ImportError:
        _warn_once("quartz", "pyobjc-framework-Quartz missing; cannot detect "
                             "sleep/lock on macOS.")
        return True
    if Quartz.CGDisplayIsAsleep(Quartz.CGMainDisplayID()):
        return False
    session = Quartz.CGSessionCopyCurrentDictionary()
    if session:
        if session.get("CGSSessionScreenIsLocked"):
            return False
        on_console = session.get("kCGSSessionOnConsoleKey")
        if on_console is not None and not on_console:
            return False        # another user's session is in front
    return True


# ---- Windows ----------------------------------------------------------------
def _windows_active() -> bool:
    if not _display_on:
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    desktop = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desktop:
        return False            # workstation is locked (or secure desktop is up)
    user32.CloseDesktop(desktop)
    return True


def start_display_watcher(app):
    """Windows only: track monitor on/off through power notifications.

    Returns an object that must be kept alive, or None.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        from PySide6.QtCore import QAbstractNativeEventFilter
        from PySide6.QtWidgets import QWidget

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # GUID_CONSOLE_DISPLAY_STATE {6FE69556-704A-47A0-8F24-C28D936FDA47}
        guid = GUID(0x6FE69556, 0x704A, 0x47A0,
                    (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47))

        user32 = ctypes.windll.user32
        user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
        user32.RegisterPowerSettingNotification.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(GUID), wintypes.DWORD]

        anchor = QWidget()                      # never shown; only owns a HWND
        handle = user32.RegisterPowerSettingNotification(
            int(anchor.winId()), ctypes.byref(guid), 0)
        if not handle:
            raise OSError("RegisterPowerSettingNotification failed")

        class Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):
                global _display_on
                try:
                    if bytes(event_type) == b"windows_generic_MSG":
                        msg = wintypes.MSG.from_address(int(message))
                        if msg.message == 0x0218 and msg.wParam == 0x8013:
                            base = msg.lParam   # POWERBROADCAST_SETTING
                            length = ctypes.c_uint32.from_address(base + 16).value
                            if length >= 1:
                                _display_on = ctypes.c_ubyte.from_address(base + 20).value != 0
                except Exception:
                    pass
                return False, 0

        event_filter = Filter()
        app.installNativeEventFilter(event_filter)
        return (anchor, handle, event_filter)
    except Exception:
        log.exception("Monitor on/off tracking unavailable; only the lock "
                      "screen will be detected on Windows.")
        return None


# ---- Linux ------------------------------------------------------------------
def _run(cmd):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return done.stdout if done.returncode == 0 else None
    except Exception:
        return None


def _linux_active() -> bool:
    if shutil.which("loginctl"):
        session = os.environ.get("XDG_SESSION_ID", "auto")
        out = _run(["loginctl", "show-session", session, "-p", "LockedHint", "--value"])
        if out and out.strip() == "yes":
            return False
    if shutil.which("gdbus") and "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        out = _run(["gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver",
                    "--object-path", "/org/gnome/ScreenSaver",
                    "--method", "org.gnome.ScreenSaver.GetActive"])
        if out and "true" in out:
            return False
    if os.environ.get("DISPLAY") and shutil.which("xset"):
        out = _run(["xset", "q"])
        if out and re.search(r"Monitor is (Off|in Standby|in Suspend)", out):
            return False
    return True
