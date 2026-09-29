# -*- coding: utf-8 -*-
"""
boolean_select.py

Created on Mon July 20 2026

@author: Sheila Monera Cabarique
"""
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QWidget, QHBoxLayout, QRadioButton, QButtonGroup

from .info_label import InfoLabel


class BooleanSelect(QWidget):
    """
    A horizontal group of radio buttons for boolean-style choices
    (['True', 'False'], ['Yes', 'No'], etc.), with a label and optional tooltip.

    Parameters:
        parent: parent widget
        label_text (str): label shown to the left of the radio buttons
        options (list[str]): option strings, e.g. ['True', 'False']
        default (str, optional): initially selected option; defaults to options[0]
        info_text (str, optional): tooltip text for the label
    """

    changed = Signal()  # uniform signal name gui_utils' dependency watching relies on

    def __init__(self, parent, label_text, options, default=None, info_text=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

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
            layout.addWidget(btn)

        layout.addStretch(1)

    def get(self):
        """
        Return the selected value, converting 'True'/'False' text to Python
        booleans automatically.
        """
        for btn in self.radio_buttons:
            if btn.isChecked():
                text = btn.text()
                if text == "True":
                    return True
                if text == "False":
                    return False
                return text
        return None

    def set(self, value):
        """Programmatically select an option (accepts bool or the raw string)."""
        target = str(value) if isinstance(value, bool) else value
        for btn in self.radio_buttons:
            if btn.text() == target:
                btn.setChecked(True)
                return