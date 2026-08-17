# -*- coding: utf-8 -*-
"""
expandable_section.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique
"""
from qtpy.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QSizePolicy


class ExpandableSection(QWidget):
    """
    A collapsible/expandable section with a toggleable header.
    """

    def __init__(self, parent, title_text, expanded=False):
        super().__init__(parent)
        self.title_text = title_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toggle_button = QPushButton()
        self.toggle_button.setProperty("role", "section-header")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.setStyleSheet("text-align: left; padding-left: 10px;")
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button)

        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.content_frame)

        self._set_arrow_text()
        self.content_frame.setVisible(expanded)

    def toggle(self):
        expanded = self.toggle_button.isChecked()
        self.content_frame.setVisible(expanded)
        self._set_arrow_text()

    def _set_arrow_text(self):
        arrow = "\u25bc " if self.toggle_button.isChecked() else "\u25b6 "  # ▼ / ▶
        self.toggle_button.setText(arrow + self.title_text)

    def get_content_frame(self):
        return self.content_frame

    @property
    def is_expanded(self):
        return self.toggle_button.isChecked()