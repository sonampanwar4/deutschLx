"""Draws the app icon in code, so no image files are needed."""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def make_icon() -> QIcon:
    size = 128
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#5b7cfa"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(6, 6, size - 12, size - 12), 22, 22)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(84)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "D")
    p.end()
    return QIcon(pix)
