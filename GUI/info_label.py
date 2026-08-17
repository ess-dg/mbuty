# -*- coding: utf-8 -*-
"""
info_label.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique

Tooltip display (positioning, screen-edge clamping, show/hide timing) is
handled natively by Qt via QWidget.setToolTip() -- no custom tooltip
widget needed. Font size comes from the app-wide stylesheet in theme.py
via QSS role markers, so there's nothing to update here when the theme
changes.
"""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton, QSizePolicy

from . import theme


class InfoLabel(QWidget):
    """
    A label with an optional "(i)" tooltip button next to it, used as the
    left-hand column of every parameter row.

    Parameters:
        parent: parent widget (may be None; layouts don't require it up front)
        text (str): main label text
        info (str, optional): tooltip text. If None, no info button is shown.
        width (int, optional): fixed width of the label column.
                                Defaults to theme.LABEL_WIDTH.
    """

    def __init__(self, parent=None, text="", info=None, width=None):
        super().__init__(parent)

        width = width if width is not None else theme.LABEL_WIDTH
        self.setFixedWidth(width)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.main_label = QLabel(text)
        self.main_label.setWordWrap(True)
        self.main_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.main_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.main_label, stretch=1)

        self.info_btn = None
        if info:
            self.info_btn = self._make_info_button(info)
            layout.addWidget(self.info_btn, alignment=Qt.AlignTop)

    def _make_info_button(self, info):
        btn = QToolButton()
        btn.setText("(i)")
        btn.setFixedSize(theme.ICON_BUTTON_SIZE, theme.ICON_BUTTON_SIZE)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(info)
        btn.setFocusPolicy(Qt.NoFocus)
        return btn

    def set_text(self, text):
        self.main_label.setText(text)

    def set_info(self, info):
        """Add, replace, or hide (pass None) the tooltip button after construction."""
        if info and self.info_btn is None:
            self.info_btn = self._make_info_button(info)
            self.layout().addWidget(self.info_btn, alignment=Qt.AlignTop)
        if self.info_btn is not None:
            if info:
                self.info_btn.setToolTip(info)
                self.info_btn.setVisible(True)
            else:
                self.info_btn.setVisible(False)