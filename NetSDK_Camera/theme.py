# coding=utf-8
"""
theme.py  —  Dahua NetSDK Control Center
Toàn bộ màu sắc, font, shadow, và QSS global dùng chung.
Import:  from theme import T, GLOBAL_QSS, make_shadow
"""
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QFont


# ══════════════════════════════════════════════════════════════════════
#  COLOR TOKENS  —  DARK (default)
# ══════════════════════════════════════════════════════════════════════
class T:
    # ── Backgrounds / surfaces ────────────────────────────────────────
    BG = S1 = S2 = S3 = S4 = SIDEBAR = TOPBAR = "#000000"

    # ── Borders ───────────────────────────────────────────────────────
    BD = BD2 = BD3 = "#FFFFFF"

    # ── Text ──────────────────────────────────────────────────────────
    P1      = "#FFFFFF"   # primary text — titles, labels
    P2 = P3 = "#FFFFFF"

    # ── Status / feedback ─────────────────────────────────────────────
    ACCENT = GREEN = AMBER = RED = "#FFFFFF"

    # ── Demo category accents (per-card accent color) ─────────────────
    CAT_DEVICE = CAT_CAMERA = CAT_CAMERA2 = CAT_ALARM = CAT_PLAYBACK = CAT_CONTROL = CAT_AI = CAT_TRAFFIC = "#FFFFFF"

    # ── Typography ────────────────────────────────────────────────────
    FONT = "Segoe UI"     # primary — Windows native, fallback Arial
    MONO = "Courier New"  # monospace — module paths, version strings

    # ── Sizing constants ──────────────────────────────────────────────
    RADIUS_CARD   = 18    # card border-radius px
    RADIUS_BTN    = 10    # button border-radius px
    RADIUS_CHIP   = 9     # category chip / small button
    RADIUS_INPUT  = 10    # search input

    SIDEBAR_W     = 210   # sidebar fixed width px
    CARD_W        = 288   # demo card width px
    CARD_H        = 178   # demo card height px (font +4px → taller)
    TOPBAR_H      = 60    # topbar fixed height px
    STATUSBAR_H   = 38    # statusbar fixed height px


# ══════════════════════════════════════════════════════════════════════
#  COLOR TOKENS  —  LIGHT
#  Sidebar giữ nguyên dark (--sb-* vars trong CSS, không đổi).
#  Chỉ vùng content thay đổi khi toggle sang light.
# ══════════════════════════════════════════════════════════════════════
class TLight:
    # ── Backgrounds / surfaces ────────────────────────────────────────
    BG = S1 = S2 = S3 = S4 = SIDEBAR = TOPBAR = "#FFFFFF"

    # ── Borders ───────────────────────────────────────────────────────
    BD = BD2 = BD3 = "#000000"

    # ── Text ──────────────────────────────────────────────────────────
    P1 = P2 = P3 = "#000000"

    # ── Status / feedback ─────────────────────────────────────────────
    ACCENT = GREEN = AMBER = RED = "#000000"

    # ── Card accent colors stay the same ──────────────────────────────
    CAT_DEVICE = CAT_CAMERA = CAT_CAMERA2 = CAT_ALARM = CAT_PLAYBACK = CAT_CONTROL = CAT_AI = CAT_TRAFFIC = "#000000"

    # ── Typography / sizing — same as T ──────────────────────────────
    FONT        = T.FONT
    MONO        = T.MONO
    RADIUS_CARD = T.RADIUS_CARD
    RADIUS_BTN  = T.RADIUS_BTN
    RADIUS_CHIP = T.RADIUS_CHIP


# ══════════════════════════════════════════════════════════════════════
#  THEMES REGISTRY
#  Dùng cho code Python muốn biết token theo theme name.
#  Web UI tự handle qua CSS variables + data-theme attribute.
# ══════════════════════════════════════════════════════════════════════
THEMES = {
    "dark":  T,
    "light": TLight,
}


# ══════════════════════════════════════════════════════════════════════
#  SHADOW FACTORY
# ══════════════════════════════════════════════════════════════════════
def make_shadow(widget, blur: int = 24, y_off: int = 6, alpha: int = 80):
    """Attach a drop shadow QGraphicsEffect to widget. Returns the effect."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y_off)
    c = QColor("#000000")
    c.setAlpha(alpha)
    eff.setColor(c)
    widget.setGraphicsEffect(eff)
    return eff


# Shortcut kept on T class for backward compat with launcher.py
T.shadow = staticmethod(make_shadow)


# ══════════════════════════════════════════════════════════════════════
#  FONT HELPERS
# ══════════════════════════════════════════════════════════════════════
def font(size: int, bold: bool = False) -> QFont:
    return QFont(T.FONT, size, QFont.Bold if bold else QFont.Normal)

def font_mono(size: int) -> QFont:
    return QFont(T.MONO, size)


# ══════════════════════════════════════════════════════════════════════
#  GLOBAL QSS  —  dùng cho QMessageBox (launcher dùng WebEngine nên
#  không cần QSS cho widget layout; chỉ dialog còn là native PyQt5).
#  Áp vào app:  app.setStyleSheet(GLOBAL_QSS)
#  Để switch theme: app.setStyleSheet(GLOBAL_QSS_LIGHT)
# ══════════════════════════════════════════════════════════════════════
GLOBAL_QSS = f"""
/* ── Scroll bars ─────────────────────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}

QScrollBar:vertical {{
    background: {T.S1};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {T.BD3};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {T.ACCENT}; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical  {{ background: none; }}

QScrollBar:horizontal {{
    background: {T.S1};
    height: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {T.BD3};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {T.ACCENT}; }}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Line edit / search ──────────────────────────────────────── */
QLineEdit {{
    background-color: {T.S2};
    color: {T.P1};
    border: 1px solid {T.BD2};
    border-radius: {T.RADIUS_INPUT}px;
    padding: 0 14px;
    font-family: '{T.FONT}';
    font-size: 10px;
    selection-background-color: {T.ACCENT};
}}
QLineEdit:focus {{
    border: 1.5px solid {T.ACCENT};
    background-color: {T.S3};
}}
QLineEdit::placeholder {{
    color: {T.P3};
}}

/* ── Tooltip ─────────────────────────────────────────────────── */
QToolTip {{
    background-color: {T.S3};
    color: {T.P1};
    border: 1px solid {T.BD2};
    border-radius: 6px;
    padding: 4px 10px;
    font-family: '{T.FONT}';
    font-size: 9px;
}}

/* ── Message box ─────────────────────────────────────────────── */
QMessageBox {{
    background-color: {T.S1};
    color: {T.P1};
    font-family: '{T.FONT}';
}}
QMessageBox QLabel {{
    color: {T.P1};
    background: transparent;
    font-family: '{T.FONT}';
    font-size: 10px;
}}
QMessageBox QPushButton {{
    background-color: {T.S3};
    color: {T.P1};
    border: 1px solid {T.BD2};
    border-radius: {T.RADIUS_BTN}px;
    padding: 6px 20px;
    font-family: '{T.FONT}';
    font-size: 9px;
    min-width: 80px;
}}
QMessageBox QPushButton:hover {{
    background-color: {T.ACCENT};
    border-color: {T.ACCENT};
    color: white;
}}
"""


GLOBAL_QSS_LIGHT = f"""
QScrollArea {{ background: transparent; border: none; }}

QScrollBar:vertical {{
    background: {TLight.S1};
    width: 6px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {TLight.BD3}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TLight.ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical  {{ background: none; }}

QLineEdit {{
    background-color: {TLight.S2};
    color: {TLight.P1};
    border: 1px solid {TLight.BD2};
    border-radius: {T.RADIUS_INPUT}px;
    padding: 0 14px;
    font-family: '{T.FONT}';
    font-size: 12px;
    selection-background-color: {TLight.ACCENT};
}}
QLineEdit:focus {{
    border: 1.5px solid {TLight.ACCENT};
    background-color: {TLight.S3};
}}

QToolTip {{
    background-color: {TLight.S2};
    color: {TLight.P1};
    border: 1px solid {TLight.BD2};
    border-radius: 6px;
    padding: 4px 10px;
    font-family: '{T.FONT}';
    font-size: 11px;
}}

QMessageBox {{
    background-color: {TLight.S2};
    color: {TLight.P1};
    font-family: '{T.FONT}';
}}
QMessageBox QLabel {{
    color: {TLight.P1};
    background: transparent;
    font-family: '{T.FONT}';
    font-size: 12px;
}}
QMessageBox QPushButton {{
    background-color: {TLight.S3};
    color: {TLight.P1};
    border: 1px solid {TLight.BD2};
    border-radius: {T.RADIUS_BTN}px;
    padding: 6px 20px;
    font-family: '{T.FONT}';
    font-size: 11px;
    min-width: 80px;
}}
QMessageBox QPushButton:hover {{
    background-color: {TLight.ACCENT};
    border-color: {TLight.ACCENT};
    color: white;
}}
"""


# ══════════════════════════════════════════════════════════════════════
#  SNIPPET LIBRARY  —  QSS strings hay dùng lại
# ══════════════════════════════════════════════════════════════════════

def qss_card(bg: str = T.S2, border: str = T.BD, radius: int = T.RADIUS_CARD) -> str:
    """Base card frame style."""
    return f"""
        background-color: {bg};
        border: 1px solid {border};
        border-radius: {radius}px;
    """

def qss_btn_primary(accent: str = T.ACCENT) -> str:
    """Filled primary button."""
    return f"""
        QPushButton {{
            background-color: {accent};
            color: #FFFFFF;
            border: none;
            border-radius: {T.RADIUS_BTN}px;
            font-family: '{T.FONT}';
            font-weight: 700;
        }}
        QPushButton:hover {{ background-color: {accent}CC; }}
        QPushButton:pressed {{ background-color: {accent}99; }}
        QPushButton:disabled {{
            background-color: {T.S2};
            color: {T.P3};
        }}
    """

def qss_btn_ghost() -> str:
    """Ghost/outline button."""
    return f"""
        QPushButton {{
            background-color: {T.S2};
            color: {T.P2};
            border: 1px solid {T.BD2};
            border-radius: {T.RADIUS_BTN}px;
            font-family: '{T.FONT}';
        }}
        QPushButton:hover {{
            background-color: {T.S3};
            color: {T.P1};
            border-color: {T.BD3};
        }}
        QPushButton:pressed {{ background-color: {T.S1}; }}
        QPushButton:disabled {{
            background-color: {T.S1};
            color: {T.P3};
            border-color: {T.BD};
        }}
    """

def qss_btn_danger() -> str:
    """Danger/exit button."""
    return f"""
        QPushButton {{
            background-color: {T.S2};
            color: {T.P2};
            border: 1px solid {T.BD};
            border-radius: {T.RADIUS_BTN}px;
            font-family: '{T.FONT}';
        }}
        QPushButton:hover {{
            background-color: {T.S3};
            color: {T.RED};
            border-color: {T.RED}80;
        }}
        QPushButton:pressed {{ background-color: {T.S3}; }}
    """

def qss_chip(accent: str) -> str:
    """Accent category chip / badge."""
    return f"""
        color: {accent};
        background: {accent}18;
        border: 1px solid {accent}40;
        border-radius: 8px;
        padding: 1px 0;
        font-family: '{T.FONT}';
        font-weight: 700;
    """

def qss_nav_item(active: bool, accent: str = T.ACCENT) -> str:
    """Sidebar nav button."""
    if active:
        return f"""
            QPushButton {{
                background-color: {accent}22;
                color: {accent};
                border: none;
                border-left: 2px solid {accent};
                border-radius: 8px;
                text-align: left;
                padding-left: 12px;
                font-family: '{T.FONT}';
                font-weight: 600;
            }}
        """
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {T.P2};
            border: none;
            border-radius: 8px;
            text-align: left;
            padding-left: 14px;
            font-family: '{T.FONT}';
        }}
        QPushButton:hover {{
            background-color: {T.S3};
            color: {T.P1};
        }}
    """
