# -*- coding: utf-8 -*-
"""
range_entry.py

qtpy replacement for the Tk RangeEntryWidgets (linked min/max numeric entry
pair with invalid-range highlighting).

Notably simpler than the Tk version:
- No dummy_focus_holder / root.bind_all("<Button-1>", ...) hack to detect
  "clicked outside the entry" — QLineEdit's own `editingFinished` signal
  fires exactly when focus leaves the widget (Enter, Tab, or click away),
  so validation just connects to that.
- No manual bg color juggling — invalid state goes through
  theme.set_widget_state(), which flips a QSS selector.
"""
from qtpy.QtCore import Signal
from qtpy.QtGui import QIntValidator, QDoubleValidator
from qtpy.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel

from .info_label import InfoLabel
from . import theme


class RangeEntryWidgets(QWidget):
    """
    A pair of linked entry fields defining a numeric range [min, max].

    Parameters:
        parent: parent widget
        label_text (str): label for the range input
        default (tuple): (min_value, max_value) initial values
        info_text (str, optional): tooltip text for the label
        input_validation (str): 'int' or 'float'
    """

    rangeChanged = Signal()  # emitted whenever a valid range is (re)confirmed
    changed = Signal()  # uniform alias gui_utils' dependency watching relies on; emitted alongside rangeChanged

    def __init__(self, parent, label_text, default=(0, 1), info_text=None, input_validation="float"):
        super().__init__(parent)
        self.input_validation = input_validation

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.info_label = InfoLabel(text=label_text, info=info_text)
        layout.addWidget(self.info_label)

        self.entry_min = QLineEdit(str(default[0]))
        self.entry_max = QLineEdit(str(default[1]))
        self.entry_min.setFixedWidth((theme.INPUT_WIDTH - 30) // 2)
        self.entry_max.setFixedWidth((theme.INPUT_WIDTH - 30) // 2)

        validator = QIntValidator() if input_validation == "int" else QDoubleValidator()
        self.entry_min.setValidator(validator)
        # QLineEdit doesn't like sharing one QValidator instance across widgets
        # in every Qt binding, so give the max entry its own.
        validator2 = QIntValidator() if input_validation == "int" else QDoubleValidator()
        self.entry_max.setValidator(validator2)

        layout.addWidget(self.entry_min)
        layout.addWidget(QLabel("to"))
        layout.addWidget(self.entry_max)
        layout.addStretch(1)

        self.entry_min.editingFinished.connect(self.validate)
        self.entry_max.editingFinished.connect(self.validate)
        self.entry_min.textChanged.connect(self.validate)
        self.entry_max.textChanged.connect(self.validate)
        self.rangeChanged.connect(self.changed.emit)

        self.validate()

    def validate(self):
        valid = self._is_valid()
        theme.set_widget_state(self.entry_min, "" if valid else "invalid")
        theme.set_widget_state(self.entry_max, "" if valid else "invalid")
        if valid:
            self.rangeChanged.emit()
        return valid

    def get(self):
        """Return [min, max] if valid, else []."""
        if self._is_valid():
            return [self._convert(self.entry_min.text()), self._convert(self.entry_max.text())]
        return []

    def _convert(self, val):
        val = val.strip()
        return int(val) if self.input_validation == "int" else float(val)

    def _is_valid(self):
        try:
            return self._convert(self.entry_min.text()) <= self._convert(self.entry_max.text())
        except ValueError:
            return False