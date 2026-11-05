"""deutschlx - German vocabulary cards powered by a local Ollama model."""

import argparse
import faulthandler
import logging
import sys
from logging.handlers import RotatingFileHandler


def _setup_logging():
    import config
    log_dir = config.data_dir() / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers = [RotatingFileHandler(log_dir / "deutschlx.log",
                                    maxBytes=1_000_000, backupCount=2,
                                    encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # If the process ever crashes hard, the Python stack lands in crash.log.
    global _crash_file
    _crash_file = open(log_dir / "crash.log", "a")
    faulthandler.enable(_crash_file)

    def hook(exc_type, exc, tb):
        logging.getLogger("deutschlx").error("Uncaught exception",
                                             exc_info=(exc_type, exc, tb))
    sys.excepthook = hook
    return log_dir


def _pick_font(app):
    from PySide6.QtGui import QFont, QFontDatabase
    available = set(QFontDatabase.families())
    for family in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu",
                   "Noto Sans", "Cantarell", "DejaVu Sans"):
        if family in available:
            font = QFont(family)
            font.setPointSize(10)
            app.setFont(font)
            return


def main():
    parser = argparse.ArgumentParser(prog="deutschlx")
    parser.add_argument("--install-autostart", action="store_true",
                        help="start deutschlx automatically when you log in")
    parser.add_argument("--uninstall-autostart", action="store_true",
                        help="remove the automatic start")
    args = parser.parse_args()

    if args.install_autostart or args.uninstall_autostart:
        import autostart
        if args.install_autostart:
            print("Autostart installed:", autostart.install())
        else:
            print("Autostart removed:", autostart.uninstall())
        return 0

    log_dir = _setup_logging()

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication

    import config
    from engine import OllamaEngine
    from presence import start_display_watcher
    from scheduler import Scheduler

    app = QApplication(sys.argv[:1])
    app.setApplicationName("deutschlx")
    app.setQuitOnLastWindowClosed(False)
    _pick_font(app)

    # Only one copy at a time.
    lock = QLockFile(str(config.data_dir() / "deutschlx.lock"))
    if not lock.tryLock(0):
        logging.info("deutschlx is already running; exiting.")
        return 0

    if sys.platform == "darwin":                 # no Dock icon, menu-bar only
        try:
            from AppKit import (NSApplication,
                                NSApplicationActivationPolicyAccessory)
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory)
        except Exception:
            logging.exception("Could not hide the Dock icon.")

    watcher = start_display_watcher(app)         # Windows monitor on/off tracking
    scheduler = Scheduler(app, OllamaEngine())

    logging.info("deutschlx started (logs: %s)", log_dir)
    code = app.exec()
    del scheduler, watcher, lock
    return code


if __name__ == "__main__":
    raise SystemExit(main())
