# -*- coding: utf-8 -*-
"""
theme.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique

Central styling module for the MBUTY Qt GUI.
"""

from qtpy.QtCore import QObject, Signal, QSize, Qt
from qtpy.QtGui import QFont, QIcon, QPixmap, QPainter, QColor


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"           # falls back to system default if missing
FONT_FAMILY_MONO = "Consolas"      # falls back similarly; used for console/log widgets

FONT_SIZE_BASE = 10       # body text, entries, buttons
FONT_SIZE_LABEL = 10      # field labels
FONT_SIZE_HEADER = 12     # section headers
FONT_SIZE_CONSOLE = 12    # console/log output


def base_font(size=FONT_SIZE_BASE, bold=False):
    f = QFont(FONT_FAMILY, size)
    f.setBold(bold)
    return f


def mono_font(size=FONT_SIZE_CONSOLE):
    return QFont(FONT_FAMILY_MONO, size)


# --------------------------------------------------------------------------
# Layout constants
# --------------------------------------------------------------------------
LABEL_WIDTH = 220         
INPUT_WIDTH = 300         
ROW_SPACING = 6
ICON_BUTTON_SIZE = 20     
BORDER_RADIUS = 6


# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------
LIGHT = {
    "bg":            "#FAF5E9",   # cream
    "surface":       "#FFFFFF",   # cards / input backgrounds
    "surface_alt":   "#F1EAD8",   # header bars, expandable-section headers
    "border":        "#D9D0BA",
    "text":          "#2A2620",
    "text_secondary":"#6B6558",
    "accent":        "#3D6E64",   # muted teal
    "accent_hover":  "#335A52",
    "accent_text":   "#FFFFFF",
    "error":         "#B3413A",
    "error_bg":      "#F8DEDC",
    "success":       "#3D7A4F",
    "disabled":      "#BFB9A8",
}

DARK = {
    "bg":            "#141824",   # dark navy
    "surface":       "#1C2233",
    "surface_alt":   "#232B40",
    "border":        "#323C52",
    "text":          "#E7E9EE",
    "text_secondary":"#9CA3B5",
    "accent":        "#5FA69A",   # muted teal, lightened for dark bg
    "accent_hover":  "#74BAAE",
    "accent_text":   "#0E1420",
    "error":         "#E08A84",
    "error_bg":      "#3A2229",
    "success":       "#7FC495",
    "disabled":      "#4A5266",
}

MPL_RC = {
    "light": {
        "figure.facecolor": LIGHT["surface"],
        "axes.facecolor":   LIGHT["surface"],
        "axes.edgecolor":   LIGHT["border"],
        "axes.labelcolor":  LIGHT["text"],
        "text.color":       LIGHT["text"],
        "xtick.color":      LIGHT["text_secondary"],
        "ytick.color":      LIGHT["text_secondary"],
        "grid.color":       LIGHT["border"],
        "legend.facecolor": LIGHT["surface_alt"],
        "legend.edgecolor": LIGHT["border"],
    },
    "dark": {
        "figure.facecolor": DARK["surface"],
        "axes.facecolor":   DARK["surface"],
        "axes.edgecolor":   DARK["border"],
        "axes.labelcolor":  DARK["text"],
        "text.color":       DARK["text"],
        "xtick.color":      DARK["text_secondary"],
        "ytick.color":      DARK["text_secondary"],
        "grid.color":       DARK["border"],
        "legend.facecolor": DARK["surface_alt"],
        "legend.edgecolor": DARK["border"],
    },
}


_themed_toolbar_cls = None


def _get_themed_toolbar_class():
    """Memoized toolbar subclass that recolors matplotlib icons to match app theme.
    
    matplotlib's dark-mode detection checks QPalette, not QSS stylesheets. Since we
    use stylesheet-only theming, we manually recolor icons using text.color from
    apply_mpl_theme(). Built lazily to avoid forcing matplotlib import at module load.
    """
    global _themed_toolbar_cls
    if _themed_toolbar_cls is None:
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

        class _ThemedNavigationToolbar(NavigationToolbar2QT):
            def _icon(self, name):
                icon = super()._icon(name)
                pixmap = icon.pixmap(QSize(24, 24))
                tinted = QPixmap(pixmap.size())
                tinted.fill(Qt.transparent)
                painter = QPainter(tinted)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                import matplotlib as mpl
                painter.fillRect(tinted.rect(), QColor(mpl.rcParams.get("text.color", "#000000")))
                painter.end()
                return QIcon(tinted)

        _themed_toolbar_cls = _ThemedNavigationToolbar
    return _themed_toolbar_cls


def ThemedNavigationToolbar(*args, **kwargs):
    """Drop-in replacement for NavigationToolbar2QT that themes its own icons.
    Used by dashboard embedded canvases; standalone plt.show() windows use _patch_qt_toolbar().
    """
    return _get_themed_toolbar_class()(*args, **kwargs)


def _patch_qt_toolbar():
    """Patch matplotlib's toolbar class for standalone plt.show() windows.
    
    Must run after matplotlib.backends.backend_qt is imported but before new figures
    are created. Replaces the _toolbar2_class attribute on FigureManagerQT to use
    our themed toolbar for all subsequently created windows."""
    import matplotlib.backends.backend_qt as backend_qt
    themed_cls = _get_themed_toolbar_class()
    if backend_qt.FigureManagerQT._toolbar2_class is not themed_cls:
        backend_qt.FigureManagerQT._toolbar2_class = themed_cls


def apply_mpl_theme(mode="dark"):
    """Apply theme to matplotlib rcParams and patch Qt toolbar for theming.
    Call before creating any Figure or toolbar. Call again if mode changes."""
    import matplotlib as mpl
    mpl.rcParams.update(MPL_RC[mode])
    _patch_qt_toolbar()

# --------------------------------------------------------------------------
# Stylesheet builder
# --------------------------------------------------------------------------
import os
import tempfile
from qtpy.QtGui import QPixmap, QPainter, QColor, QPolygon
from qtpy.QtCore import Qt, QPoint


def _triangle_icon_path(color_hex: str, direction: str) -> str:
    """Renders a small triangle to a real PNG on disk and returns its
    path. QSS's url() only resolves actual file paths or Qt resource
    paths (:/...) -- it has no concept of data: URIs, so embedding the
    triangle as a base64 data URI silently loads nothing. Writing a
    real file sidesteps that entirely."""
    pix = QPixmap(12, 12)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(Qt.NoPen)
    if direction == "down":
        pts = [QPoint(1, 3), QPoint(11, 3), QPoint(6, 9)]
    else:
        pts = [QPoint(1, 7), QPoint(11, 7), QPoint(6, 1)]
    painter.drawPolygon(QPolygon(pts))
    painter.end()

    safe_color = color_hex.lstrip("#")
    path = os.path.join(tempfile.gettempdir(), f"mbuty_arrow_{direction}_{safe_color}.png")
    pix.save(path, "PNG")
    return path.replace("\\", "/")  # QSS url() wants forward slashes, even on Windows

def build_stylesheet(mode="light"):
    p = LIGHT if mode == "light" else DARK
    down_arrow = _triangle_icon_path(p["text_secondary"], "down")
    up_arrow = _triangle_icon_path(p["text_secondary"], "up")

    return f"""
    QWidget {{
        background-color: {p['bg']};
        color: {p['text']};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_SIZE_BASE}pt;
    }}

    QLabel {{
        background: transparent;
        color: {p['text']};
    }}
    QLabel[role="secondary"] {{
        color: {p['text_secondary']};
    }}
    QLabel[role="header"] {{
        color: {p['text']};
        font-size: {FONT_SIZE_HEADER}pt;
        font-weight: 600;
    }}

    QLineEdit, QComboBox, QAbstractSpinBox {{
        background-color: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: {BORDER_RADIUS}px;
        padding: 4px 8px;
        color: {p['text']};
        selection-background-color: {p['accent']};
        selection-color: {p['accent_text']};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {p['accent']};
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        color: {p['disabled']};
        background-color: {p['surface_alt']};
    }}

    /* Validation state */
    QLineEdit[state="invalid"] {{
        border: 1px solid {p['error']};
        background-color: {p['error_bg']};
    }}
    QLineEdit[state="warning"] {{
        border: 1px solid #C98A3D;
        background-color: {"#3A2E1C" if mode == "dark" else "#FBEBD6"};
    }}

    QPushButton {{
        background-color: {p['accent']};
        color: {p['accent_text']};
        border: none;
        border-radius: {BORDER_RADIUS}px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background-color: {p['accent_hover']};
    }}
    QPushButton:disabled {{
        background-color: {p['disabled']};
    }}

    QToolButton {{
        background: transparent;
        border: none;
        color: {p['accent']};
        font-weight: 600;
    }}
    QToolButton:hover {{
        color: {p['accent_hover']};
    }}

    QRadioButton, QCheckBox {{
        background: transparent;
        color: {p['text']};
        spacing: 6px;
    }}
    QRadioButton::indicator {{
        width: 10px;
        height: 10px;
        border-radius: 7px;
    }}
    QRadioButton::indicator:unchecked {{
        border: 2px solid {p['border']};
        background-color: {p['surface']};
    }}
    QRadioButton::indicator:checked {{
        border: 2px solid {p['accent']};
        background-color: {p['accent']};
    }}
        QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 3px;
    }}
    QCheckBox::indicator:unchecked {{
        border: 2px solid {p['border']};
        background-color: {p['surface']};
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 2px solid {p['accent']};
    }}
    QCheckBox::indicator:checked {{
        border: 2px solid {p['accent']};
        background-color: {p['accent']};
    }}

    QScrollArea {{
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border']};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p['text_secondary']};
    }}
    
    QPushButton[role="section-header"] {{
        background-color: {p['surface_alt']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: {BORDER_RADIUS}px;
        padding: 6px 10px;
        text-align: left;
        font-size: {FONT_SIZE_HEADER}pt;
        font-weight: 600;
    }}
    QPushButton[role="section-header"]:hover {{
        background-color: {p['border']};
    }}
    
    QFrame[role="card"] {{
        background-color: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: {BORDER_RADIUS}px;
    }}
    QFrame[role="card"][state="invalid"] {{
        border: 1px solid {p['error']};
        background-color: {p['error_bg']};
    }}

    QToolTip {{
        background-color: {p['surface_alt']};
        color: {p['text']};
        border: 1px solid {p['border']};
        padding: 4px;
    }}

    /* Console / log widget: permanently dark for high ANSI contrast */
    QPlainTextEdit[role="console"], QTextEdit[role="console"] {{
        background-color: #0E1116;
        color: #E7E9EE;
        font-family: "{FONT_FAMILY_MONO}";
        font-size: {FONT_SIZE_CONSOLE}pt;
        border: 1px solid {p['border']};
        border-radius: {BORDER_RADIUS}px;
    }}
    QTabWidget::pane {{
        border: 1px solid {p['border']};
        background: {p['bg']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: {p['surface_alt']};
        color: {p['text_secondary']};
        border: 1px solid {p['border']};
        border-bottom: none;
        padding: 6px 14px;
        margin-right: 2px;
        border-top-left-radius: {BORDER_RADIUS}px;
        border-top-right-radius: {BORDER_RADIUS}px;
    }}
    QTabBar::tab:selected {{
        background: {p['bg']};
        color: {p['text']};
        font-weight: 600;
    }}
    QTabBar::tab:hover {{
        background: {p['border']};
    }}

    QTableView {{
        background-color: {p['surface']};
        alternate-background-color: {p['surface_alt']};
        gridline-color: {p['border']};
        color: {p['text']};
        selection-background-color: {p['accent']};
        selection-color: {p['accent_text']};
        border: 1px solid {p['border']};
    }}
    QHeaderView::section {{
        background-color: {p['surface_alt']};
        color: {p['text']};
        padding: 4px;
        border: 1px solid {p['border']};
    }}

    QMainWindow {{
        background-color: {p['bg']};
    }}
    QMainWindow::separator {{
        background: {p['border']};
        width: 1px;
        height: 1px;
    }}
    QHeaderView::down-arrow {{
        image: url({down_arrow});
        width: 10px;
        height: 10px;
        subcontrol-position: center right;
        margin-right: 6px;
    }}
    QHeaderView::up-arrow {{
        image: url({up_arrow});
        width: 10px;
        height: 10px;
        subcontrol-position: center right;
        margin-right: 6px;
    }}

    QTableCornerButton::section {{
        background-color: {p['surface_alt']};
        border: 1px solid {p['border']};
    }}
    """


# --------------------------------------------------------------------------
# ThemeManager
# --------------------------------------------------------------------------
class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app, mode="dark"):
        super().__init__()
        self._app = app
        self._mode = mode
        self._app.setStyle("Fusion")
        self.apply(mode)

    @property
    def mode(self):
        return self._mode

    @property
    def palette(self):
        return LIGHT if self._mode == "light" else DARK

    def apply(self, mode):
        self._mode = mode
        self._app.setStyleSheet(build_stylesheet(mode))
        self.theme_changed.emit(mode)

    def set_mode(self, mode):
        if mode not in ("light", "dark"):
            raise ValueError("mode must be 'light' or 'dark'")
        if mode != self._mode:
            self.apply(mode)

    def toggle(self):
        self.set_mode("dark" if self._mode == "light" else "light")


def set_widget_state(widget, state):
    widget.setProperty("state", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)