"""The deutschlx learning card: vocabulary, your sentence, then the result."""

import logging
import sys
import threading

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

import config

log = logging.getLogger(__name__)

STYLE = """
#card { background: #11141b; border: 1px solid #2b3345; }
#accent { background: #5b7cfa; }
QLabel { background: transparent; color: #e8ebf3; }
#brand { color: #7f9bff; font-size: 11px; font-weight: 700; }
#tag { color: #7d8799; font-size: 11px; }
#word { font-size: 28px; font-weight: 700; color: #ffffff; }
#plural { color: #98a2b6; font-size: 13px; }
#meaning { font-size: 15px; color: #dfe4f0; }
#panel { background: #181d28; border: 1px solid #272f40; border-radius: 6px; }
#sentence { font-size: 15px; color: #ffffff; }
#translation { font-size: 13px; color: #8e98ac; }
#verbs { font-size: 13px; color: #c3cbdc; }
#sep { background: #272f40; }
#section { color: #7d8799; font-size: 10px; font-weight: 700; }
QPlainTextEdit { background: #0c0f15; border: 1px solid #2f384c; border-radius: 6px;
                 padding: 6px 8px; color: #ffffff; font-size: 14px;
                 selection-background-color: #5b7cfa; }
QPlainTextEdit:focus { border: 1px solid #5b7cfa; }
QPushButton { background: #5b7cfa; color: #ffffff; border: none; border-radius: 6px;
              padding: 8px 24px; font-weight: 700; font-size: 13px; }
QPushButton:hover { background: #6f8cff; }
QPushButton:disabled { background: #333a4c; color: #8a93a6; }
QPushButton#ghost { background: #232a3a; color: #dfe4f0; }
QPushButton#ghost:hover { background: #2c3548; }
#good { color: #5fd38d; font-size: 24px; font-weight: 700; }
#fixhead { color: #f5b754; font-size: 13px; font-weight: 700; }
#fixed { color: #ffffff; font-size: 17px; font-weight: 600; }
#error { color: #f28b82; font-size: 13px; }
"""


class SentenceEdit(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


def _label(text="", name=None, wrap=True, plain=True):
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if plain:
        label.setTextFormat(Qt.TextFormat.PlainText)   # never interpret model text as HTML
    return label


class Card(QWidget):
    finished = Signal()          # emitted once, when the card is closed
    _result = Signal(object)     # from the worker thread
    _failed = Signal(str)

    def __init__(self, entry, engine):
        super().__init__()
        self.entry = entry
        self.engine = engine
        self._done = False
        self._sentence = ""

        flags = (Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint)
        if sys.platform != "darwin":      # on macOS "Tool" windows hide when the app is inactive
            flags |= Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setWindowTitle("deutschlx")
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(STYLE)
        self._build()
        self._result.connect(self._on_result)
        self._failed.connect(self._on_failed)

    # ---- layout -----------------------------------------------------------
    def _build(self):
        e = self.entry
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        accent = QFrame()
        accent.setObjectName("accent")
        accent.setFixedHeight(3)
        root.addWidget(accent)

        body = QVBoxLayout()
        body.setContentsMargins(20, 14, 20, 18)
        body.setSpacing(9)
        root.addLayout(body)

        header = QHBoxLayout()
        header.addWidget(_label("DEUTSCHLX", "brand", wrap=False))
        header.addStretch()
        header.addWidget(_label("Vocabulary", "tag", wrap=False))
        body.addLayout(header)

        body.addWidget(_label(e["word"], "word"))
        body.addWidget(_label(f"Plural: {e['plural']}", "plural"))
        body.addWidget(_label(e["meaning"], "meaning"))

        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 10, 12, 10)
        pl.setSpacing(5)
        pl.addWidget(_label(e["sentence"], "sentence"))
        pl.addWidget(_label(e["translation"], "translation"))
        if e["verbs"]:
            sep = QFrame()
            sep.setObjectName("sep")
            sep.setFixedHeight(1)
            pl.addSpacing(2)
            pl.addWidget(sep)
            lines = [f"{inf}  –  {pret}  –  {part}" for inf, pret, part in e["verbs"]]
            pl.addWidget(_label("\n".join(lines), "verbs"))
        body.addWidget(panel)

        # -- input part (hidden after checking)
        self.input_box = QWidget()
        il = QVBoxLayout(self.input_box)
        il.setContentsMargins(0, 4, 0, 0)
        il.setSpacing(7)
        il.addWidget(_label("YOUR TURN  ·  WRITE A NEW GERMAN SENTENCE", "section", wrap=False))
        self.input = SentenceEdit()
        self.input.setPlaceholderText("Type your German sentence…")
        self.input.setFixedHeight(60)
        self.input.submitted.connect(self._submit)
        il.addWidget(self.input)
        row = QHBoxLayout()
        row.addStretch()
        self.check_button = QPushButton("Check")
        self.check_button.clicked.connect(self._submit)
        row.addWidget(self.check_button)
        il.addLayout(row)
        body.addWidget(self.input_box)

        # -- result part (shown after checking)
        self.result_box = QWidget()
        rl = QVBoxLayout(self.result_box)
        rl.setContentsMargins(0, 4, 0, 0)
        rl.setSpacing(6)
        self.good_label = _label("✓  Sehr gut!", "good", wrap=False)
        self.fixhead_label = _label("Corrected sentence", "fixhead", wrap=False)
        self.fixed_label = _label("", "fixed")
        self.fixed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.error_label = _label("", "error")
        for w in (self.good_label, self.fixhead_label, self.fixed_label, self.error_label):
            rl.addWidget(w)
        rrow = QHBoxLayout()
        rrow.addStretch()
        self.retry_button = QPushButton("Try again")
        self.retry_button.setObjectName("ghost")
        self.retry_button.clicked.connect(self._retry)
        rrow.addWidget(self.retry_button)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self._finish)
        rrow.addWidget(self.ok_button)
        rl.addSpacing(4)
        rl.addLayout(rrow)
        body.addWidget(self.result_box)
        self.result_box.hide()

    def _fit(self):
        """Resize to the content; keep the bottom-right corner where it is."""
        height = self.layout().totalHeightForWidth(config.CARD_WIDTH)
        if height <= 0:
            height = self.sizeHint().height()
        old_bottom = self.geometry().bottom() if self.isVisible() else None
        self.setFixedSize(config.CARD_WIDTH, height)
        if old_bottom is not None:
            self.move(self.x(), old_bottom - height + 1)

    def _move_to_center(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.x() + (area.width() - self.width()) // 2,
                  area.y() + (area.height() - self.height()) // 2)

    # ---- showing ----------------------------------------------------------
    def present(self):
        self._fit()
        self._move_to_center()
        self.show()
        self.raise_()
        if config.GRAB_FOCUS:
            self.activateWindow()
        self.input.setFocus()

    # ---- checking ---------------------------------------------------------
    def _submit(self):
        sentence = self.input.toPlainText().strip()
        if not sentence or not self.check_button.isEnabled():
            return
        self._sentence = sentence
        self.check_button.setEnabled(False)
        self.check_button.setText("Checking…")
        self.input.setReadOnly(True)

        def work():
            try:
                result = self.engine.check_sentence(self.entry, sentence)
            except Exception as exc:
                log.exception("Sentence check failed")
                try:
                    self._failed.emit(str(exc))
                except RuntimeError:
                    pass
                return
            try:
                self._result.emit(result)
            except RuntimeError:        # card was closed meanwhile
                pass

        threading.Thread(target=work, daemon=True).start()

    @Slot(object)
    def _on_result(self, result):
        for w in (self.good_label, self.fixhead_label, self.fixed_label,
                  self.error_label, self.retry_button):
            w.hide()
        if result["is_correct"]:
            self.good_label.show()
        else:
            self.fixhead_label.show()
            self.fixed_label.setText(result["corrected"])
            self.fixed_label.show()
        self._show_result_box()

    @Slot(str)
    def _on_failed(self, message):
        for w in (self.good_label, self.fixhead_label, self.fixed_label):
            w.hide()
        self.error_label.setText(
            "Couldn't check your sentence. Is Ollama running?\n" + message[:140])
        self.error_label.show()
        self.retry_button.show()
        self._show_result_box()

    def _show_result_box(self):
        self.input_box.hide()
        self.result_box.show()
        self.ok_button.setFocus()
        self._fit()

    def _retry(self):
        self.result_box.hide()
        self.input_box.show()
        self.check_button.setEnabled(True)
        self.check_button.setText("Check")
        self.input.setReadOnly(False)
        self.input.setFocus()
        self._fit()

    # ---- closing ----------------------------------------------------------
    def _finish(self):
        if self._done:
            return
        self._done = True
        self.close()
        self.finished.emit()

    def closeEvent(self, event):
        # Also reached if the OS closes the window (Alt+F4, Cmd+W): treat it as OK.
        if not self._done:
            self._done = True
            self.finished.emit()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()      # drag the card by its background
