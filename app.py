"""Giao diện PySide6 của ANTT SafePack."""

from collections.abc import Callable
from html import escape
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QDesktopServices, QFont, QIcon, QPainter,
    QPainterPath, QPen, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame,
    QGraphicsDropShadowEffect, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget
)

from integrity import AppError, path_parts
from packages import COMPRESSION, Progress, Result, create_package
from safepack_pages import BenchmarkPage, ExplorePage


ACCENT_TEAL = "#075b51"
APP_NAME = "ANTT SafePack"
APP_DESCRIPTION = "Mã hóa và khôi phục gói tệp"
PROJECT_DIR = Path(__file__).resolve().parent
ACCENT_TEAL_HOVER = "#097367"
ACCENT_TEAL_PRESSED = "#05453e"
ACCENT_GREEN = "#13734b"
ACCENT_GREEN_HOVER = "#0f5c3c"
BG_MAIN = "#ffffff"
BG_SIDEBAR = "#f4f6f5"
BORDER_COLOR = "#dce5e0"
TEXT_DARK = "#182825"
TEXT_MUTED = "#5c706b"
TEXT_ERROR = "#b0253b"

STYLE = f"""
QWidget {{
    color: {TEXT_DARK};
    background: {BG_MAIN};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}

/* Sidebar */
QFrame#sidebar {{
    background: {BG_SIDEBAR};
    border-right: 1px solid {BORDER_COLOR};
}}
QFrame#sidebar QWidget {{
    background: transparent;
}}
QFrame#sidebarBottom {{
    border-top: 1px solid {BORDER_COLOR};
    background: {BG_SIDEBAR};
}}

/* Bottom sidebar toolbar buttons */
QToolButton#sidebarToolBtn {{
    background: #ffffff;
    border: 1px solid #d0dbd6;
    border-radius: 5px;
    padding: 4px;
    min-width: 32px;
    max-width: 32px;
    min-height: 28px;
    max-height: 28px;
    font-weight: 700;
    font-size: 14px;
    color: #405550;
}}
QToolButton#sidebarToolBtn::menu-indicator {{
    image: none;
    width: 0px;
}}
QToolButton#sidebarToolBtn:hover {{
    background: #eef5f1;
    border-color: #a0b8ad;
    color: {ACCENT_TEAL};
}}
QToolButton#sidebarToolBtn:pressed {{
    background: #dceae3;
}}

/* Buttons */
QPushButton {{
    background: #ffffff;
    color: #203630;
    border: 1px solid #b5c7bf;
    border-radius: 6px;
    padding: 7px 15px;
    min-height: 20px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: #f0f6f3;
    border-color: #729688;
}}
QPushButton:pressed {{
    background: #e2ede7;
}}
QPushButton:focus {{
    border: 1px solid {ACCENT_TEAL};
}}
QPushButton:disabled {{
    background: #f2f5f4;
    color: #8c9d98;
    border-color: #dbe4df;
}}

QPushButton#primary {{
    color: #ffffff;
    background: {ACCENT_TEAL};
    border: 1px solid {ACCENT_TEAL};
    padding: 8px 18px;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {ACCENT_TEAL_HOVER};
    border-color: {ACCENT_TEAL_HOVER};
}}
QPushButton#primary:pressed {{
    background: {ACCENT_TEAL_PRESSED};
    border-color: {ACCENT_TEAL_PRESSED};
}}
QPushButton#primary:disabled {{
    color: #a2bbb3;
    background: #bfd6cd;
    border-color: #bfd6cd;
}}

QPushButton#moreBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 16px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0;
}}
QPushButton#moreBtn::menu-indicator {{
    image: none;
    width: 0px;
}}
QPushButton#moreBtn:hover {{
    background: #eef3f0;
    border-color: #dce5e0;
}}

/* Form inputs */
QLineEdit {{
    background: #ffffff;
    border: 1px solid #a9beb5;
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: {ACCENT_TEAL};
    selection-color: white;
}}
QLineEdit:focus {{
    border: 2px solid {ACCENT_TEAL};
    padding: 7px 9px;
}}
QLineEdit[invalid="true"] {{
    border-color: {TEXT_ERROR};
}}

QCheckBox {{
    spacing: 8px;
    color: #314440;
    font-size: 12.5px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid #99b8a8;
    border-radius: 4px;
    background: #ffffff;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_GREEN};
    border-color: {ACCENT_GREEN};
}}

/* Cards and Panels */
QFrame#contentCard {{
    background: #ffffff;
    border: 1px solid #d2ded7;
    border-radius: 8px;
}}
QFrame#dashedCard {{
    background: #f9fbf9;
    border: 1.5px dashed #b8ccc2;
    border-radius: 8px;
}}
QFrame#successCard {{
    background: #f2f9f5;
    border: 1px solid #b2dcce;
    border-radius: 8px;
}}
QFrame#errorCard {{
    background: #fdf5f6;
    border: 1px solid #f0bcc4;
    border-radius: 8px;
}}
QFrame#dividerLine {{
    background: #eef3f0;
    max-height: 1px;
    min-height: 1px;
}}

/* Progress bar */
QProgressBar {{
    background: #e0ece6;
    border: 0;
    border-radius: 3px;
    max-height: 6px;
}}
QProgressBar::chunk {{
    background: {ACCENT_TEAL};
    border-radius: 3px;
}}

/* Scroll area */
QScrollArea {{
    border: 0;
    background: transparent;
}}

/* Context Menu */
QMenu {{
    background: #ffffff;
    border: 1px solid #c2d4cb;
    border-radius: 6px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 18px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: #e6f4ef;
    color: {ACCENT_TEAL};
}}
"""


def draw_shield_lock_emblem(size: int = 90) -> QPixmap:
    """Vẽ minh họa Khiên + Ổ khóa theo phong cách Cryptomator."""
    pix = QPixmap(size * 2, size * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    scale = size / 90.0
    p.scale(scale, scale)

    # 1. Vẽ khiên ngoài màu bạc/xám
    shield = QPainterPath()
    shield.moveTo(45, 8)
    shield.cubicTo(68, 8, 82, 18, 82, 42)
    shield.cubicTo(82, 68, 45, 86, 45, 86)
    shield.cubicTo(45, 86, 8, 68, 8, 42)
    shield.cubicTo(8, 18, 22, 8, 45, 8)

    p.setPen(QPen(QColor("#d0dcd5"), 4))
    p.setBrush(QBrush(QColor("#f0f5f2")))
    p.drawPath(shield)

    # 2. Vành quai khóa màu bạc
    shackle = QPainterPath()
    shackle.moveTo(33, 44)
    shackle.lineTo(33, 33)
    shackle.arcTo(33, 21, 24, 24, 180, -180)
    shackle.lineTo(57, 44)
    p.setPen(QPen(QColor("#8fa89b"), 4.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(shackle)

    # 3. Thân khóa màu xanh lá (Cryptomator green)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#2ea44f")))
    p.drawRoundedRect(QRectF(26, 43, 38, 30), 5, 5)

    # 4. Lỗ khóa màu xanh đậm
    p.setBrush(QBrush(QColor("#154226")))
    p.drawEllipse(QRectF(42.5, 50, 5, 5))
    kh = QPainterPath()
    kh.moveTo(43.5, 53)
    kh.lineTo(46.5, 53)
    kh.lineTo(47.5, 62)
    kh.lineTo(42.5, 62)
    kh.closeSubpath()
    p.drawPath(kh)

    p.end()
    return pix


def draw_circle_badge(kind: str, size: int = 52) -> QPixmap:
    """Vẽ huy hiệu tròn lớn ở đầu trang bên phải."""
    pix = QPixmap(size * 2, size * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Nền tròn xanh teal
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(ACCENT_TEAL)))
    p.drawEllipse(0, 0, size, size)

    # Biểu tượng trắng bên trong
    scale = size / 24.0
    p.scale(scale, scale)
    pen = QPen(QColor("#ffffff"), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "restore":
        p.drawRoundedRect(QRectF(6, 10, 12, 10), 2, 2)
        shackle = QPainterPath()
        shackle.moveTo(8, 10)
        shackle.lineTo(8, 7)
        shackle.arcTo(8, 4, 8, 8, 180, -180)
        shackle.lineTo(16, 8)
        p.drawPath(shackle)
        p.drawLine(QPointF(12, 13), QPointF(12, 17))
        p.drawLine(QPointF(10, 15), QPointF(12, 17))
        p.drawLine(QPointF(14, 15), QPointF(12, 17))
    else:
        p.drawRoundedRect(QRectF(6, 10, 12, 10), 2, 2)
        shackle = QPainterPath()
        shackle.moveTo(8, 10)
        shackle.lineTo(8, 7)
        shackle.arcTo(8, 4, 8, 8, 180, -180)
        shackle.lineTo(16, 10)
        p.drawPath(shackle)
        p.drawPoint(QPointF(12, 15))

    p.end()
    return pix


def draw_icon(name: str, size: int = 20, color: str = ACCENT_TEAL) -> QPixmap:
    """Vẽ các biểu tượng nhỏ dạng vector."""
    pix = QPixmap(size * 2, size * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    scale = size / 24.0
    p.scale(scale, scale)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if name == "lock_closed":
        p.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        shackle = QPainterPath()
        shackle.moveTo(8, 10)
        shackle.lineTo(8, 7)
        shackle.arcTo(8, 4, 8, 8, 180, -180)
        shackle.lineTo(16, 10)
        p.drawPath(shackle)
        p.drawPoint(QPointF(12, 15.5))
    elif name == "lock_open":
        p.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        shackle = QPainterPath()
        shackle.moveTo(8, 10)
        shackle.lineTo(8, 7)
        shackle.arcTo(8, 4, 8, 8, 180, -180)
        shackle.lineTo(16, 8)
        p.drawPath(shackle)
        p.drawPoint(QPointF(12, 15.5))
    elif name == "eye":
        eye = QPainterPath()
        eye.moveTo(3, 12)
        eye.cubicTo(7, 6, 17, 6, 21, 12)
        eye.cubicTo(17, 18, 7, 18, 3, 12)
        p.drawPath(eye)
        p.drawEllipse(QRectF(9.5, 9.5, 5, 5))
    elif name == "eye_closed":
        eye = QPainterPath()
        eye.moveTo(3, 12)
        eye.cubicTo(7, 6, 17, 6, 21, 12)
        eye.cubicTo(17, 18, 7, 18, 3, 12)
        p.drawPath(eye)
        p.drawLine(QPointF(4, 4), QPointF(20, 20))
    elif name == "more":
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(QRectF(5, 10.5, 3, 3))
        p.drawEllipse(QRectF(10.5, 10.5, 3, 3))
        p.drawEllipse(QRectF(16, 10.5, 3, 3))
    elif name == "plus":
        p.drawLine(QPointF(12, 6), QPointF(12, 18))
        p.drawLine(QPointF(6, 12), QPointF(18, 12))
    elif name == "gear":
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(QRectF(9.5, 9.5, 5, 5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(7.5, 7.5, 9, 9))
        for angle in range(0, 360, 45):
            p.save()
            p.translate(12, 12)
            p.rotate(angle)
            p.drawLine(QPointF(0, 5), QPointF(0, 9))
            p.restore()
    elif name == "file":
        p.drawRoundedRect(QRectF(5, 3, 14, 18), 1.5, 1.5)
        p.drawLine(QPointF(8, 8), QPointF(16, 8))
        p.drawLine(QPointF(8, 12), QPointF(16, 12))
        p.drawLine(QPointF(8, 16), QPointF(13, 16))
    elif name == "folder":
        folder = QPainterPath()
        folder.moveTo(4, 7)
        folder.lineTo(9, 7)
        folder.lineTo(11, 9)
        folder.lineTo(20, 9)
        folder.lineTo(20, 19)
        folder.lineTo(4, 19)
        folder.closeSubpath()
        p.drawPath(folder)
    elif name == "archive":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.drawLine(QPointF(4, 9), QPointF(20, 9))
        p.drawLine(QPointF(10, 12), QPointF(14, 12))
        p.drawLine(QPointF(10, 14), QPointF(14, 14))

    p.end()
    return pix


class NavItem(QFrame):
    """Mục điều hướng dạng thẻ danh sách giống hệt Cryptomator."""
    clicked = Signal()

    def __init__(self, mode: str, title: str, subtitle: str):
        super().__init__()
        self.mode = mode
        self.raw_title = title
        self.default_subtitle = subtitle
        self.checked = False
        self.hovered = False
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        text_layout.addWidget(self.title_label)

        self.sub_label = QLabel(subtitle)
        text_layout.addWidget(self.sub_label)

        layout.addLayout(text_layout, 1)
        self.update_style()

    def set_subtitle(self, text: str):
        self.sub_label.setText(text if text else self.default_subtitle)

    def setChecked(self, checked: bool):
        self.checked = checked
        self.update_style()

    def isChecked(self) -> bool:
        return self.checked

    def enterEvent(self, event):
        self.hovered = True
        self.update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def update_style(self):
        icon_name = {"create": "lock_closed", "restore": "lock_open", "benchmark": "archive"}[self.mode]
        if self.checked:
            bg_color = "#e8f4ed"
            icon_color = ACCENT_TEAL
            title_color = ACCENT_TEAL
            sub_color = "#406057"
            font_weight = "650"
        elif self.hovered:
            bg_color = "#edf3f0"
            icon_color = "#4a605a"
            title_color = TEXT_DARK
            sub_color = TEXT_MUTED
            font_weight = "600"
        else:
            bg_color = "transparent"
            icon_color = "#60746e"
            title_color = TEXT_DARK
            sub_color = TEXT_MUTED
            font_weight = "600"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 0;
                border-radius: 0px;
            }}
        """)
        self.icon_label.setStyleSheet("background: transparent; border: 0;")
        self.icon_label.setPixmap(draw_icon(icon_name, 22, color=icon_color))

        self.title_label.setStyleSheet(f"""
            font-weight: {font_weight};
            font-size: 13.5px;
            color: {title_color};
            background: transparent;
            border: 0;
        """)
        self.sub_label.setStyleSheet(f"""
            color: {sub_color};
            font-size: 11.5px;
            background: transparent;
            border: 0;
        """)


class CryptomatorPasswordDialog(QDialog):
    """Hộp thoại mật khẩu có dải tiêu đề xanh lá và biểu tượng khiên khóa như Cryptomator."""
    def __init__(self, parent, title: str, filename: str, *, repeat: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(530)
        self.drag_position = None
        self.repeat = repeat

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 15, 15, 15)

        card = QFrame()
        card.setObjectName("dialogCard")
        card.setStyleSheet(f"""
            QFrame#dialogCard {{
                background: #f8faf8;
                border: 1.5px solid {ACCENT_GREEN};
                border-radius: 8px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 95))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 1. Header bar xanh lá
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {ACCENT_GREEN};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom: 0px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 10, 8)
        header_layout.setSpacing(8)

        header_icon = QLabel()
        header_icon.setPixmap(draw_icon("lock_closed", 16, color="#ffffff"))
        header_icon.setStyleSheet("background: transparent; border: 0;")
        header_layout.addWidget(header_icon)

        header_title = QLabel(title)
        header_title.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 13px; background: transparent; border: 0;")
        header_layout.addWidget(header_title, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ffffff;
                border: 0;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #0f5c3c;
                border-radius: 12px;
            }
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        card_layout.addWidget(header)

        # 2. Body dialog
        body = QWidget()
        body.setStyleSheet("background: transparent; border: 0;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 24, 20)
        body_layout.setSpacing(18)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        emblem = QLabel()
        emblem.setPixmap(draw_shield_lock_emblem(86))
        emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_col.addWidget(emblem)
        left_col.addStretch()
        body_layout.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(8)

        prompt_text = f'Nhập mật khẩu cho "{filename}":'
        prompt = QLabel(prompt_text)
        prompt.setTextFormat(Qt.TextFormat.PlainText)
        prompt.setStyleSheet("font-size: 13px; font-weight: 600; color: #202d2a;")
        prompt.setWordWrap(True)
        right_col.addWidget(prompt)

        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setPlaceholderText("Nhập mật khẩu…")
        self.password_field.setInputMethodHints(
            Qt.InputMethodHint.ImhHiddenText | Qt.InputMethodHint.ImhNoPredictiveText | Qt.InputMethodHint.ImhSensitiveData
        )
        self.password_action = self.password_field.addAction(
            QIcon(draw_icon("eye", 16, color="#5c706b")), QLineEdit.ActionPosition.TrailingPosition
        )
        self.password_action.triggered.connect(lambda: self.toggle_visibility(self.password_field, self.password_action))
        right_col.addWidget(self.password_field)

        self.confirm_field = None
        if repeat:
            confirm_label = QLabel("Nhập lại mật khẩu:")
            confirm_label.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #202d2a; margin-top: 4px;")
            right_col.addWidget(confirm_label)

            self.confirm_field = QLineEdit()
            self.confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_field.setPlaceholderText("Nhập lại mật khẩu xác nhận…")
            self.confirm_field.setInputMethodHints(
                Qt.InputMethodHint.ImhHiddenText | Qt.InputMethodHint.ImhNoPredictiveText | Qt.InputMethodHint.ImhSensitiveData
            )
            self.confirm_action = self.confirm_field.addAction(
                QIcon(draw_icon("eye", 16, color="#5c706b")), QLineEdit.ActionPosition.TrailingPosition
            )
            self.confirm_action.triggered.connect(lambda: self.toggle_visibility(self.confirm_field, self.confirm_action))
            right_col.addWidget(self.confirm_field)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {TEXT_ERROR}; font-size: 12px; font-weight: 600;")
        self.error_label.hide()
        right_col.addWidget(self.error_label)

        if repeat:
            right_col.addWidget(QLabel("AES-256 · mã hóa cả tên tệp"))
        right_col.addSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        action_title = "Tạo gói" if repeat else "Mở khóa"
        self.confirm_btn = QPushButton(action_title)
        self.confirm_btn.setObjectName("primary")
        self.confirm_btn.setStyleSheet(f"""
            QPushButton#primary {{
                background: {ACCENT_GREEN};
                border: 1px solid {ACCENT_GREEN};
                color: #ffffff;
                font-weight: 700;
                padding: 7px 20px;
                border-radius: 6px;
            }}
            QPushButton#primary:hover {{
                background: {ACCENT_GREEN_HOVER};
            }}
            QPushButton#primary:disabled {{
                background: #b4d8c6;
                border-color: #b4d8c6;
                color: #ffffff;
            }}
        """)
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setMinimumWidth(95)
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setDefault(True)
        btn_layout.addWidget(self.confirm_btn)

        right_col.addLayout(btn_layout)
        body_layout.addLayout(right_col, 1)
        card_layout.addWidget(body)

        outer_layout.addWidget(card)

        self.password_field.textChanged.connect(self.validate)
        if self.confirm_field is not None:
            self.confirm_field.textChanged.connect(self.validate)
        self.validate()
        self.password_field.setFocus()

        header.mousePressEvent = self.header_mouse_press
        header.mouseMoveEvent = self.header_mouse_move

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            geo = self.parent().geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def header_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def header_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def toggle_visibility(self, field: QLineEdit, action: QAction):
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
            action.setIcon(QIcon(draw_icon("eye_closed", 16, color="#5c706b")))
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            action.setIcon(QIcon(draw_icon("eye", 16, color="#5c706b")))

    def validate(self):
        pwd = self.password_field.text()
        if self.repeat and self.confirm_field is not None:
            cfm = self.confirm_field.text()
            mismatch = bool(cfm) and (pwd != cfm)
            self.error_label.setText("Hai mật khẩu không khớp." if mismatch else "")
            self.error_label.setVisible(mismatch)
            valid = bool(pwd) and (pwd == cfm)
        else:
            valid = bool(pwd)
            self.error_label.hide()
        self.confirm_btn.setEnabled(valid)

    def clear(self):
        self.password_field.clear()
        if self.confirm_field is not None:
            self.confirm_field.clear()


class OperationPage(QWidget):
    """Trang thao tác bên phải với bố cục thẳng trục và các trạng thái rõ ràng."""
    def __init__(self, window, mode: str):
        super().__init__()
        self.window = window
        self.mode = mode
        self.creating = mode == "create"
        self.source: Path | None = None
        self.destination: Path | None = None
        self.custom_destination = False
        self.require_destination_choice = False
        self.result: Result | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 28, 36, 24)
        main_layout.setSpacing(18)

        # 1. Header trên cùng phong cách Cryptomator
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)

        self.badge = QLabel()
        self.badge.setPixmap(draw_circle_badge(self.mode, 50))
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 2, 0, 0)
        title_box.setSpacing(3)

        title_text = "Mã hóa" if self.creating else "Khôi phục"
        self.heading_label = QLabel(title_text)
        self.heading_label.setStyleSheet("font-size: 22px; font-weight: 700; color: #162623;")
        title_box.addWidget(self.heading_label)

        self.sub_heading = QLabel("~\\Chưa chọn tệp nguồn" if self.creating else "~\\Chưa chọn gói .7z")
        self.sub_heading.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12.5px;")
        title_box.addWidget(self.sub_heading)
        header.addLayout(title_box, 1)

        self.more_btn = QPushButton()
        self.more_btn.setObjectName("moreBtn")
        self.more_btn.setIcon(QIcon(draw_icon("more", 18, color="#5c706b")))
        self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_menu = QMenu(self.more_btn)
        self.more_menu.addAction("Chọn tệp nguồn…" if self.creating else "Chọn gói .7z…", self.pick_file)
        if self.creating:
            self.more_menu.addAction("Chọn thư mục nguồn…", self.pick_folder)
        self.more_menu.addAction("Đổi nơi lưu…", self.pick_destination)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Đặt lại", self.reset_page)
        self.more_btn.setMenu(self.more_menu)
        header.addWidget(self.more_btn, 0, Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(header)

        line = QFrame()
        line.setObjectName("dividerLine")
        main_layout.addWidget(line)

        # 2. Vùng làm việc chính thẳng trục với tiêu đề
        self.work_area = QVBoxLayout()
        self.work_area.setContentsMargins(0, 0, 0, 0)
        self.work_area.setSpacing(14)
        main_layout.addLayout(self.work_area)

        # Bảng 1: Chưa chọn tệp (Dashed Card)
        self.setup_empty_card()

        # Bảng 2: Đã chọn tệp (Details Card + Nút tác vụ)
        self.setup_selected_card()

        # Bảng 3: Đang thực hiện (Progress Card)
        self.setup_progress_card()

        # Bảng 4: Kết quả (Success/Error Card)
        self.setup_result_card()

        main_layout.addStretch(1)
        self.show_state("empty")

    def setup_empty_card(self):
        self.empty_card = QFrame()
        self.empty_card.setObjectName("dashedCard")
        layout = QVBoxLayout(self.empty_card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        headline = QLabel("Chọn dữ liệu cần bảo vệ" if self.creating else "Chọn gói .7z cần khôi phục")
        headline.setStyleSheet("font-size: 15px; font-weight: 650; color: #1c2e2a;")
        layout.addWidget(headline)

        desc = QLabel(
            "Tạo gói lưu trữ chuẩn .7z được mã hóa AES-256 kèm tính năng ẩn tên tệp (Header Encryption) "
            "và đối chiếu SHA-256 từng tệp để chống sửa đổi." if self.creating else
            "Giải nén gói .7z do ANTT CKI tạo ra và tự động đối chiếu mã băm SHA-256 thực tế của từng tệp sau khi ghi đĩa."
        )
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12.5px; line-height: 1.4;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.setSpacing(10)

        self.btn_pick_file = QPushButton("Chọn tệp…" if self.creating else "Chọn gói .7z…")
        self.btn_pick_file.setObjectName("primary")
        self.btn_pick_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_file.clicked.connect(self.pick_file)
        btn_row.addWidget(self.btn_pick_file)

        if self.creating:
            self.btn_pick_folder = QPushButton("Chọn thư mục…")
            self.btn_pick_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_pick_folder.clicked.connect(self.pick_folder)
            btn_row.addWidget(self.btn_pick_folder)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.work_area.addWidget(self.empty_card)

    def setup_selected_card(self):
        self.selected_container = QWidget()
        layout = QVBoxLayout(self.selected_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("contentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        # Hàng 1: Nguồn
        source_row = QHBoxLayout()
        source_row.setSpacing(12)
        self.src_icon = QLabel()
        self.src_icon.setFixedSize(24, 24)
        source_row.addWidget(self.src_icon, 0, Qt.AlignmentFlag.AlignTop)

        src_text = QVBoxLayout()
        src_text.setSpacing(2)
        self.src_name = QLabel()
        self.src_name.setStyleSheet("font-weight: 650; font-size: 14px; color: #1c2e2a;")
        self.src_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        src_text.addWidget(self.src_name)

        self.src_path = QLabel()
        self.src_path.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11.5px;")
        self.src_path.setWordWrap(True)
        self.src_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        src_text.addWidget(self.src_path)
        source_row.addLayout(src_text, 1)

        self.btn_change_src = QPushButton("Đổi")
        self.btn_change_src.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.creating:
            src_menu = QMenu(self.btn_change_src)
            src_menu.addAction("Chọn tệp khác…", self.pick_file)
            src_menu.addAction("Chọn thư mục khác…", self.pick_folder)
            self.btn_change_src.setMenu(src_menu)
        else:
            self.btn_change_src.clicked.connect(self.pick_file)
        source_row.addWidget(self.btn_change_src, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(source_row)

        card_layout.addWidget(QFrame(objectName="dividerLine"))

        # Hàng 2: Đích dự kiến
        dst_row = QHBoxLayout()
        dst_row.setSpacing(12)
        self.dst_icon = QLabel()
        self.dst_icon.setFixedSize(24, 24)
        self.dst_icon.setPixmap(draw_icon("archive" if self.creating else "folder", 20, color=ACCENT_TEAL))
        dst_row.addWidget(self.dst_icon, 0, Qt.AlignmentFlag.AlignTop)

        dst_text = QVBoxLayout()
        dst_text.setSpacing(2)
        dst_caption = QLabel("Lưu gói tại:" if self.creating else "Khôi phục vào:")
        dst_caption.setStyleSheet("font-weight: 600; font-size: 13px; color: #2e443f;")
        dst_text.addWidget(dst_caption)

        self.dst_path = QLabel()
        self.dst_path.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11.5px;")
        self.dst_path.setWordWrap(True)
        self.dst_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dst_text.addWidget(self.dst_path)
        dst_row.addLayout(dst_text, 1)

        self.btn_change_dst = QPushButton("Đổi nơi lưu")
        self.btn_change_dst.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_dst.clicked.connect(self.pick_destination)
        dst_row.addWidget(self.btn_change_dst, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(dst_row)

        if self.creating:
            compression_row = QHBoxLayout()
            compression_row.addWidget(QLabel("Chế độ nén"))
            self.compression = QComboBox()
            for mode in ("LZMA2", "Store"):
                self.compression.addItem(COMPRESSION[mode], mode)
            compression_row.addWidget(self.compression, 1)
            card_layout.addLayout(compression_row)

        layout.addWidget(card)

        # Nút kích hoạt chính (Tạo gói mã hóa / Khôi phục dữ liệu)
        btn_action_row = QHBoxLayout()
        btn_action_row.setContentsMargins(0, 4, 0, 0)
        btn_action_row.addStretch()

        self.btn_submit = QPushButton("Tạo gói mã hóa" if self.creating else "Khôi phục dữ liệu")
        self.btn_submit.setObjectName("primary")
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet("padding: 9px 24px; font-size: 13.5px; font-weight: 700;")
        self.btn_submit.clicked.connect(lambda: self.window.request_password(self))
        btn_action_row.addWidget(self.btn_submit)

        layout.addLayout(btn_action_row)
        self.work_area.addWidget(self.selected_container)

    def setup_progress_card(self):
        self.progress_card = QFrame()
        self.progress_card.setObjectName("contentCard")
        layout = QVBoxLayout(self.progress_card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.progress_title = QLabel("Đang xử lý…")
        self.progress_title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {ACCENT_TEAL};")
        layout.addWidget(self.progress_title)

        self.progress_step = QLabel("Chuẩn bị tác vụ…")
        self.progress_step.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12.5px;")
        self.progress_step.setWordWrap(True)
        layout.addWidget(self.progress_step)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        self.work_area.addWidget(self.progress_card)

    def setup_result_card(self):
        self.result_card = QFrame()
        self.result_card.setObjectName("successCard")
        self.result_layout = QVBoxLayout(self.result_card)
        self.result_layout.setContentsMargins(18, 16, 18, 16)
        self.result_layout.setSpacing(10)

        self.result_title = QLabel()
        self.result_title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {ACCENT_TEAL};")
        self.result_layout.addWidget(self.result_title)

        self.result_details = QLabel()
        self.result_details.setStyleSheet(f"color: {TEXT_DARK}; font-size: 12.5px; line-height: 1.4;")
        self.result_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result_details.setWordWrap(True)
        self.result_layout.addWidget(self.result_details)

        self.result_actions = QHBoxLayout()
        self.result_actions.setContentsMargins(0, 4, 0, 0)
        self.result_actions.setSpacing(10)

        self.btn_open_folder = QPushButton("Mở thư mục")
        self.btn_open_folder.setObjectName("primary")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self.open_output)
        self.result_actions.addWidget(self.btn_open_folder)

        if self.creating:
            self.btn_restore_now = QPushButton("Khôi phục gói này")
            self.btn_restore_now.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_restore_now.clicked.connect(lambda: self.window.restore_result(self.result))
            self.result_actions.addWidget(self.btn_restore_now)

        self.result_actions.addStretch()
        self.result_layout.addLayout(self.result_actions)
        self.work_area.addWidget(self.result_card)

    def show_state(self, state: str):
        self.empty_card.setVisible(state == "empty")
        self.selected_container.setVisible(state in ("selected", "running", "result"))
        self.progress_card.setVisible(state == "running")
        self.result_card.setVisible(state == "result")
        self.btn_submit.setEnabled(state != "running" and not self.require_destination_choice)
        self.btn_change_src.setEnabled(state != "running")
        self.btn_change_dst.setEnabled(state != "running")

    def reset_page(self):
        self.source = None
        self.destination = None
        self.custom_destination = False
        self.require_destination_choice = False
        self.result = None
        self.sub_heading.setText("~\\Chưa chọn tệp nguồn" if self.creating else "~\\Chưa chọn gói .7z")
        self.window.update_nav_subtitles()
        self.show_state("empty")

    def pick_file(self):
        title = "Chọn tệp nguồn" if self.creating else "Chọn gói .7z"
        mask = "Tất cả tệp (*)" if self.creating else "Gói 7-Zip (*.7z)"
        initial = str(self.source.parent) if self.source else str(PROJECT_DIR)
        selection, _ = QFileDialog.getOpenFileName(self, title, initial, mask)
        if selection:
            self.set_source(Path(selection))

    def pick_folder(self):
        initial = str(self.source.parent) if self.source else str(PROJECT_DIR)
        selection = QFileDialog.getExistingDirectory(self, "Chọn thư mục nguồn", initial)
        if selection:
            self.set_source(Path(selection))

    def set_source(self, source: Path):
        self.source = source
        name = source.name or str(source)
        self.src_name.setText(name)
        self.src_path.setText(str(source))
        self.src_icon.setPixmap(draw_icon("folder" if source.is_dir() else "file", 20, color=ACCENT_TEAL))
        self.sub_heading.setText(f"~\\{name}")
        self.window.update_nav_subtitles()

        if not self.custom_destination:
            if self.creating:
                dest = source.parent / f"{source.name or 'Ban sao'}.7z"
            else:
                dest = source.parent / f"{source.stem} - khôi phục"
            self.set_destination(dest)

        self.show_state("selected")
        self.btn_submit.setFocus()

    def set_destination(self, destination: Path, *, custom: bool = False):
        self.destination = destination
        self.custom_destination = custom
        if custom:
            self.require_destination_choice = False
            self.btn_submit.setEnabled(not self.window.busy)
        self.dst_path.setText("Chưa chọn nơi lưu" if self.require_destination_choice else str(destination))

    def pick_destination(self):
        curr = self.destination or (self.source.parent if self.source else PROJECT_DIR)
        if self.creating:
            saved, _ = QFileDialog.getSaveFileName(
                self, "Lưu gói mã hóa", str(curr), "Gói 7-Zip (*.7z)",
                options=QFileDialog.Option.DontConfirmOverwrite
            )
            if not saved:
                return
            dest = Path(saved)
            if dest.suffix.lower() != ".7z":
                dest = dest.with_name(dest.name + ".7z")
        else:
            parent = QFileDialog.getExistingDirectory(
                self, "Chọn thư mục chứa dữ liệu khôi phục", str(curr.parent if curr else str(PROJECT_DIR))
            )
            if not parent:
                return
            name, ok = QInputDialog.getText(self, "Đặt tên thư mục", "Tên thư mục mới:", text=curr.name if curr else "Gói khôi phục")
            if not ok or not name.strip():
                return
            try:
                if len(path_parts(name.strip())) != 1:
                    raise AppError("Hãy nhập một tên thư mục duy nhất.")
            except AppError as error:
                self.show_error_result("Tên thư mục không hợp lệ", str(error))
                return
            dest = Path(parent) / name.strip()

        self.set_destination(dest, custom=True)

    def show_working(self, title: str, step: str):
        self.progress_title.setText(title)
        self.progress_step.setText(step)
        self.show_state("running")

    def update_progress_step(self, step: str):
        self.progress_step.setText(step)

    def show_success_result(self, result: Result):
        self.result = result
        self.result_card.setObjectName("successCard")
        self.result_card.setStyleSheet("")
        self.result_title.setText("✓ Đã tạo gói mã hóa thành công" if self.creating else "✓ Đã khôi phục dữ liệu thành công")
        self.result_title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {ACCENT_TEAL};")

        if self.creating:
            count_str = f"{result.count} tệp"
        else:
            count_str = f"{result.count}/{result.count} tệp khớp SHA-256"

        details = (
            f"<b>Tên đầu ra:</b> {escape(result.path.name)}<br>"
            f"<b>Vị trí lưu:</b> {escape(str(result.path))}<br>"
            f"<b>Số tệp:</b> {count_str}<br>"
            f"<b>Thời gian:</b> {result.seconds:.2f} giây"
        )
        self.result_details.setText(details)
        self.btn_open_folder.setVisible(True)
        if self.creating:
            self.btn_restore_now.setVisible(True)
        self.show_state("result")

    def show_error_result(self, title: str, message: str):
        self.result = None
        self.result_card.setObjectName("errorCard")
        self.result_card.setStyleSheet("")
        self.result_title.setText(f"✕ {title}")
        self.result_title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {TEXT_ERROR};")
        self.result_details.setText(f"<b>Chi tiết:</b> {escape(message)}")
        self.btn_open_folder.setVisible(False)
        if self.creating:
            self.btn_restore_now.setVisible(False)
        self.show_state("result")

    def open_output(self):
        if self.result is None:
            return
        folder = self.result.path.parent if self.creating else self.result.path
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            self.result_details.setText(self.result_details.text() + "<br><font color='#b0253b'>Không thể mở thư mục Explorer.</font>")


class App(QMainWindow):
    """Cửa sổ chính và bộ điều phối một tác vụ nền tại một thời điểm."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {APP_DESCRIPTION}")
        self.setWindowIcon(QIcon(draw_circle_badge("create", 32)))
        self.resize(1160, 720)
        self.setMinimumSize(850, 600)

        self.busy = False
        self.events: SimpleQueue = SimpleQueue()
        self.pages: dict[str, QWidget] = {}
        self.nav_items: dict[str, NavItem] = {}

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Cột trái (Sidebar)
        root_layout.addWidget(self.build_sidebar())

        # Cột phải (Stack các trang chức năng)
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        self.setCentralWidget(root)

        for page in (OperationPage(self, "create"), ExplorePage(self), BenchmarkPage(self)):
            mode = page.mode
            self.pages[mode] = page
            self.stack.addWidget(page)

        self.navigate("create")

        # Bộ hẹn giờ đón sự kiện tiến trình nền
        self.poller = QTimer(self)
        self.poller.setInterval(30)
        self.poller.timeout.connect(self.poll)
        self.poller.start()

    def build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Phần thương hiệu góc trên
        brand = QWidget()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(18, 20, 18, 14)
        brand_layout.setSpacing(10)

        brand_icon = QLabel()
        brand_icon.setPixmap(draw_circle_badge("create", 28))
        brand_layout.addWidget(brand_icon)

        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(1)
        brand_title = QLabel(APP_NAME)
        brand_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #162623;")
        brand_text_box.addWidget(brand_title)

        brand_sub = QLabel(APP_DESCRIPTION)
        brand_sub.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        brand_text_box.addWidget(brand_sub)

        brand_layout.addLayout(brand_text_box, 1)
        layout.addWidget(brand)

        # Dải mục danh sách điều hướng phong cách Cryptomator
        items_box = QVBoxLayout()
        items_box.setContentsMargins(0, 4, 0, 0)
        items_box.setSpacing(2)

        nav_items = [
            ("create", "Mã hóa", "~\\Tạo gói .7z AES-256"),
            ("restore", "Khám phá và khôi phục", "Duyệt gói và kiểm tra SHA-256"),
            ("benchmark", "So sánh cấu hình", "Đo Store và LZMA2"),
        ]

        for mode, title, sub in nav_items:
            item = NavItem(mode, title, sub)
            item.clicked.connect(lambda m=mode: self.navigate(m))
            self.nav_items[mode] = item
            items_box.addWidget(item)

        layout.addLayout(items_box)
        layout.addStretch(1)

        # Thanh công cụ đáy cột trái (+ và ⚙)
        bottom_bar = QFrame()
        bottom_bar.setObjectName("sidebarBottom")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(14, 10, 14, 10)
        bottom_layout.setSpacing(8)

        self.btn_plus = QToolButton()
        self.btn_plus.setObjectName("sidebarToolBtn")
        self.btn_plus.setIcon(QIcon(draw_icon("plus", 16, color="#405550")))
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_plus.setToolTip("Chọn nhanh tệp hoặc gói mới")
        plus_menu = QMenu(self.btn_plus)
        plus_menu.addAction("Mã hóa tệp…", lambda: self.quick_select("file"))
        plus_menu.addAction("Mã hóa thư mục…", lambda: self.quick_select("folder"))
        plus_menu.addAction("Khôi phục gói .7z…", lambda: self.quick_select("restore"))
        self.btn_plus.setMenu(plus_menu)
        bottom_layout.addWidget(self.btn_plus)

        bottom_layout.addStretch(1)

        self.btn_gear = QToolButton()
        self.btn_gear.setObjectName("sidebarToolBtn")
        self.btn_gear.setIcon(QIcon(draw_icon("gear", 16, color="#405550")))
        self.btn_gear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gear.setToolTip("Thông tin ứng dụng")
        self.btn_gear.clicked.connect(self.show_about)
        bottom_layout.addWidget(self.btn_gear)

        layout.addWidget(bottom_bar)
        return sidebar

    def quick_select(self, kind: str):
        if kind == "restore":
            self.navigate("restore")
            self.pages["restore"].pick_file()
        elif kind == "folder":
            self.navigate("create")
            self.pages["create"].pick_folder()
        else:
            self.navigate("create")
            self.pages["create"].pick_file()

    def show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Giới thiệu {APP_NAME}")
        msg.setText(f"<b>{APP_NAME}</b><br>{APP_DESCRIPTION}")
        msg.setInformativeText(
            "Đồ án An toàn Thông tin · Nhóm 8<br><br>"
            "Gói .7z hỗ trợ Store và LZMA2, AES-256 và mã hóa tên tệp.<br>"
            "Kiểm chứng SHA-256 theo manifest, khôi phục toàn bộ hoặc theo tệp."
        )
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def navigate(self, mode: str):
        for m, item in self.nav_items.items():
            item.setChecked(m == mode)
        self.stack.setCurrentWidget(self.pages[mode])

    def update_nav_subtitles(self):
        for mode, page in self.pages.items():
            if page.source is not None:
                self.nav_items[mode].set_subtitle(f"~\\{page.source.name}")
            else:
                self.nav_items[mode].set_subtitle("")

    def restore_result(self, result: Result | None):
        if result is not None and not self.busy:
            restore_page = self.pages["restore"]
            restore_page.set_source(result.path)
            self.navigate("restore")

    def choose_recommended_destination(self, page):
        page.require_destination_choice = True
        page.set_destination(page.destination)
        page.btn_submit.setEnabled(False)
        page.pick_destination()

    def ask_password(self, title: str, filename: str, *, repeat: bool = False) -> str:
        if self.busy:
            return ""
        dialog = CryptomatorPasswordDialog(self, title, filename, repeat=repeat)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        password = dialog.password_field.text() if accepted else ""
        dialog.clear()
        dialog.deleteLater()

        return password

    def request_password(self, page: OperationPage):
        if self.busy or page.source is None or page.destination is None or page.require_destination_choice:
            return

        title = f'Đặt mật khẩu cho "{page.source.name}"'
        password = self.ask_password(title, page.source.name, repeat=True)
        if not password:
            return
        source, destination = page.source, page.destination
        compression = page.compression.currentData()
        self.start_task(page, lambda progress: create_package(source, destination, password, progress, compression=compression))

    def set_busy(self, busy: bool):
        self.busy = busy
        self.btn_plus.setEnabled(not busy)
        for page in self.pages.values():
            page.setEnabled(not busy)

    def start_task(self, page: QWidget, task: Callable[[Progress], object]):
        if self.busy:
            return
        self.set_busy(True)
        title = "Đang tạo gói mã hóa…" if page.mode == "create" else "Đang xử lý…"
        page.show_working(title, "Chuẩn bị tác vụ và kiểm tra môi trường…")
        Thread(target=self.worker_thread, args=(page.mode, task), daemon=True).start()

    def worker_thread(self, mode: str, task: Callable[[Progress], object]):
        def progress_callback(step: str):
            self.events.put((mode, "step", step))

        try:
            result = task(progress_callback)
        except AppError as err:
            self.events.put((mode, "error", str(err)))
        except OSError as err:
            reason = {
                5: "Quyền truy cập bị từ chối hoặc tệp đang được sử dụng.",
                32: "Tệp đang được một chương trình khác sử dụng.",
                112: "Ổ đĩa không đủ dung lượng.",
                206: "Đường dẫn dài hơn giới hạn Windows hỗ trợ.",
                223: "Tệp vượt quá giới hạn kích thước vùng lưu.",
            }.get(getattr(err, "winerror", None), "Hãy kiểm tra đường dẫn, quyền truy cập và dung lượng đĩa.")
            self.events.put((mode, "error", f"Lỗi đọc/ghi hệ thống tập tin. {reason}"))
        except Exception:
            self.events.put((mode, "error", "Tác vụ gặp lỗi không lường trước. Hãy thử lại."))
        else:
            self.events.put((mode, "success", result))

    def poll(self):
        while True:
            try:
                mode, event, value = self.events.get_nowait()
            except Empty:
                return

            page = self.pages[mode]
            if event == "step":
                page.update_progress_step(value)
                continue

            self.set_busy(False)
            if event == "error":
                page.show_error_result("Không thể hoàn tất tác vụ", value)
            else:
                page.show_success_result(value)

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    window = App()
    window.show()
    window.raise_()
    window.activateWindow()
    try:
        import ctypes
        hwnd = int(window.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
