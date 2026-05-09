from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "src" / "fakturownik" / "assets"
PNG_PATH = ASSETS_DIR / "app_icon.png"
ICO_PATH = ASSETS_DIR / "app_icon.ico"


def draw_icon(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    outer = QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94)
    bg_gradient = QLinearGradient(outer.topLeft(), outer.bottomRight())
    bg_gradient.setColorAt(0.0, QColor("#0b1f2a"))
    bg_gradient.setColorAt(0.55, QColor("#124559"))
    bg_gradient.setColorAt(1.0, QColor("#0d5c63"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(bg_gradient)
    painter.drawRoundedRect(outer, size * 0.12, size * 0.12)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 28), max(2, size // 96)))
    painter.drawRoundedRect(outer.adjusted(size * 0.01, size * 0.01, -size * 0.01, -size * 0.01), size * 0.11, size * 0.11)

    glow = QPainterPath()
    glow.addEllipse(QRectF(size * 0.08, size * 0.06, size * 0.36, size * 0.22))
    painter.fillPath(glow, QColor(255, 255, 255, 18))

    shadow_rect = QRectF(size * 0.22, size * 0.18, size * 0.56, size * 0.62)
    painter.setBrush(QColor(5, 16, 24, 65))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(shadow_rect.translated(size * 0.02, size * 0.03), size * 0.08, size * 0.08)

    card_rect = QRectF(size * 0.20, size * 0.15, size * 0.56, size * 0.62)
    card_gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomLeft())
    card_gradient.setColorAt(0.0, QColor("#fbfdff"))
    card_gradient.setColorAt(1.0, QColor("#dfeaf0"))
    painter.setBrush(card_gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(card_rect, size * 0.075, size * 0.075)

    fold_path = QPainterPath()
    fold_path.moveTo(card_rect.right() - size * 0.16, card_rect.top())
    fold_path.lineTo(card_rect.right(), card_rect.top())
    fold_path.lineTo(card_rect.right(), card_rect.top() + size * 0.16)
    fold_path.closeSubpath()
    painter.fillPath(fold_path, QColor("#b7f3ea"))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#12b3a6"))
    painter.drawRoundedRect(QRectF(size * 0.27, size * 0.23, size * 0.32, size * 0.055), size * 0.02, size * 0.02)

    painter.setPen(QPen(QColor("#6f8591"), max(3, size // 48), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for offset in (0.37, 0.48, 0.59):
        painter.drawLine(QPointF(size * 0.29, size * offset), QPointF(size * 0.66, size * offset))

    painter.setBrush(QColor("#f59e0b"))
    painter.setPen(QPen(QColor(255, 255, 255, 210), max(3, size // 64)))
    seal_rect = QRectF(size * 0.52, size * 0.53, size * 0.18, size * 0.18)
    painter.drawEllipse(seal_rect)
    painter.drawLine(QPointF(size * 0.56, size * 0.62), QPointF(size * 0.60, size * 0.66))
    painter.drawLine(QPointF(size * 0.60, size * 0.66), QPointF(size * 0.66, size * 0.58))

    accent_path = QPainterPath()
    accent_path.moveTo(size * 0.18, size * 0.80)
    accent_path.cubicTo(size * 0.33, size * 0.72, size * 0.52, size * 0.82, size * 0.72, size * 0.76)
    accent_path.lineTo(size * 0.72, size * 0.84)
    accent_path.cubicTo(size * 0.50, size * 0.90, size * 0.32, size * 0.84, size * 0.18, size * 0.90)
    accent_path.closeSubpath()
    painter.fillPath(accent_path, QColor(255, 255, 255, 20))

    painter.end()
    return pixmap


def main() -> int:
    app = QGuiApplication(sys.argv)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    png_pixmap = draw_icon(512)
    ico_pixmap = draw_icon(256)

    if not png_pixmap.save(str(PNG_PATH)):
        raise RuntimeError(f"Nie udalo sie zapisac pliku {PNG_PATH}")
    if not ico_pixmap.save(str(ICO_PATH)):
        raise RuntimeError(f"Nie udalo sie zapisac pliku {ICO_PATH}")

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())