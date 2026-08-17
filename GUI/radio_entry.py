# -*- coding: utf-8 -*-
"""
radio_entry.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique

A vertically stacked radio button group. Functionally this is
BooleanSelect's layout swapped to QVBoxLayout with no True/False coercion
on get() -- kept as a separate class since the config schema in
gui_config.py treats 'radio' and 'bool' as distinct widget types with
different get() semantics.
"""
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QRadioButton, QButtonGroup

from .info_label import InfoLabel


class RadioEntry(QWidget):
    """
    A vertical group of radio buttons with a label and optional tooltip.

    Parameters:
        parent: parent widget
        label_text (str): label shown next to the radio group
        options (list[str]): option strings
        default (str, optional): initially selected option; defaults to options[0]
        info_text (str, optional): tooltip text for the label
    """

    changed = Signal()  # uniform signal name gui_utils' dependency watching relies on

    def __init__(self, parent, label_text, options, default=None, info_text=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        outer.addWidget(self.info_label)

        col = QVBoxLayout()
        col.setSpacing(2)
        outer.addLayout(col)
        outer.addStretch(1)

        self._group = QButtonGroup(self)
        self.radio_buttons = []

        if default is None or default not in options:
            default = options[0]
        for opt in options:
            btn = QRadioButton(opt)
            btn.setChecked(opt == default)
            self._group.addButton(btn)
            self.radio_buttons.append(btn)
            btn.toggled.connect(lambda checked: self.changed.emit() if checked else None)
            col.addWidget(btn)

    def get(self):
        """Return the text of the currently selected option."""
        for btn in self.radio_buttons:
            if btn.isChecked():
                return btn.text()
        return None

    def set(self, value):
        """Programmatically select an option."""
        for btn in self.radio_buttons:
            if btn.text() == value:
                btn.setChecked(True)
                return