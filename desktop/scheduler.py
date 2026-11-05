"""Decides when a card appears and owns the tray (menu bar) icon."""

import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import config
from card import Card
from history import History
from icon import make_icon
from presence import is_screen_active

log = logging.getLogger(__name__)

IDLE, GENERATING, READY, SHOWING = range(4)


class Scheduler(QObject):
    _generated = Signal(object)
    _generation_failed = Signal(str)

    def __init__(self, app, engine, presence=is_screen_active, history=None,
                 interval_seconds=None, first_delay_seconds=None,
                 retry_seconds=None, poll_seconds=None, tray=True):
        super().__init__()
        self.app = app
        self.engine = engine
        self.presence = presence
        self.history = history if history is not None else History()
        self.interval = (config.INTERVAL_MINUTES * 60
                         if interval_seconds is None else interval_seconds)
        first = (config.FIRST_SESSION_DELAY_MINUTES * 60
                 if first_delay_seconds is None else first_delay_seconds)
        self.retry = config.RETRY_SECONDS if retry_seconds is None else retry_seconds

        self.state = IDLE
        self.paused = False
        self.next_due = time.time() + first    # wall clock: counts while the laptop sleeps
        self.entry = None
        self.card = None
        self._old_cards = []                   # keeps closed cards alive until it is safe
        self._force = False
        self._forced = False

        self._generated.connect(self._on_generated)
        self._generation_failed.connect(self._on_generation_failed)

        self.tray = None
        if tray:
            self._setup_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        poll = config.POLL_SECONDS if poll_seconds is None else poll_seconds
        self.timer.start(int(poll * 1000))
        QTimer.singleShot(500, self._tick)

    # ---- tray -------------------------------------------------------------
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("No system tray available; use Ctrl+C in a terminal to quit.")
        self.tray = QSystemTrayIcon(make_icon(), self.app)
        self.tray.setToolTip("deutschlx")
        self.menu = QMenu()
        self.status_action = QAction("", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        now_action = QAction("Practice now", self.menu)
        now_action.triggered.connect(self.practice_now)
        self.menu.addAction(now_action)
        self.pause_action = QAction("Pause", self.menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.pause_action)
        self.menu.addSeparator()
        quit_action = QAction("Quit deutschlx", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        self.menu.aboutToShow.connect(self._refresh_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self._refresh_menu()

    def _refresh_menu(self):
        if self.paused:
            text = "Paused"
        elif self.state == SHOWING:
            text = "Card is open"
        elif self.state in (GENERATING, READY):
            text = "Preparing your card…"
        else:
            minutes = max(0, int((self.next_due - time.time()) / 60 + 0.99))
            text = "Next card: now" if minutes == 0 else f"Next card in {minutes} min"
        self.status_action.setText(text)
        self.pause_action.setText("Resume" if self.paused else "Pause")

    # ---- user actions -----------------------------------------------------
    @Slot()
    def toggle_pause(self):
        self.paused = not self.paused
        if self.tray:
            self._refresh_menu()

    @Slot()
    def practice_now(self):
        if self.state == IDLE:
            self._force = True
            self._tick()

    # ---- state machine ----------------------------------------------------
    @Slot()
    def _tick(self):
        if self.state in (GENERATING, SHOWING):
            return
        if self.state == READY:
            if self._forced or (not self.paused and self.presence()):
                self._show_card()
            return
        # IDLE
        if not self._force:
            if self.paused or time.time() < self.next_due:
                return
            if not self.presence():
                return
        self._forced, self._force = self._force, False
        self._start_generation()

    def _start_generation(self):
        self.state = GENERATING

        def work():
            try:
                entry = self.engine.generate_entry(self.history)
            except Exception as exc:
                log.exception("Could not create vocabulary")
                self._generation_failed.emit(str(exc))
                return
            self._generated.emit(entry)

        threading.Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_generated(self, entry):
        self.entry = entry
        self.state = READY
        self._tick()            # show right away if the screen is still active

    @Slot(str)
    def _on_generation_failed(self, message):
        self.state = IDLE
        self._forced = False
        self.next_due = time.time() + self.retry
        log.warning("Will retry in %s s: %s", self.retry, message)

    def _show_card(self):
        self._old_cards.clear()                 # previous card is long gone by now
        entry, self.entry = self.entry, None
        self.history.add(entry["word"])
        self.card = Card(entry, self.engine)
        self.card.finished.connect(self._on_card_finished)
        self.state = SHOWING
        self._forced = False
        self.card.present()

    @Slot()
    def _on_card_finished(self):
        # Runs inside the card's own button handler: never destroy the card here.
        card, self.card = self.card, None
        if card is not None:
            card.hide()
            card.deleteLater()
            self._old_cards.append(card)        # keep the Python wrapper alive for now
        self.state = IDLE
        self.next_due = time.time() + self.interval   # 35 minutes from pressing OK
